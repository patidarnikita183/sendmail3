from flask import Blueprint, render_template, redirect, url_for, session, jsonify, request, Response, render_template_string
from .auth import get_auth_url, get_access_token, make_graph_request
from .database import save_campaign, save_email_tracking, save_sender_info, recipients_collection, campaigns_collection, email_opens_collection, link_clicks_collection, unsubscribes_collection, replies_collection,senders_collection
from .tracking import add_email_tracking, is_email_unsubscribed, record_unsubscribe, save_reply_tracking, extract_tracking_id_from_email, find_campaign_by_recipient_email
from .email import process_uploaded_file, parse_email_addresses, validate_email
from .config import Config
import uuid
import requests
import time
from urllib.parse import unquote
from datetime import datetime, timezone, timedelta
import base64

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return redirect('/app')

@main_bp.route('/app')
def main_app():
    return render_template("frontend.html")

@main_bp.route('/signin')
def signin():
    auth_url = get_auth_url()
    return redirect(auth_url)

@main_bp.route('/callback')
def oauth_callback():
    if 'code' not in request.args:
        return redirect(url_for('main.main_app'))
    
    auth_code = request.args.get('code')
    token_response = get_access_token(auth_code)
    
    if token_response and 'access_token' in token_response:
        session['access_token'] = token_response['access_token']
        try:
            user_profile = make_graph_request('/me', token_response['access_token'])
            session['user_profile'] = user_profile
            print(f"User signed in: {user_profile.get('displayName', 'Unknown')} ({user_profile.get('mail', user_profile.get('userPrincipalName', 'Unknown'))})")
        except Exception as error:
            print(f"Error getting user profile: {error}")
        return redirect(url_for('main.main_app', auth='success'))
    else:
        print(f"Token acquisition error: {token_response}")
        return redirect(url_for('main.main_app', auth='error'))

@main_bp.route('/get-user-profile')
def get_user_profile():
    try:
        access_token = session.get('access_token')
        if not access_token:
            return jsonify({'error': 'User not authenticated'}), 401
        user = make_graph_request('/me', access_token)
        return jsonify({
            'displayName': user.get('displayName', 'Unknown'),
            'email': user.get('mail') or user.get('userPrincipalName', 'Unknown'),
            'id': user.get('id', ''),
            'jobTitle': user.get('jobTitle', ''),
            'officeLocation': user.get('officeLocation', '')
        })
    except Exception as error:
        print(f"Error getting user profile: {error}")
        return jsonify({'error': 'Error fetching user profile'}), 500

# @main_bp.route('/get-mails/<int:num>')
# def get_mails(num):
#     try:
#         access_token = session.get('access_token')
#         if not access_token:
#             return "User not authenticated. Please sign in first.", 401
#         messages = make_graph_request(f'/me/messages?$top={num}', access_token)
#         return jsonify(messages)
#     except Exception as error:
#         print(f"Error fetching messages: {error}")
#         return str(error), 500

@main_bp.route('/get-mails/<int:num>')
def get_mails(num):
    try:
        access_token = session.get('access_token')
        if not access_token:
            return "User not authenticated. Please sign in first.", 401
        
        # Get user profile to identify the sender
        user_profile = session.get('user_profile')
        if not user_profile:
            return "User profile not found", 400
        
        sender_email = user_profile.get('mail', user_profile.get('userPrincipalName', '')).lower()
        
        # Get all campaign IDs for this sender
        campaign_ids = [campaign['id'] for campaign in campaigns_collection.find(
            {"sender_email": sender_email}, 
            {"id": 1}
        )]
        
        if not campaign_ids:
            return jsonify({
                'value': [],
                'message': 'No campaigns found for this sender'
            })
        
        # Get all tracking IDs for these campaigns
        tracking_ids = [recipient['tracking_id'] for recipient in recipients_collection.find(
            {"campaign_id": {"$in": campaign_ids}}, 
            {"tracking_id": 1}
        )]
        
        if not tracking_ids:
            return jsonify({
                'value': [],
                'message': 'No recipients found for campaigns'
            })
        
        # Get recipient emails for these tracking IDs
        recipient_emails = [recipient['email'] for recipient in recipients_collection.find(
            {"tracking_id": {"$in": tracking_ids}}, 
            {"email": 1}
        )]
        
        if not recipient_emails:
            return jsonify({
                'value': [],
                'message': 'No recipient emails found'
            })
        
        # Fetch messages from Outlook
        messages = make_graph_request(f'/me/messages?$top={num * 5}', access_token)  # Increased multiplier to get more messages
        
        if not isinstance(messages, dict) or 'value' not in messages:
            return jsonify(messages)
        
        # Filter messages to only include those sent BY your app
        filtered_messages = []
        for message in messages['value']:
            # Check if this is an app-sent email by looking for tracking URLs in content
            message_content = message.get('body', {}).get('content', '')
            
            # Check if the email contains your app's tracking domain/signature
            # Replace 'your-tracking-domain.com' with your actual tracking domain
            is_app_sent = any([
                'ngrok-free.app/track/' in message_content,  # Based on your JSON example
                '/track/open/' in message_content,
                '/track/click/' in message_content,
                '/unsubscribe/' in message_content
            ])
            
            if is_app_sent:
                # Additional verification: check if sent to campaign recipients
                to_recipients = message.get('toRecipients', [])
                cc_recipients = message.get('ccRecipients', [])
                bcc_recipients = message.get('bccRecipients', [])
                all_recipients = to_recipients + cc_recipients + bcc_recipients
                
                # Verify this email was sent to a campaign recipient
                is_campaign_email = False
                for recipient in all_recipients:
                    recipient_email = recipient.get('emailAddress', {}).get('address', '').lower()
                    if recipient_email in recipient_emails:
                        # Find campaign context
                        recipient_data = recipients_collection.find_one({
                            "email": recipient_email,
                            "campaign_id": {"$in": campaign_ids}
                        })
                        
                        if recipient_data:
                            campaign_data = campaigns_collection.find_one({
                                "id": recipient_data['campaign_id']
                            })
                            
                            # Add campaign metadata to message
                            message['campaign_info'] = {
                                'campaign_id': recipient_data['campaign_id'],
                                'campaign_name': campaign_data.get('name', 'Unknown') if campaign_data else 'Unknown',
                                'tracking_id': recipient_data['tracking_id'],
                                'recipient_name': recipient_data.get('name', 'Unknown')
                            }
                            
                            is_campaign_email = True
                            break
                
                if is_campaign_email:
                    filtered_messages.append(message)
            
            # Stop if we have enough messages
            if len(filtered_messages) >= num:
                break
        
        # Limit to requested number
        filtered_messages = filtered_messages[:num]
        
        return jsonify({
            'value': filtered_messages,
            'total_filtered': len(filtered_messages),
            'total_campaigns': len(campaign_ids),
            'total_recipients': len(recipient_emails)
        })
        
    except Exception as error:
        print(f"Error fetching filtered messages: {error}")
        return str(error), 500
@main_bp.route('/track/open/<tracking_id>')
def track_email_open(tracking_id):
    try:
        recipient = recipients_collection.find_one({"tracking_id": tracking_id})
        if recipient:
            email = recipient.get("email")
            name = recipient.get("name")
            ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            user_agent = request.headers.get('User-Agent', '')
            open_data = {
                "tracking_id": tracking_id,
                "opened_at": datetime.now(timezone(timedelta(hours=5, minutes=30))),
                "ip_address": ip_address,
                "user_agent": user_agent
            }
            email_opens_collection.insert_one(open_data)
            print(f"📧 EMAIL OPENED: {name} ({email}) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        pixel_data = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')
        return Response(
            pixel_data,
            mimetype='image/gif',
            headers={
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        )
    except Exception as e:
        print(f"Error tracking email open: {e}")
        pixel_data = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')
        return Response(pixel_data, mimetype='image/gif')

@main_bp.route('/track/click/<tracking_id>/<path:encoded_url>')
def track_link_click(tracking_id, encoded_url):
    try:
        original_url = unquote(encoded_url)
        recipient = recipients_collection.find_one({"tracking_id": tracking_id})
        if recipient:
            email = recipient.get("email")
            name = recipient.get("name")
            ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            user_agent = request.headers.get('User-Agent', '')
            click_data = {
                "tracking_id": tracking_id,
                "url": original_url,
                "clicked_at": datetime.now(timezone(timedelta(hours=5, minutes=30))),
                "ip_address": ip_address,
                "user_agent": user_agent
            }
            link_clicks_collection.insert_one(click_data)
            print(f"🖱️ LINK CLICKED: {name} ({email}) -> {original_url} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return redirect(original_url, code=302)
    except Exception as e:
        print(f"Error tracking link click: {e}")
        return jsonify({'error': 'Tracking failed'}), 500

@main_bp.route('/track/view-online/<tracking_id>')
def view_email_online(tracking_id):
    try:
        pipeline = [
            {"$match": {"tracking_id": tracking_id}},
            {"$lookup": {
                "from": "campaigns",
                "localField": "campaign_id",
                "foreignField": "id",
                "as": "campaign"
            }},
            {"$unwind": "$campaign"}
        ]
        result = list(recipients_collection.aggregate(pipeline))
        if result:
            recipient_data = result[0]
            email = recipient_data.get("email")
            name = recipient_data.get("name")
            campaign_id = recipient_data.get("campaign_id")
            content = recipient_data["campaign"].get("content")
            ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            user_agent = request.headers.get('User-Agent', '')
            open_data = {
                "tracking_id": tracking_id,
                "opened_at": datetime.now(timezone(timedelta(hours=5, minutes=30))),
                "ip_address": ip_address,
                "user_agent": user_agent
            }
            email_opens_collection.insert_one(open_data)
            print(f"🌐 EMAIL VIEWED ONLINE: {name} ({email}) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            return f'''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Email View</title>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
            </head>
            <body style="margin: 0; padding: 0; background: #f4f4f4;">
                <div style="max-width: 600px; margin: 0 auto; background: white;">
                    <div style="background: #007bff; color: white; padding: 10px; text-align: center; font-size: 12px;">
                        📧 Email viewed online - Tracking active
                    </div>
                    {content}
                </div>
            </body>
            </html>
            '''
        return "Email not found", 404
    except Exception as e:
        print(f"Error viewing email online: {e}")
        return f"Error: {str(e)}", 500

@main_bp.route('/unsubscribe/<tracking_id>')
def unsubscribe_email(tracking_id):
    try:
        recipient = recipients_collection.find_one({"tracking_id": tracking_id})
        if not recipient:
            return render_template_string('''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Unsubscribe - Invalid Link</title>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; text-align: center; }
                    .error { color: #dc3545; }
                </style>
            </head>
            <body>
                <h2 class="error">Invalid Unsubscribe Link</h2>
                <p>This unsubscribe link is not valid or has expired.</p>
            </body>
            </html>
            ''', email=email), 404
        
        email = recipient.get("email")
        name = recipient.get("name")
        campaign_id = recipient.get("campaign_id")
        campaign = campaigns_collection.find_one({"id": campaign_id})
        sender_email = campaign.get("sender_email", "").lower()
        
        if is_email_unsubscribed(email, sender_email):
            return render_template_string('''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Already Unsubscribed</title>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; text-align: center; }
                    .info { color: #0066cc; }
                    .success { color: #28a745; }
                </style>
            </head>
            <body>
                <h2 class="info">Already Unsubscribed</h2>
                <p>The email address <strong>{{ email }}</strong> is already unsubscribed from our mailing list.</p>
                <p class="success">✅ You will not receive any more emails from us.</p>
            </body>
            </html>
            ''', email=email)
        
        return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Unsubscribe Confirmation</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
                .container { background: #f8f9fa; padding: 30px; border-radius: 10px; text-align: center; }
                .btn { display: inline-block; padding: 12px 24px; margin: 10px; text-decoration: none; border-radius: 5px; font-weight: bold; }
                .btn-danger { background: #dc3545; color: white; }
                .btn-secondary { background: #6c757d; color: white; }
                .btn:hover { opacity: 0.8; }
            </style>
        </head>
        <body>
            <div class="container">
                <h2>🚫 Unsubscribe Confirmation</h2>
                <p>Are you sure you want to unsubscribe <strong>{{ email }}</strong> from our mailing list?</p>
                <p><strong>{{ name }}</strong>, you will no longer receive emails from us.</p>
                <form method="POST" action="{{ url_for('main.confirm_unsubscribe', tracking_id=tracking_id) }}" style="display: inline;">
                    <button type="submit" class="btn btn-danger">Yes, Unsubscribe Me</button>
                </form>
                <a href="javascript:history.back()" class="btn btn-secondary">Cancel</a>
                <p style="margin-top: 30px; font-size: 12px; color: #6c757d;">
                    This action cannot be undone. You can always resubscribe by contacting us directly.
                </p>
            </div>
        </body>
        </html>
        ''', email=email, name=name, tracking_id=tracking_id)
    except Exception as e:
        print(f"Error in unsubscribe page: {e}")
        return "Error processing unsubscribe request", 500

@main_bp.route('/unsubscribe/<tracking_id>', methods=['POST'])
def confirm_unsubscribe(tracking_id):
    try:
        recipient = recipients_collection.find_one({"tracking_id": tracking_id})
        if not recipient:
            return "Invalid unsubscribe request", 404
        email = recipient.get("email")
        name = recipient.get("name")
        campaign_id = recipient.get("campaign_id")
        if record_unsubscribe(email, tracking_id, campaign_id):
            return render_template_string('''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Successfully Unsubscribed</title>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; text-align: center; }
                    .success { color: #28a745; background: #d4edda; padding: 20px; border-radius: 5px; border: 1px solid #c3e6cb; }
                </style>
            </head>
            <body>
                <div class="success">
                    <h2>✅ Successfully Unsubscribed</h2>
                    <p><strong>{{ email }}</strong> has been removed from our mailing list.</p>
                    <p>You will no longer receive emails from us.</p>
                    <p style="margin-top: 20px; font-size: 12px;">
                        Thank you for your time. If you have any feedback, please feel free to contact us.
                    </p>
                </div>
            </body>
            </html>
            ''', email=email)
        return "Error processing unsubscribe", 500
    except Exception as e:
        print(f"Error confirming unsubscribe: {e}")
        return "Error processing unsubscribe request", 500

@main_bp.route('/api/analytics/campaign/<campaign_id>')
def get_campaign_analytics(campaign_id):
    try:
        check_response = check_campaign_replies(campaign_id)
        campaign = campaigns_collection.find_one({"id": campaign_id})
        sender_email = campaign.get("sender_email").lower()
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        total_sent = recipients_collection.count_documents({"campaign_id": campaign_id})
        recipient_tracking_ids = [r["tracking_id"] for r in recipients_collection.find({"campaign_id": campaign_id}, {"tracking_id": 1})]
        recipient_emails = [r["email"] for r in recipients_collection.find({"campaign_id": campaign_id}, {"email": 1})]
        
        unique_opens_pipeline = [
            {"$match": {"tracking_id": {"$in": recipient_tracking_ids}}},
            {"$group": {"_id": "$tracking_id"}},
            {"$count": "unique_opens"}
        ]
        unique_opens_result = list(email_opens_collection.aggregate(unique_opens_pipeline))
        unique_opens = unique_opens_result[0]["unique_opens"] if unique_opens_result else 0
        
        total_opens = email_opens_collection.count_documents({"tracking_id": {"$in": recipient_tracking_ids}})
        
        unique_clicks_pipeline = [
            {"$match": {"tracking_id": {"$in": recipient_tracking_ids}}},
            {"$group": {"_id": "$tracking_id"}},
            {"$count": "unique_clicks"}
        ]
        unique_clicks_result = list(link_clicks_collection.aggregate(unique_clicks_pipeline))
        unique_clicks = unique_clicks_result[0]["unique_clicks"] if unique_clicks_result else 0
        
        total_clicks = link_clicks_collection.count_documents({"tracking_id": {"$in": recipient_tracking_ids}})
        
        unsubscribe_count = unsubscribes_collection.count_documents({
            "email": {"$in": recipient_emails},
            "sender_email": sender_email.lower()
        })
        
        unsubscribe_details = list(unsubscribes_collection.find(
            {"email": {"$in": recipient_emails}, "sender_email": sender_email.lower()},
            {"email": 1, "unsubscribed_at": 1, "tracking_id": 1}
        ))
        
        reply_count = replies_collection.count_documents({"campaign_id": campaign_id})
        
        reply_details = list(replies_collection.find(
            {"campaign_id": campaign_id},
            {"sender_email": 1, "sender_name": 1, "subject": 1, "received_at": 1, "tracking_id": 1, "body_content": 1}
        ).sort("received_at", -1))
        
        unique_reply_pipeline = [
            {"$match": {"campaign_id": campaign_id}},
            {"$group": {"_id": "$sender_email"}},
            {"$count": "unique_replies"}
        ]
        unique_reply_result = list(replies_collection.aggregate(unique_reply_pipeline))
        unique_replies = unique_reply_result[0]["unique_replies"] if unique_reply_result else 0
        
        recipients_data = []
        for recipient in recipients_collection.find({"campaign_id": campaign_id}):
            tracking_id = recipient["tracking_id"]
            email = recipient["email"]
            opens_count = email_opens_collection.count_documents({"tracking_id": tracking_id})
            clicks_count = link_clicks_collection.count_documents({"tracking_id": tracking_id})
            replies_count = replies_collection.count_documents({"tracking_id": tracking_id})
            first_open = email_opens_collection.find_one({"tracking_id": tracking_id}, sort=[("opened_at", 1)])
            first_open_time = first_open["opened_at"] if first_open else None
            first_click = link_clicks_collection.find_one({"tracking_id": tracking_id}, sort=[("clicked_at", 1)])
            first_click_time = first_click["clicked_at"] if first_click else None
            sent_at = recipient.get("sent_at", None)
            unsubscribe_info = unsubscribes_collection.find_one({"email": email, "sender_email": sender_email.lower()})
            is_unsubscribed = unsubscribe_info is not None
            unsubscribe_date = unsubscribe_info["unsubscribed_at"] if unsubscribe_info else None
            reply_info = replies_collection.find_one({"tracking_id": tracking_id})
            has_replied = reply_info is not None
            reply_date = reply_info["received_at"] if reply_info else None
            recipients_data.append({
                'email': email,
                'name': recipient["name"],
                'tracking_id': tracking_id,
                'opens': opens_count,
                'clicks': clicks_count,
                'replies': replies_count,
                'first_open': first_open_time if first_open_time else None,
                'first_click':first_click_time,
                'sent_at':sent_at,
                'unsubscribed': is_unsubscribed,
                'unsubscribe_date': unsubscribe_date if unsubscribe_date else None,
                'replied': has_replied,
                'reply_date': reply_date if reply_date else None
            })
        
        open_rate = (unique_opens / total_sent * 100) if total_sent > 0 else 0
        click_rate = (unique_clicks / total_sent * 100) if total_sent > 0 else 0
        click_to_open_rate = (unique_clicks / unique_opens * 100) if unique_opens > 0 else 0
        unsubscribe_rate = (unsubscribe_count / total_sent * 100) if total_sent > 0 else 0
        reply_rate = (unique_replies / total_sent * 100) if total_sent > 0 else 0
        
        data = {
            'campaign_id': campaign_id,
            'campaign_name': campaign.get("name"),
            'subject': campaign.get("subject"),
            'total_sent': total_sent,
            'unique_opens': unique_opens,
            'total_opens': total_opens,
            'unique_clicks': unique_clicks,
            'total_clicks': total_clicks,
            'unsubscribe_count': unsubscribe_count,
            'reply_count': reply_count,
            'unique_replies': unique_replies,
            'open_rate': round(open_rate, 2),
            'click_rate': round(click_rate, 2),
            'click_to_open_rate': round(click_to_open_rate, 2),
            'unsubscribe_rate': round(unsubscribe_rate, 2),
            'reply_rate': round(reply_rate, 2),
            'recipients': recipients_data,
            'unsubscribe_details': [
                {
                    'email': unsub['email'],
                    'unsubscribed_at': unsub['unsubscribed_at'].isoformat(),
                    'tracking_id': unsub.get('tracking_id')
                } for unsub in unsubscribe_details
            ],
            'reply_details': [
                {
                    'sender_email': reply['sender_email'],
                    'sender_name': reply['sender_name'],
                    'subject': reply['subject'],
                    'received_at': reply['received_at'].isoformat(),
                    'tracking_id': reply.get('tracking_id'),
                    'body_preview': reply.get('body_content', '')[:200] + '...' if len(reply.get('body_content', '')) > 200 else reply.get('body_content', '')
                } for reply in reply_details
            ]
        }
        print("Updated analytics response with reply data -------\n", data)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/analytics/all-campaigns')
def get_all_campaigns_analytics():
    try:
        campaigns_data = []
        for campaign in campaigns_collection.find().sort("created_at", -1):
            campaign_id = campaign["id"]
            total_recipients = campaign.get("total_recipients", 0)
            recipient_tracking_ids = [r["tracking_id"] for r in recipients_collection.find({"campaign_id": campaign_id}, {"tracking_id": 1})]
            if recipient_tracking_ids:
                unique_opens_pipeline = [
                    {"$match": {"tracking_id": {"$in": recipient_tracking_ids}}},
                    {"$group": {"_id": "$tracking_id"}},
                    {"$count": "unique_opens"}
                ]
                unique_opens_result = list(email_opens_collection.aggregate(unique_opens_pipeline))
                unique_opens = unique_opens_result[0]["unique_opens"] if unique_opens_result else 0
                unique_clicks_pipeline = [
                    {"$match": {"tracking_id": {"$in": recipient_tracking_ids}}},
                    {"$group": {"_id": "$tracking_id"}},
                    {"$count": "unique_clicks"}
                ]
                unique_clicks_result = list(link_clicks_collection.aggregate(unique_clicks_pipeline))
                unique_clicks = unique_clicks_result[0]["unique_clicks"] if unique_clicks_result else 0
            else:
                unique_opens = 0
                unique_clicks = 0
            open_rate = (unique_opens / total_recipients * 100) if total_recipients > 0 else 0
            click_rate = (unique_clicks / total_recipients * 100) if total_recipients > 0 else 0
            campaigns_data.append({
                'campaign_id': campaign_id,
                'name': campaign.get("name"),
                'subject': campaign.get("subject"),
                'created_at': campaign.get("created_at").isoformat() if campaign.get("created_at") else None,
                'sent_at': campaign.get("sent_at").isoformat() if campaign.get("sent_at") else None,
                'total_recipients': total_recipients,
                'unique_opens': unique_opens,
                'unique_clicks': unique_clicks,
                'open_rate': round(open_rate, 2),
                'click_rate': round(click_rate, 2)
            })
        return jsonify({'campaigns': campaigns_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/unsubscribes')
def get_all_unsubscribes():
    try:
        unsubscribes = list(unsubscribes_collection.find(
            {}, {"_id": 0, "email": 1, "unsubscribed_at": 1, "campaign_id": 1, "tracking_id": 1}
        ).sort("unsubscribed_at", -1))
        for unsub in unsubscribes:
            if 'unsubscribed_at' in unsub:
                unsub['unsubscribed_at'] = unsub['unsubscribed_at'].isoformat()
        return jsonify({
            'total_unsubscribes': len(unsubscribes),
            'unsubscribes': unsubscribes
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/send-mail', methods=['POST'])
def send_mail():
    try:
        data = {
            "error": "No valid email addresses found after filtering unsubscribed emails",
            "unsubscribed_count": 1,
            "unsubscribed_recipients": [
                {
                    "email": "nikitapatidar.xalt@gmail.com",
                    "name": "nikitapatidar.xalt"
                }
            ]
        }
        return jsonify(data), 201
        
        access_token = session.get('access_token')
        if not access_token:
            return jsonify({'error': 'User not authenticated. Please sign in first.'}), 401
        user_profile = session.get('user_profile')
        if not user_profile:
            return jsonify({'error': 'User profile not found'}), 401
        sender_email = user_profile.get('mail', user_profile.get('userPrincipalName')).lower()
        if not sender_email:
            return jsonify({'error': 'Could not determine client email'}), 400
        
        campaign_id = str(uuid.uuid4())
        try:
            sender_name = user_profile.get('displayName', sender_email.split('@')[0] if '@' in sender_email else 'Unknown')
            save_sender_info(sender_email, sender_name, campaign_id)
        except Exception as e:
            print(f"⚠️ Error saving sender info: {e}")
        
        recipients = []
        if request.content_type and 'multipart/form-data' in request.content_type:
            subject = request.form.get('subject')
            message = request.form.get('message')
            recipients_text = request.form.get('recipients_text', '')
            link = request.form.get("link", "https://www.microsoft.com")
            if 'recipients_file' in request.files:
                file = request.files['recipients_file']
                if file.filename != '':
                    try:
                        recipients_data = process_uploaded_file(file)
                        recipients.extend(recipients_data)
                    except Exception as e:
                        return jsonify({'error': f'Error processing file: {str(e)}'}), 400
            if recipients_text.strip():
                text_recipients = parse_email_addresses(recipients_text)
                recipients.extend([{'name': email.split('@')[0], 'email': email} for email in text_recipients])
        else:
            data = request.json
            subject = data.get('subject')
            message = data.get('message')
            recipients_list = data.get('recipients', [])
            link = data.get("link", "https://www.microsoft.com")
            for recipient in recipients_list:
                if isinstance(recipient, str):
                    recipients.append({'name': recipient.split('@')[0], 'email': recipient})
                else:
                    recipients.append(recipient)
        
        if not recipients:
            return jsonify({'error': 'No recipients specified'}), 400
        if not subject or not message:
            return jsonify({'error': 'Subject and message are required'}), 400
        
        seen_emails = set()
        valid_recipients = []
        invalid_recipients = []
        unsubscribed_recipients = []
        
        for recipient_data in recipients:
            email = recipient_data.get('email', '').strip().lower()
            name = recipient_data.get('name', '').strip()
            print(f"Processing recipient: {name} <{email}>")
            if email and email not in seen_emails:
                if validate_email(email):
                    if is_email_unsubscribed(email, sender_email):
                        unsubscribed_recipients.append({'name': name or email.split('@')[0], 'email': email})
                        print(f"🚫 Skipping unsubscribed email: {email}")
                    else:
                        valid_recipients.append({'name': name or email.split('@')[0], 'email': email})
                    seen_emails.add(email)
                else:
                    invalid_recipients.append(email)
        
        if not valid_recipients:
            return jsonify({
                'error': 'No valid email addresses found after filtering unsubscribed emails',
                'unsubscribed_count': len(unsubscribed_recipients),
                'unsubscribed_recipients': unsubscribed_recipients
            }), 201
        
        save_campaign(campaign_id, subject, message, len(valid_recipients), sender_email)
        
        sent_count = 0
        failed_recipients = []
        tracking_data = []
        
        for recipient in valid_recipients:
            try:
                recipient_email = recipient['email']
                recipient_name = recipient['name']
                tracking_id = str(uuid.uuid4())
                personalized_message = message.replace('{name}', recipient_name)
                personalized_message = personalized_message + link
                tracked_message = add_email_tracking(personalized_message, tracking_id)
                
                send_mail_data = {
                    "message": {
                        "subject": subject,
                        "body": {
                            "contentType": "HTML",
                            "content": tracked_message
                        },
                        "toRecipients": [
                            {
                                "emailAddress": {
                                    "address": recipient_email,
                                    "name": recipient_name
                                }
                            }
                        ]
                    },
                    "saveToSentItems": True
                }
                
                url = f"{Config.GRAPH_ENDPOINT}/me/sendMail"
                headers = {
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json'
                }
                
                response = requests.post(url, headers=headers, json=send_mail_data)
                
                if response.status_code == 202:
                    outlook_message_id = f"outlook_{tracking_id}"
                    save_email_tracking(campaign_id, tracking_id, recipient_name, recipient_email, outlook_message_id)
                    tracking_data.append({
                        'tracking_id': tracking_id,
                        'recipient': f"{recipient_name} <{recipient_email}>",
                        'outlook_id': outlook_message_id,
                        'status': 'sent'
                    })
                    sent_count += 1
                    print(f'✅ Email sent with tracking to {recipient_name} <{recipient_email}> (ID: {tracking_id})')
                else:
                    try:
                        error_data = response.json()
                        error_message = error_data.get('error', {}).get('message', 'Unknown error')
                        print(f'❌ Failed to send email to {recipient_email}: {error_message}')
                        failed_recipients.append(f"{recipient_name} <{recipient_email}>: {error_message}")
                    except ValueError:
                        error_message = f'HTTP {response.status_code}: {response.text}'
                        print(f'❌ Failed to send email to {recipient_email}: {error_message}')
                        failed_recipients.append(f"{recipient_name} <{recipient_email}>: {error_message}")
                time.sleep(0.1)
            except Exception as e:
                print(f'❌ Failed to send email to {recipient_email}: {e}')
                failed_recipients.append(f"{recipient_name} <{recipient_email}>: {str(e)}")
        
        response_data = {
            'success': True,
            'campaign_id': campaign_id,
            'sent_count': sent_count,
            'total_recipients': len(valid_recipients),
            'unsubscribed_count': len(unsubscribed_recipients),
            'tracking_data': tracking_data,
            'tracking_enabled': True,
            'analytics_url': f'{Config.BASE_URL}/api/analytics/campaign/{campaign_id}'
        }
        
        if invalid_recipients:
            response_data['invalid_recipients'] = invalid_recipients
        if failed_recipients:
            response_data['failed_recipients'] = failed_recipients
        if unsubscribed_recipients:
            response_data['unsubscribed_recipients'] = unsubscribed_recipients
            response_data['message'] = f'Skipped {len(unsubscribed_recipients)} unsubscribed recipients'
        
        print(f"📊 Campaign {campaign_id} sent with tracking enabled!")
        print(f"🚫 Skipped {len(unsubscribed_recipients)} unsubscribed recipients")
        print(f"📈 View analytics at: {Config.BASE_URL}/api/analytics/campaign/{campaign_id}")
        return jsonify(response_data)
    except Exception as e:
        print(f'❌ Error sending email: {e}')
        return jsonify({'error': f'Failed to send email: {str(e)}'}), 500

@main_bp.route('/send-mail/<recipient>')
def send_mail_single(recipient):
    try:
        access_token = session.get('access_token')
        if not access_token:
            return jsonify({'error': 'User not authenticated. Please sign in first.'}), 401
        subject = request.args.get('subject', 'Wanna go out for lunch?')
        message = request.args.get('message', 'I know a sweet spot that just opened around us!')
        
        send_mail_data = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "Text",
                    "content": message
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": recipient
                        }
                    }
                ]
            },
            "saveToSentItems": True
        }
        
        url = f"{Config.GRAPH_ENDPOINT}/me/sendMail"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.post(url, headers=headers, json=send_mail_data)
        
        if response.status_code == 202:
            return jsonify({'success': True, 'message': 'Email sent successfully'})
        else:
            try:
                error_data = response.json()
                return jsonify({'error': error_data.get('error', {}).get('message', 'Unknown error')}), response.status_code
            except ValueError:
                return jsonify({'error': f'HTTP {response.status_code}: {response.text}'}), response.status_code
    except Exception as error:
        print(f"Error sending message: {error}")
        return jsonify({'error': str(error)}), 500

@main_bp.route('/api/check-replies/<campaign_id>')
def check_campaign_replies(campaign_id):
    try:
        data = {
            "campaign_id": "8ed1a5a7-9710-43fd-903a-3ce5c54512ec",
            "campaign_name": "Campaign 8ed1a5a7-9710-43fd-903a-3ce5c54512ec",
            "click_rate": 100.0,
            "click_to_open_rate": 100.0,
            "open_rate": 100.0,
            "recipients": [
                {
                    "clicks": 1,
                    "email": "nikitapatidar.xalt@gmail.com",
                    "first_click": "Fri, 04 Jul 2025 06:48:42 GMT",
                    "first_open": "Fri, 04 Jul 2025 06:48:16 GMT",
                    "name": "nikitapatidar.xalt",
                    "opens": 1,
                    "replied": True,
                    "replies": 1,
                    "reply_date": "Fri, 04 Jul 2025 06:50:18 GMT",
                    "sent_at": "Fri, 04 Jul 2025 06:47:29 GMT",
                    "tracking_id": "bd4a69da-3ec6-468b-92fe-f1e096b3df83",
                    "unsubscribe_date": "Fri, 04 Jul 2025 06:49:30 GMT",
                    "unsubscribed": True
                }
            ],
            "reply_count": 1,
            "reply_details": [
                {
                    "body_preview": "<html><head>\r\n<meta http-equiv=\"Content-Type\" content=\"text/html; charset=utf-8\"></head><body><div dir=\"ltr\">yes</div><br><div class=\"gmail_quote gmail_quote_container\"><div dir=\"ltr\" class=\"gmail_att...",
                    "received_at": "2025-07-04T06:50:18",
                    "sender_email": "nikitapatidar.xalt@gmail.com",
                    "sender_name": "nikita patidar",
                    "subject": "Re: Wanna go out for lunch?",
                    "tracking_id": "bd4a69da-3ec6-468b-92fe-f1e096b3df83"
                }
            ],
            "reply_rate": 100.0,
            "subject": "Wanna go out for lunch?",
            "total_clicks": 1,
            "total_opens": 1,
            "total_sent": 1,
            "unique_clicks": 1,
            "unique_opens": 1,
            "unique_replies": 1,
            "unsubscribe_count": 1,
            "unsubscribe_details": [
                {
                    "email": "nikitapatidar.xalt@gmail.com",
                    "tracking_id": "bd4a69da-3ec6-468b-92fe-f1e096b3df83",
                    "unsubscribed_at": "2025-07-04T06:49:30.218000"
                }
            ],
            "unsubscribe_rate": 100.0
        }
        return jsonify(data), 200
        access_token = session.get('access_token')
        if not access_token:
            return jsonify({'error': 'User not authenticated'}), 401
        recipients = list(recipients_collection.find(
            {"campaign_id": campaign_id}, 
            {"email": 1, "tracking_id": 1, "name": 1, "sent_at": 1}
        ))
        if not recipients:
            return jsonify({'error': 'Campaign not found'}), 404
        campaign = campaigns_collection.find_one({"id": campaign_id})
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        campaign_start_time = campaign.get('created_at')
        if not campaign_start_time:
            earliest_sent = recipients_collection.find_one(
                {"campaign_id": campaign_id}, 
                sort=[("sent_at", 1)]
            )
            campaign_start_time = earliest_sent.get('sent_at') if earliest_sent else datetime.now() - timedelta(hours=24)
        
        recipient_emails = [r["email"] for r in recipients]
        new_replies_count = 0
        campaign_start_iso = campaign_start_time.isoformat() + 'Z' if isinstance(campaign_start_time, datetime) else campaign_start_time
        
        try:
            messages_response = make_graph_request(
                f'/me/messages?$filter=receivedDateTime ge {campaign_start_iso}&$top=50&$select=id,subject,sender,receivedDateTime,body,conversationId',
                access_token
            )
            if isinstance(messages_response, dict) and 'value' in messages_response:
                messages = messages_response['value']
                for message in messages:
                    try:
                        sender_email = message.get('sender', {}).get('emailAddress', {}).get('address', '').lower()
                        if sender_email in recipient_emails:
                            sender_name = message.get('sender', {}).get('emailAddress', {}).get('name', '')
                            subject = message.get('subject', '')
                            message_id = message.get('id', '')
                            received_at = datetime.fromisoformat(message.get('receivedDateTime', '').replace('Z', '+00:00'))
                            body_content = message.get('body', {}).get('content', '')
                            thread_id = message.get('conversationId', '')
                            recipient_data = next((r for r in recipients if r["email"] == sender_email), None)
                            if recipient_data:
                                tracking_id = recipient_data["tracking_id"]
                                existing_reply = replies_collection.find_one({
                                    "message_id": message_id,
                                    "campaign_id": campaign_id
                                })
                                if not existing_reply:
                                    if save_reply_tracking(
                                        message_id, campaign_id, tracking_id, 
                                        sender_email, sender_name, subject, 
                                        body_content, received_at, thread_id
                                    ):
                                        new_replies_count += 1
                                        print(f"✅ NEW REPLY FOUND for Campaign {campaign_id}: {sender_email}")
                    except Exception as e:
                        print(f"Error processing message: {e}")
                        continue
        except Exception as e:
            print(f"Error fetching messages from Outlook: {e}")
            return jsonify({'error': 'Failed to fetch emails from Outlook'}), 500
        return jsonify({
            'campaign_id': campaign_id,
            'new_replies_found': new_replies_count,
            'total_recipients_checked': len(recipient_emails),
            'campaign_start_time': campaign_start_iso,
            'status': 'success'
        })
    except Exception as e:
        print(f"Error checking campaign replies: {e}")
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/replies/<campaign_id>')
def get_campaign_replies(campaign_id):
    try:
        replies = list(replies_collection.find({"campaign_id": campaign_id}, {"_id": 0}).sort("received_at", -1))
        for reply in replies:
            if 'received_at' in reply:
                reply['received_at'] = reply['received_at'].isoformat()
            if 'processed_at' in reply:
                reply['processed_at'] = reply['processed_at'].isoformat()
        return jsonify({
            'campaign_id': campaign_id,
            'total_replies': len(replies),
            'replies': replies
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/replies/all')
def get_all_replies():
    try:
        replies = list(replies_collection.find({}, {"_id": 0}).sort("received_at", -1))
        for reply in replies:
            if 'received_at' in reply:
                reply['received_at'] = reply['received_at'].isoformat()
            if 'processed_at' in reply:
                reply['processed_at'] = reply['processed_at'].isoformat()
        return jsonify({
            'total_replies': len(replies),
            'replies': replies
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500