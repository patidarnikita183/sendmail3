from flask import Flask, request, redirect, url_for, session, jsonify, render_template,Response,render_template_string
import base64
import urllib.parse
from urllib.parse import quote, unquote
from flask_socketio import SocketIO
import re
import requests
import os
import pandas as pd
from werkzeug.utils import secure_filename
import uuid
import time 
from pymongo import MongoClient
from datetime import datetime, timezone
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta, timezone;


load_dotenv()  
# import urllib.parse
app = Flask(__name__)
app.secret_key = 'any_secret_key'  

print("before mongodb")
MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL,tls=True)
db = client["email_tracking"]
print("after connection to mongodb")


# Collections
print("1")
campaigns_collection = db["campaigns"]
recipients_collection = db["recipients"]
email_opens_collection = db["email_opens"]
link_clicks_collection = db["link_clicks"]
# unsubscribed_collection = db["unsubscribed_emails"]
print("Adding unsubscribe collection...")
unsubscribes_collection = db["unsubscribes"]
print("Unsubscribe collection added")
print("Adding replies collection...")
replies_collection = db["replies"]
print("Replies collection added")

print("2")

# Configuration
print("3")
CLIENT_ID =os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TENANT_ID =os.getenv("TENANT_ID")
PORT = os.getenv("PORT")
REDIRECT_URI = os.getenv("REDIRECT_URI")
# REDIRECT_URI = f"https://8d6e-106-222-213-67.ngrok-free.app:{PORT}/callback"
BASE_URL = os.getenv("BASE_URL")
print("4")
# Microsoft Graph endpoints
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
GRAPH_ENDPOINT = "https://graph.microsoft.com/v1.0"

# Scopes
USER_SCOPES = [
    "User.Read",
    "Mail.Read", 
    "Mail.Send",
    "Mail.ReadWrite"
]
def get_auth_url():
    print("5")
    
    """Generate the authorization URL for Microsoft Graph"""
    params = {
        'client_id': CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'scope': ' '.join(USER_SCOPES),
        'response_mode': 'query',
        'prompt': 'select_account'
    }
    
    auth_url = f"{AUTHORITY}/oauth2/v2.0/authorize?" + urllib.parse.urlencode(params)
    return auth_url
def get_access_token(auth_code):
    print("6")

    """Exchange authorization code for access token"""
    token_url = f"{AUTHORITY}/oauth2/v2.0/token"
    
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': auth_code,
        'redirect_uri': REDIRECT_URI,
        'grant_type': 'authorization_code'
    }
    
    response = requests.post(token_url, data=data)
    return response.json() if response.status_code == 200 else None

print("7")

# Add SocketIO support after your app initialization
socketio = SocketIO(app, cors_allowed_origins="*")
print("8")
# Add your BASE_URL configuration (update with your actual domain/ngrok URL)
# BASE_URL = "http://localhost:9000"  # Update this with your actual domain or ngrok URL
# BASE_URL =  "https://a31a-2401-4900-8821-dad7-3d1e-864e-454a-65e0.ngrok-free.app"
# Database initialization function
def init_tracking_db():
    """Initialize tracking database with indexes"""
    try:
        # Existing indexes...
        campaigns_collection.create_index("id", unique=True)
        recipients_collection.create_index("tracking_id", unique=True)
        recipients_collection.create_index("campaign_id")
        email_opens_collection.create_index("tracking_id")
        link_clicks_collection.create_index("tracking_id")
        
        # Existing unsubscribed emails index
        unsubscribes_collection.create_index("email", unique=True)
        unsubscribes_collection.create_index("tracking_id")
        unsubscribes_collection.create_index("unsubscribed_at")
        
        # UPDATED: Replies indexes focused on campaign-specific queries
        replies_collection.create_index([("campaign_id", 1), ("message_id", 1)], unique=True)  # Compound unique index
        replies_collection.create_index("campaign_id")  # Fast campaign lookups
        replies_collection.create_index("tracking_id")
        replies_collection.create_index("sender_email")
        replies_collection.create_index("received_at")
        
        print("✅ Campaign-specific replies MongoDB database initialized")
        print("✅ Email tracking MongoDB database initialized")
    except Exception as e:
        print(f"Error initializing database: {e}")

# Function to save campaign data
def save_campaign(campaign_id, subject, message, total_recipients):
    """Save campaign to database"""
    try:
        campaign_data = {
            "id": campaign_id,
            "name": f"Campaign {campaign_id}",
            "subject": subject,
            "content": message,
            "status": "sending",
            "created_at":  datetime.now(timezone(timedelta(hours=5, minutes=30))),
            "sent_at": None,
            "total_recipients": total_recipients
        }
        
        campaigns_collection.update_one(
            {"id": campaign_id},
            {"$set": campaign_data},
            upsert=True
        )
        
    except Exception as e:
        print(f"Error saving campaign: {e}")

# Function to save individual email tracking data
def save_email_tracking(campaign_id, tracking_id, recipient_name, recipient_email, outlook_message_id):
    """Save individual email tracking data"""
    try:
        recipient_data = {
            "campaign_id": campaign_id,
            "email": recipient_email,
            "name": recipient_name,
            "tracking_id": tracking_id,
            "sent_at": datetime.now(timezone(timedelta(hours=5, minutes=30))),
            "delivery_status": "sent"
        }
        
        recipients_collection.insert_one(recipient_data)
        
    except Exception as e:
        print(f"Error saving email tracking: {e}")

# Function to add tracking to email content
def add_email_tracking(content, tracking_id):
    """Add tracking pixel, link tracking, and unsubscribe link to email content"""
    
    # Add tracking pixel (invisible 1x1 image)
    tracking_pixel = f'<img src="{BASE_URL}/track/open/{tracking_id}" width="1" height="1" style="display:none;" alt="" border="0">'
    
    # Add CSS-based tracking as backup
    css_tracker = f'<div style="background:url(\'{BASE_URL}/track/open/{tracking_id}\') no-repeat;width:1px;height:1px;display:none;"></div>'
    
    # Add view online link for better tracking reliability
    view_online = f'''
    <div style="text-align: center; padding: 10px; background: #f8f9fa; margin: 10px 0; border-radius: 5px; font-size: 12px;">
        <a href="{BASE_URL}/track/view-online/{tracking_id}" style="color: #6c757d; text-decoration: none;">
            📱 View this email in your browser
        </a>
    </div>
    '''
    
    # Add unsubscribe link
    unsubscribe_link = f'''
    <div style="text-align: center; padding: 15px; background: #f8f9fa; margin: 20px 0; border-radius: 5px; border-top: 1px solid #dee2e6;">
        <p style="margin: 0; font-size: 12px; color: #6c757d;">
            Don't want to receive these emails? 
            <a href="{BASE_URL}/unsubscribe/{tracking_id}" style="color: #dc3545; text-decoration: none;">
                🚫 Unsubscribe here
            </a>
        </p>
        <p style="margin: 5px 0 0 0; font-size: 10px; color: #adb5bd;">
            This will remove you from all future emails from this sender.
        </p>
    </div>
    '''
    
    def replace_link(match):
        original_url = match.group(0)
        if original_url.startswith('http') and BASE_URL not in original_url:
            tracking_url = f"{BASE_URL}/track/click/{tracking_id}/{quote(original_url, safe='')}"
            str1 = f"""<br><br>
                    <a href={tracking_url} style="display: inline-block; background: #00bcf2; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 5px;">
                        🔗 {tracking_url}
                    </a>"""
            return str1
        return original_url

    # Regex to match URLs starting with http or https
    tracked_content = re.sub(r'https?://[^\s]+', replace_link, content)

    # Insert tracking elements and unsubscribe link
    if '<body' in tracked_content:
        body_end = tracked_content.rfind('</body>')
        if body_end != -1:
            # Insert before closing body tag
            tracked_content = (tracked_content[:body_end] + 
                             unsubscribe_link + 
                             tracked_content[body_end:])
        
        body_start = tracked_content.find('>', tracked_content.find('<body'))
        if body_start != -1:
            tracked_content = (tracked_content[:body_start+1] + 
                             tracking_pixel + css_tracker + view_online + 
                             tracked_content[body_start+1:])
    else:
        tracked_content = tracking_pixel + css_tracker + view_online + tracked_content + unsubscribe_link
    
    return tracked_content

# Updated tracking routes
@app.route('/track/open/<tracking_id>')
def track_email_open(tracking_id):
    """Track email opens"""
    try:
        # Check if recipient exists
        recipient = recipients_collection.find_one({"tracking_id": tracking_id})
        
        if recipient:
            email = recipient.get("email")
            name = recipient.get("name")
            ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            user_agent = request.headers.get('User-Agent', '')
            
            # Record the email open
            open_data = {
                "tracking_id": tracking_id,
                "opened_at": datetime.now(timezone(timedelta(hours=5, minutes=30))),
                "ip_address": ip_address,
                "user_agent": user_agent
            }
            
            email_opens_collection.insert_one(open_data)
            
            print(f"📧 EMAIL OPENED: {name} ({email}) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Emit real-time update if using SocketIO
            try:
                socketio.emit('email_opened', {
                    'tracking_id': tracking_id,
                    'email': email,
                    'name': name,
                    'timestamp': datetime.now().isoformat()
                })
            except:
                pass  # SocketIO might not be connected
        
        # Return 1x1 transparent GIF
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



@app.route('/track/click/<tracking_id>/<path:encoded_url>')
def track_link_click(tracking_id, encoded_url):
    """Track link clicks and redirect to original URL"""
    try:
        original_url = unquote(encoded_url)
        
        # Check if recipient exists
        recipient = recipients_collection.find_one({"tracking_id": tracking_id})
        
        if recipient:
            email = recipient.get("email")
            name = recipient.get("name")
            ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            user_agent = request.headers.get('User-Agent', '')
            # Record the link click
            click_data = {
                "tracking_id": tracking_id,
                "url": original_url,
                "clicked_at": datetime.now(timezone(timedelta(hours=5, minutes=30))),
                "ip_address": ip_address,
                "user_agent": user_agent
            }
            
            link_clicks_collection.insert_one(click_data)
            
            print(f"🖱️  LINK CLICKED: {name} ({email}) -> {original_url} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Emit real-time update if using SocketIO
            try:
                socketio.emit('link_clicked', {
                    'tracking_id': tracking_id,
                    'email': email,
                    'name': name,
                    'url': original_url,
                    'timestamp': datetime.now().isoformat()
                })
            except:
                pass  # SocketIO might not be connected
        
        # Redirect to original URL
        return redirect(original_url, code=302)
        
    except Exception as e:
        print(f"Error tracking link click: {e}")
        return jsonify({'error': 'Tracking failed'}), 500




@app.route('/track/view-online/<tracking_id>')
def view_email_online(tracking_id):
    """View email online and track the view"""
    try:
        # Get recipient and campaign info using aggregation
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
            
            # Track this as an email open
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
            
            # Return the email content with a header
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
        else:
            return "Email not found", 404
            
    except Exception as e:
        print(f"Error viewing email online: {e}")
        return f"Error: {str(e)}", 500
    


# NEW: Function to check if email is unsubscribed
def is_email_unsubscribed(email):
    """Check if an email address has unsubscribed"""
    try:
        unsubscribe_record = unsubscribes_collection.find_one({"email": email.lower()})
        return unsubscribe_record is not None
    except Exception as e:
        print(f"Error checking unsubscribe status: {e}")
        return False

# Add this function to record unsubscribe
def record_unsubscribe(email, tracking_id=None, campaign_id=None):
    """Record an unsubscribe"""
    try:
        unsubscribe_data = {
            "email": email.lower(),
            "tracking_id": tracking_id,
            "campaign_id": campaign_id,
            "unsubscribed_at": datetime.now(timezone(timedelta(hours=5, minutes=30))),
            "ip_address": request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr),
            "user_agent": request.headers.get('User-Agent', '')
        }
        
        # Use upsert to avoid duplicates
        unsubscribes_collection.update_one(
            {"email": email.lower()},
            {"$set": unsubscribe_data},
            upsert=True
        )
        
        print(f"🚫 UNSUBSCRIBED: {email} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Emit real-time update if using SocketIO
        try:
            socketio.emit('email_unsubscribed', {
                'email': email,
                'tracking_id': tracking_id,
                'campaign_id': campaign_id,
                'timestamp': datetime.now().isoformat()
            })
        except:
            pass  # SocketIO might not be connected
            
        return True
    except Exception as e:
        print(f"Error recording unsubscribe: {e}")
        return False
    

# NEW: Unsubscribe route
@app.route('/unsubscribe/<tracking_id>')
def unsubscribe_email(tracking_id):
    """Handle email unsubscribe requests"""
    try:
        # Get recipient info from tracking ID
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
            '''), 404
        
        email = recipient.get("email")
        name = recipient.get("name")
        campaign_id = recipient.get("campaign_id")
        
        # Check if already unsubscribed
        if is_email_unsubscribed(email):
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
        
        # Show unsubscribe confirmation page
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
                
                <form method="POST" action="{{ url_for('confirm_unsubscribe', tracking_id=tracking_id) }}" style="display: inline;">
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

@app.route('/unsubscribe/<tracking_id>', methods=['POST'])
def confirm_unsubscribe(tracking_id):
    """Confirm and process unsubscribe"""
    try:
        # Get recipient info from tracking ID
        recipient = recipients_collection.find_one({"tracking_id": tracking_id})
        
        if not recipient:
            return "Invalid unsubscribe request", 404
        
        email = recipient.get("email")
        name = recipient.get("name")
        campaign_id = recipient.get("campaign_id")
        
        # Record the unsubscribe
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
        else:
            return "Error processing unsubscribe", 500
            
    except Exception as e:
        print(f"Error confirming unsubscribe: {e}")
        return "Error processing unsubscribe request", 500


#  UPDATE the analytics function to include unsubscribe data

@app.route('/api/analytics/campaign/<campaign_id>')
def get_campaign_analytics(campaign_id):
    """Get analytics for a specific campaign including unsubscribe and reply data"""
    try:
        # First check for new replies
        check_response = check_campaign_replies(campaign_id)
        
        campaign = campaigns_collection.find_one({"id": campaign_id})
        
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Get recipients count
        total_sent = recipients_collection.count_documents({"campaign_id": campaign_id})
        
        # Get recipient tracking IDs for this campaign
        recipient_tracking_ids = [r["tracking_id"] for r in recipients_collection.find({"campaign_id": campaign_id}, {"tracking_id": 1})]
        recipient_emails = [r["email"] for r in recipients_collection.find({"campaign_id": campaign_id}, {"email": 1})]
        
        # Get unique opens count
        unique_opens_pipeline = [
            {"$match": {"tracking_id": {"$in": recipient_tracking_ids}}},
            {"$group": {"_id": "$tracking_id"}},
            {"$count": "unique_opens"}
        ]
        unique_opens_result = list(email_opens_collection.aggregate(unique_opens_pipeline))
        unique_opens = unique_opens_result[0]["unique_opens"] if unique_opens_result else 0
        
        # Get total opens count
        total_opens = email_opens_collection.count_documents({
            "tracking_id": {"$in": recipient_tracking_ids}
        })
        
        # Get unique clicks count
        unique_clicks_pipeline = [
            {"$match": {"tracking_id": {"$in": recipient_tracking_ids}}},
            {"$group": {"_id": "$tracking_id"}},
            {"$count": "unique_clicks"}
        ]
        unique_clicks_result = list(link_clicks_collection.aggregate(unique_clicks_pipeline))
        unique_clicks = unique_clicks_result[0]["unique_clicks"] if unique_clicks_result else 0
        
        # Get total clicks count
        total_clicks = link_clicks_collection.count_documents({
            "tracking_id": {"$in": recipient_tracking_ids}
        })
        
        # GET UNSUBSCRIBE DATA
        unsubscribe_count = unsubscribes_collection.count_documents({
            "email": {"$in": recipient_emails}
        })
        
        # Get unsubscribe details
        unsubscribe_details = list(unsubscribes_collection.find(
            {"email": {"$in": recipient_emails}},
            {"email": 1, "unsubscribed_at": 1, "tracking_id": 1}
        ))
        
        # GET REPLY DATA
        reply_count = replies_collection.count_documents({
            "campaign_id": campaign_id
        })
        
        # Get reply details
        reply_details = list(replies_collection.find(
            {"campaign_id": campaign_id},
            {"sender_email": 1, "sender_name": 1, "subject": 1, "received_at": 1, "tracking_id": 1, "body_content": 1}
        ).sort("received_at", -1))
        
        # Get unique reply count (unique recipients who replied)
        unique_reply_pipeline = [
            {"$match": {"campaign_id": campaign_id}},
            {"$group": {"_id": "$sender_email"}},
            {"$count": "unique_replies"}
        ]
        unique_reply_result = list(replies_collection.aggregate(unique_reply_pipeline))
        unique_replies = unique_reply_result[0]["unique_replies"] if unique_reply_result else 0
        
        # Get detailed recipient data
        recipients_data = []
        for recipient in recipients_collection.find({"campaign_id": campaign_id}):
            tracking_id = recipient["tracking_id"]
            email = recipient["email"]
            opens_count = email_opens_collection.count_documents({"tracking_id": tracking_id})
            clicks_count = link_clicks_collection.count_documents({"tracking_id": tracking_id})
            replies_count = replies_collection.count_documents({"tracking_id": tracking_id})
            
            first_open = email_opens_collection.find_one(
                {"tracking_id": tracking_id},
                sort=[("opened_at", 1)]
            )
            first_open_time = first_open["opened_at"] if first_open else None
            
            # Check if this recipient unsubscribed
            unsubscribe_info = unsubscribes_collection.find_one({"email": email})
            is_unsubscribed = unsubscribe_info is not None
            unsubscribe_date = unsubscribe_info["unsubscribed_at"] if unsubscribe_info else None
            
            # Check if this recipient replied
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
                'unsubscribed': is_unsubscribed,
                'unsubscribe_date': unsubscribe_date if unsubscribe_date else None,
                'replied': has_replied,
                'reply_date': reply_date if reply_date else None
            })
            
        # Calculate rates
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

@app.route('/api/analytics/all-campaigns')
def get_all_campaigns_analytics():
    """Get analytics summary for all campaigns"""
    try:
        campaigns_data = []
        
        for campaign in campaigns_collection.find().sort("created_at", -1):
            campaign_id = campaign["id"]
            total_recipients = campaign.get("total_recipients", 0)
            
            # Get unique opens for this campaign
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
    
# Add API route to get all unsubscribed emails
@app.route('/api/unsubscribes')
def get_all_unsubscribes():
    """Get all unsubscribed emails"""
    try:
        unsubscribes = list(unsubscribes_collection.find(
            {},
            {"_id": 0, "email": 1, "unsubscribed_at": 1, "campaign_id": 1, "tracking_id": 1}
        ).sort("unsubscribed_at", -1))
        
        # Convert datetime to ISO format
        for unsub in unsubscribes:
            if 'unsubscribed_at' in unsub:
                unsub['unsubscribed_at'] = unsub['unsubscribed_at'].isoformat()
        
        return jsonify({
            'total_unsubscribes': len(unsubscribes),
            'unsubscribes': unsubscribes
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def make_graph_request(endpoint, access_token, method='GET', data=None):
    """Make a request to Microsoft Graph API"""
    url = f"{GRAPH_ENDPOINT}{endpoint}"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    if method == 'GET':
        response = requests.get(url, headers=headers)
    elif method == 'POST':
        response = requests.post(url, headers=headers, json=data)
    
    # Handle successful responses
    if response.status_code in [200, 202]:
        # Check if response has content before trying to parse JSON
        if response.text.strip():
            try:
                return response.json()
            except ValueError:
                # If JSON parsing fails, return the text
                return response.text
        else:
            # Empty response (common for POST operations like sending email)
            return {'success': True, 'status_code': response.status_code}
    else:
        # Return error response text for debugging
        return response.text
    


@app.route('/')
def index():
    return redirect('/app')

@app.route('/app')
def main_app():
    return render_template("frontend.html")

@app.route('/signin')
def signin():
    """Redirect to Microsoft OAuth2 authorization"""
    auth_url = get_auth_url()
    return redirect(auth_url)

@app.route('/callback')
def oauth_callback():
    """Handle OAuth2 callback"""
    if 'code' not in request.args:
        # If no code, redirect to app
        return redirect(url_for('main_app'))
    
    auth_code = request.args.get('code')
    token_response = get_access_token(auth_code)
    # global ACCESS_TOKEN 
    
    if token_response and 'access_token' in token_response:
        # Store the access token in session
        session['access_token'] = token_response['access_token']
        # ACCESS_TOKEN = token_response['access_token']
        # print("access token :",ACCESS_TOKEN)
        # Get user profile information
        try:
            user_profile = make_graph_request('/me', token_response['access_token'])
            session['user_profile'] = user_profile
            print(f"User signed in: {user_profile.get('displayName', 'Unknown')} ({user_profile.get('mail', user_profile.get('userPrincipalName', 'Unknown'))})")
        except Exception as error:
            print(f"Error getting user profile: {error}")
        
        # Redirect to app with success
        return redirect(url_for('main_app', auth='success'))
    else:
        print(f"Token acquisition error: {token_response}")
        return redirect(url_for('main_app', auth='error'))

@app.route('/get-user-profile')
def get_user_profile():
    """Get user profile information"""
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

@app.route('/get-mails/<int:num>')
def get_mails(num):
    """Get recent emails"""
    try:
        access_token = session.get('access_token')
        
        if not access_token:
            return "User not authenticated. Please sign in first.", 401
        
        messages = make_graph_request(f'/me/messages?$top={num}', access_token)
        return jsonify(messages)
    
    except Exception as error:
        print(f"Error fetching messages: {error}")
        return str(error), 500



def process_dataframe(df):
    """Process pandas DataFrame to extract name and email columns"""
    recipients = []
    
    # Normalize column names
    df.columns = df.columns.str.strip().str.lower()
    
    # Find name and email columns
    name_column = None
    email_column = None
    
    # Look for name columns
    name_patterns = ['name', 'full_name', 'fullname', 'first_name', 'firstname', 'recipient', 'contact']
    for col in df.columns:
        if any(pattern in col for pattern in name_patterns):
            name_column = col
            break
    
    # Look for email columns
    email_patterns = ['email', 'e-mail', 'mail', 'email_address', 'emailaddress']
    for col in df.columns:
        if any(pattern in col for pattern in email_patterns):
            email_column = col
            break
    
    # Fallback column detection
    if not email_column:
        for col in df.columns:
            if df[col].astype(str).str.contains('@').any():
                email_column = col
                break
        if not email_column and len(df.columns) >= 1:
            email_column = df.columns[-1]
    
    if not name_column and len(df.columns) >= 2:
        for col in df.columns:
            if col != email_column:
                name_column = col
                break
    
    if not email_column:
        raise ValueError("Could not find email column in the file.")
    
    # Extract recipient data
    for index, row in df.iterrows():
        try:
            email = str(row[email_column]).strip() if pd.notna(row[email_column]) else ''
            name = str(row[name_column]).strip() if name_column and pd.notna(row[name_column]) else ''
            
            if email and '@' in email:
                if not name or name.lower() in ['nan', 'none', '']:
                    name = email.split('@')[0]
                
                recipients.append({
                    'name': name,
                    'email': email.lower()
                })
        except Exception as e:
            print(f"Error processing row {index}: {e}")
            continue
    
    if not recipients:
        raise ValueError("No valid email addresses found in the file.")
    
    return recipients



def parse_email_addresses(text):
    """Extract email addresses from text"""
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.findall(pattern, text)

def process_uploaded_file(file):
    """Process uploaded file and extract recipient data"""
    filename = secure_filename(file.filename)
    file_extension = filename.lower().split('.')[-1]
    
    recipients = []
    
    try:
        if file_extension in ['xlsx', 'xls']:
            df = pd.read_excel(file.stream)
            recipients = process_dataframe(df)
        elif file_extension == 'csv':
            file.stream.seek(0)
            df = pd.read_csv(file.stream)
            recipients = process_dataframe(df)
        elif file_extension == 'txt':
            file.stream.seek(0)
            content = file.stream.read().decode('utf-8')
            emails = parse_email_addresses(content)
            recipients = [{'name': email.split('@')[0], 'email': email} for email in emails]
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
            
    except Exception as e:
        raise Exception(f"Error processing {file_extension.upper()} file: {str(e)}")
    
    return recipients

def validate_email(email):
    """Validate email address format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

@app.route('/send-mail', methods=['POST'])
def send_mail():
    """Send personalized emails to multiple recipients via Outlook with tracking and unsubscribe checking"""
    try:
        # Authentication check
#         return jsonify({
#   "analytics_url": "https://6166-106-222-215-102.ngrok-free.app/api/analytics/campaign/a92e2697-aca1-400a-ba54-e121a5f87a8e", 
#   "campaign_id": "a92e2697-aca1-400a-ba54-e121a5f87a8e", 
#   "sent_count": 3, 
#   "success": True, 
#   "total_recipients": 3, 
#   "tracking_data": [
#     {
#       "outlook_id": "outlook_7788aae3-80b1-4a48-9ac1-936526e7afea", 
#       "recipient": "nikita.patidar <nikita.patidar@xaltanalytics.com>", 
#       "status": "sent", 
#       "tracking_id": "7788aae3-80b1-4a48-9ac1-936526e7afea"
#     }, 
#     {
#       "outlook_id": "outlook_ccf73024-26e3-4891-8b0e-5f17cb41615c", 
#       "recipient": "patidarnikita183 <patidarnikita183@gmail.com>", 
#       "status": "sent", 
#       "tracking_id": "ccf73024-26e3-4891-8b0e-5f17cb41615c"
#     }, 
#     {
#       "outlook_id": "outlook_7f40df67-c9db-4ecb-8c2a-de75ed9725da", 
#       "recipient": "tisha.berchha <tisha.berchha@xaltanalytics.com>", 
#       "status": "sent", 
#       "tracking_id": "7f40df67-c9db-4ecb-8c2a-de75ed9725da"
#     }
#   ], 
#   "tracking_enabled": True, 
#   "unsubscribed_count": 0
# }
# )
        access_token = session.get('access_token')
        if not access_token:
            return jsonify({'error': 'User not authenticated. Please sign in first.'}), 401

        # Generate campaign ID
        campaign_id = str(uuid.uuid4())
        
        # Handle both form data and JSON data
        recipients = []
        if request.content_type and 'multipart/form-data' in request.content_type:
            subject = request.form.get('subject')
            message = request.form.get('message')
            recipients_text = request.form.get('recipients_text', '')
            link = request.form.get("link","https://www.microsoft.com")
            
            # Process uploaded file
            if 'recipients_file' in request.files:
                file = request.files['recipients_file']
                if file.filename != '':
                    try:
                        recipients_data = process_uploaded_file(file)
                        recipients.extend(recipients_data)
                    except Exception as e:
                        return jsonify({'error': f'Error processing file: {str(e)}'}), 400
            
            # Process text recipients
            if recipients_text.strip():
                text_recipients = parse_email_addresses(recipients_text)
                recipients.extend([{'name': email.split('@')[0], 'email': email} for email in text_recipients])
                
        else:
            # Handle JSON data
            data = request.json
            subject = data.get('subject')
            message = data.get('message')
            recipients_list = data.get('recipients', [])
            link = data.get("link","https://www.microsoft.com")
            for recipient in recipients_list:
                if isinstance(recipient, str):
                    recipients.append({'name': recipient.split('@')[0], 'email': recipient})
                else:
                    recipients.append(recipient)

        # Validate input
        if not recipients:
            return jsonify({'error': 'No recipients specified'}), 400
        if not subject or not message:
            return jsonify({'error': 'Subject and message are required'}), 400
        
        # Remove duplicates and validate emails
        seen_emails = set()
        valid_recipients = []
        invalid_recipients = []
        unsubscribed_recipients = []
        
        for recipient_data in recipients:
            email = recipient_data.get('email', '').strip().lower()
            name = recipient_data.get('name', '').strip()
            
            if email and email not in seen_emails:
                if validate_email(email):
                    # CHECK IF EMAIL IS UNSUBSCRIBED
                    if is_email_unsubscribed(email):
                        unsubscribed_recipients.append({
                            'name': name or email.split('@')[0], 
                            'email': email
                        })
                        print(f"🚫 Skipping unsubscribed email: {email}")
                    else:
                        valid_recipients.append({
                            'name': name or email.split('@')[0], 
                            'email': email
                        })
                    seen_emails.add(email)
                else:
                    invalid_recipients.append(email)
        
        if not valid_recipients:
            return jsonify({
                'error': 'No valid email addresses found after filtering unsubscribed emails',
                'unsubscribed_count': len(unsubscribed_recipients),
                'unsubscribed_recipients': unsubscribed_recipients
            }), 400

        # Save campaign to database WITH TRACKING
        save_campaign(campaign_id, subject, message, len(valid_recipients))
        
        # Send individual emails with tracking
        sent_count = 0
        failed_recipients = []
        tracking_data = []
        
        for recipient in valid_recipients:
            try:
                recipient_email = recipient['email']
                recipient_name = recipient['name']
                tracking_id = str(uuid.uuid4())
                
                # Create personalized message content
                personalized_message = message.replace('{name}', recipient_name)
                
                # ADD TRACKING TO EMAIL CONTENT (including unsubscribe link)
                personalized_message = personalized_message + link
                tracked_message = add_email_tracking(personalized_message, tracking_id)
                
                # Create email data for Outlook API
                send_mail_data = {
                    "message": {
                        "subject": subject,
                        "body": {
                            "contentType": "HTML",  # Important: Use HTML for tracking
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

                url = f"{GRAPH_ENDPOINT}/me/sendMail"
                headers = {
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json'
                }
                
                response = requests.post(url, headers=headers, json=send_mail_data)
                
                # Check if the request was successful
                if response.status_code == 202:
                    # Save tracking data to database
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
                    # Handle error cases
                    try:
                        error_data = response.json()
                        error_message = error_data.get('error', {}).get('message', 'Unknown error')
                        print(f'❌ Failed to send email to {recipient_email}: {error_message}')
                        failed_recipients.append(f"{recipient_name} <{recipient_email}>: {error_message}")
                    except ValueError:
                        error_message = f'HTTP {response.status_code}: {response.text}'
                        print(f'❌ Failed to send email to {recipient_email}: {error_message}')
                        failed_recipients.append(f"{recipient_name} <{recipient_email}>: {error_message}")
                
                # Add small delay to avoid rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                print(f'❌ Failed to send email to {recipient_email}: {e}')
                failed_recipients.append(f"{recipient_name} <{recipient_email}>: {str(e)}")

        # Prepare response with tracking information
        response_data = {
            'success': True,
            'campaign_id': campaign_id,
            'sent_count': sent_count,
            'total_recipients': len(valid_recipients),
            'unsubscribed_count': len(unsubscribed_recipients),
            'tracking_data': tracking_data,
            'tracking_enabled': True,
            'analytics_url': f'{BASE_URL}/api/analytics/campaign/{campaign_id}'
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
        print(f"📈 View analytics at: {BASE_URL}/api/analytics/campaign/{campaign_id}")
        print("this is send mail response data &&&&&&&&&&&&&&&&&&&\n",response_data)
        return jsonify(response_data)
        
    except Exception as e:
        print(f'❌ Error sending email: {e}')
        return jsonify({'error': f'Failed to send email: {str(e)}'}), 500

@app.route('/send-mail/<recipient>')
def send_mail_single(recipient):
    """Send an email to a single recipient (legacy endpoint)"""
    try:
        print("3")
        access_token = session.get('access_token')
        
        if not access_token:
            # print("access token :",ACCESS_TOKEN)
            # access_token = ACCESS_TOKEN
            return jsonify({'error': 'User not authenticated. Please sign in first.'}), 401
            # return jsonify({'error': 'User not authenticated. Please sign in first.'}), 401
        
        # Get subject and message from query parameters or use defaults
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
        
        # Make the API request
        url = f"{GRAPH_ENDPOINT}/me/sendMail"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.post(url, headers=headers, json=send_mail_data)
        
        # Check if the request was successful
        if response.status_code == 202:
            return jsonify({'success': True, 'message': 'Email sent successfully'})
        else:
            # Handle error cases
            try:
                error_data = response.json()
                return jsonify({'error': error_data.get('error', {}).get('message', 'Unknown error')}), response.status_code
            except ValueError:
                return jsonify({'error': f'HTTP {response.status_code}: {response.text}'}), response.status_code
    
    except Exception as error:
        print(f"Error sending message: {error}")
        return jsonify({'error': str(error)}), 500

# Add these new functions anywhere after the existing functions (around line 400)

# def save_reply_tracking(message_id, campaign_id, tracking_id, sender_email, sender_name, subject, body_content, received_at, thread_id=None):
#     """Save reply tracking data"""
#     try:
#         reply_data = {
#             "message_id": message_id,
#             "campaign_id": campaign_id,
#             "tracking_id": tracking_id,
#             "sender_email": sender_email.lower(),
#             "sender_name": sender_name,
#             "subject": subject,
#             "body_content": body_content[:1000],  # Limit body content to 1000 chars
#             "received_at": received_at,
#             "thread_id": thread_id,
#             "processed_at": datetime.now(timezone(timedelta(hours=5, minutes=30)))
#         }
        
#         replies_collection.update_one(
#             {"message_id": message_id},
#             {"$set": reply_data},
#             upsert=True
#         )
        
#         print(f"💬 REPLY TRACKED: {sender_name} ({sender_email}) - {received_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
#         # Emit real-time update if using SocketIO
#         try:
#             socketio.emit('email_replied', {
#                 'campaign_id': campaign_id,
#                 'tracking_id': tracking_id,
#                 'sender_email': sender_email,
#                 'sender_name': sender_name,
#                 'subject': subject,
#                 'timestamp': received_at.isoformat()
#             })
#         except:
#             pass  # SocketIO might not be connected
            
#         return True
#     except Exception as e:
#         print(f"Error saving reply tracking: {e}")
#         return False
def save_reply_tracking(message_id, campaign_id, tracking_id, sender_email, sender_name, subject, body_content, received_at, thread_id=None):
    """Save reply tracking data for SPECIFIC campaign only"""
    try:
        reply_data = {
            "message_id": message_id,
            "campaign_id": campaign_id,  # Always store the specific campaign ID
            "tracking_id": tracking_id,
            "sender_email": sender_email.lower(),
            "sender_name": sender_name,
            "subject": subject,
            "body_content": body_content[:1000],  # Limit body content to 1000 chars
            "received_at": received_at,
            "thread_id": thread_id,
            "processed_at": datetime.now(timezone(timedelta(hours=5, minutes=30)))
        }
        
        # Use campaign_id + message_id as unique constraint to avoid duplicates
        replies_collection.update_one(
            {
                "message_id": message_id,
                "campaign_id": campaign_id  # Ensure uniqueness per campaign
            },
            {"$set": reply_data},
            upsert=True
        )
        
        print(f"💬 REPLY TRACKED for Campaign {campaign_id}: {sender_name} ({sender_email}) - {received_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Emit real-time update for THIS campaign only
        try:
            socketio.emit('email_replied', {
                'campaign_id': campaign_id,
                'tracking_id': tracking_id,
                'sender_email': sender_email,
                'sender_name': sender_name,
                'subject': subject,
                'timestamp': received_at.isoformat()
            })
        except:
            pass  # SocketIO might not be connected
            
        return True
    except Exception as e:
        print(f"Error saving reply tracking: {e}")
        return False



def extract_tracking_id_from_email(email_content, subject):
    """Extract tracking ID from email content or subject"""
    try:
        # Method 1: Look for tracking ID in email content (from tracking pixels or links)
        tracking_pattern = r'/track/(?:open|click|view-online)/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'
        matches = re.findall(tracking_pattern, email_content, re.IGNORECASE)
        if matches:
            return matches[0]
        
        # Method 2: Look for tracking ID in URLs
        url_pattern = r'https?://[^/]+/track/[^/]+/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'
        matches = re.findall(url_pattern, email_content, re.IGNORECASE)
        if matches:
            return matches[0]
            
        return None
    except Exception as e:
        print(f"Error extracting tracking ID: {e}")
        return None

def find_campaign_by_recipient_email(sender_email):
    """Find campaign ID by matching sender email with recipients"""
    try:
        recipient = recipients_collection.find_one(
            {"email": sender_email.lower()},
            sort=[("sent_at", -1)]  # Get most recent campaign
        )
        
        if recipient:
            return recipient.get("campaign_id"), recipient.get("tracking_id")
        return None, None
    except Exception as e:
        print(f"Error finding campaign by recipient email: {e}")
        return None, None

# Add these new API routes (add around line 800, after the existing routes)

# @app.route('/api/check-replies/<campaign_id>')
# def check_campaign_replies(campaign_id):
#     """Check for replies to a specific campaign by fetching recent emails"""
#     try:
#         access_token = session.get('access_token')
#         if not access_token:
#             return jsonify({'error': 'User not authenticated'}), 401
        
#         # Get campaign recipients
#         recipients = list(recipients_collection.find(
#             {"campaign_id": campaign_id}, 
#             {"email": 1, "tracking_id": 1, "name": 1}
#         ))
        
#         if not recipients:
#             return jsonify({'error': 'Campaign not found'}), 404
        
#         recipient_emails = [r["email"] for r in recipients]
#         new_replies_count = 0
        
#         # Fetch recent emails (last 7 days)
#         seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat() + 'Z'
        
#         try:
#             # Get recent emails from Outlook
#             messages_response = make_graph_request(
#                 f'/me/messages?$filter=receivedDateTime ge {seven_days_ago}&$top=100&$select=id,subject,sender,receivedDateTime,body,conversationId',
#                 access_token
#             )
            
#             if isinstance(messages_response, dict) and 'value' in messages_response:
#                 messages = messages_response['value']
                
#                 for message in messages:
#                     try:
#                         sender_email = message.get('sender', {}).get('emailAddress', {}).get('address', '').lower()
#                         sender_name = message.get('sender', {}).get('emailAddress', {}).get('name', '')
#                         subject = message.get('subject', '')
#                         message_id = message.get('id', '')
#                         received_at = datetime.fromisoformat(message.get('receivedDateTime', '').replace('Z', '+00:00'))
#                         body_content = message.get('body', {}).get('content', '')
#                         thread_id = message.get('conversationId', '')
                        
#                         # Check if sender is one of our campaign recipients
#                         if sender_email in recipient_emails:
#                             # Find the specific recipient data
#                             recipient_data = next((r for r in recipients if r["email"] == sender_email), None)
                            
#                             if recipient_data:
#                                 tracking_id = recipient_data["tracking_id"]
                                
#                                 # Check if this reply is already tracked
#                                 existing_reply = replies_collection.find_one({"message_id": message_id})
                                
#                                 if not existing_reply:
#                                     # Save the reply
#                                     if save_reply_tracking(
#                                         message_id, campaign_id, tracking_id, 
#                                         sender_email, sender_name, subject, 
#                                         body_content, received_at, thread_id
#                                     ):
#                                         new_replies_count += 1
                                        
#                     except Exception as e:
#                         print(f"Error processing message: {e}")
#                         continue
                        
#         except Exception as e:
#             print(f"Error fetching messages from Outlook: {e}")
#             return jsonify({'error': 'Failed to fetch emails from Outlook'}), 500
        
#         return jsonify({
#             'campaign_id': campaign_id,
#             'new_replies_found': new_replies_count,
#             'total_recipients_checked': len(recipient_emails),
#             'status': 'success'
#         })
        
#     except Exception as e:
#         print(f"Error checking campaign replies: {e}")
#         return jsonify({'error': str(e)}), 500

@app.route('/api/check-replies/<campaign_id>')
def check_campaign_replies(campaign_id):
    """Check for replies ONLY to the specified campaign"""
    try:
        access_token = session.get('access_token')
        if not access_token:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Get ONLY the current campaign recipients
        recipients = list(recipients_collection.find(
            {"campaign_id": campaign_id}, 
            {"email": 1, "tracking_id": 1, "name": 1, "sent_at": 1}
        ))
        
        if not recipients:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Get the campaign start time to filter replies only after campaign was sent
        campaign = campaigns_collection.find_one({"id": campaign_id})
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
            
        campaign_start_time = campaign.get('created_at')
        if not campaign_start_time:
            # If no campaign start time, use the earliest recipient sent time
            earliest_sent = recipients_collection.find_one(
                {"campaign_id": campaign_id}, 
                sort=[("sent_at", 1)]
            )
            campaign_start_time = earliest_sent.get('sent_at') if earliest_sent else datetime.now() - timedelta(hours=24)
        
        recipient_emails = [r["email"] for r in recipients]
        new_replies_count = 0
        
        # Only check emails received AFTER the campaign was sent
        campaign_start_iso = campaign_start_time.isoformat() + 'Z' if isinstance(campaign_start_time, datetime) else campaign_start_time
        
        try:
            # Get emails received ONLY after this campaign was sent
            messages_response = make_graph_request(
                f'/me/messages?$filter=receivedDateTime ge {campaign_start_iso}&$top=50&$select=id,subject,sender,receivedDateTime,body,conversationId',
                access_token
            )
            
            if isinstance(messages_response, dict) and 'value' in messages_response:
                messages = messages_response['value']
                
                for message in messages:
                    try:
                        sender_email = message.get('sender', {}).get('emailAddress', {}).get('address', '').lower()
                        
                        # ONLY process if sender is from THIS campaign
                        if sender_email in recipient_emails:
                            sender_name = message.get('sender', {}).get('emailAddress', {}).get('name', '')
                            subject = message.get('subject', '')
                            message_id = message.get('id', '')
                            received_at = datetime.fromisoformat(message.get('receivedDateTime', '').replace('Z', '+00:00'))
                            body_content = message.get('body', {}).get('content', '')
                            thread_id = message.get('conversationId', '')
                            
                            # Find the specific recipient data for THIS campaign
                            recipient_data = next((r for r in recipients if r["email"] == sender_email), None)
                            
                            if recipient_data:
                                tracking_id = recipient_data["tracking_id"]
                                
                                # Check if this reply is already tracked
                                existing_reply = replies_collection.find_one({
                                    "message_id": message_id,
                                    "campaign_id": campaign_id  # Ensure it's for THIS campaign
                                })
                                
                                if not existing_reply:
                                    # Save the reply ONLY for this campaign
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


# @app.route('/api/replies/<campaign_id>')
# def get_campaign_replies(campaign_id):
#     """Get all replies for a specific campaign"""
#     try:
#         replies = list(replies_collection.find(
#             {"campaign_id": campaign_id},
#             {"_id": 0}
#         ).sort("received_at", -1))
        
#         # Convert datetime to ISO format
#         for reply in replies:
#             if 'received_at' in reply:
#                 reply['received_at'] = reply['received_at'].isoformat()
#             if 'processed_at' in reply:
#                 reply['processed_at'] = reply['processed_at'].isoformat()
        
#         return jsonify({
#             'campaign_id': campaign_id,
#             'total_replies': len(replies),
#             'replies': replies
#         })
        
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500
@app.route('/api/replies/<campaign_id>')
def get_campaign_replies(campaign_id):
    """Get replies ONLY for the specified campaign"""
    try:
        # Get replies ONLY for this specific campaign
        replies = list(replies_collection.find(
            {"campaign_id": campaign_id},  # Only this campaign
            {"_id": 0}
        ).sort("received_at", -1))
        
        # Convert datetime to ISO format
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


@app.route('/api/replies/all')
def get_all_replies():
    """Get all replies across all campaigns"""
    try:
        replies = list(replies_collection.find({}, {"_id": 0}).sort("received_at", -1))
        
        # Convert datetime to ISO format
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

def check_current_campaign_replies(campaign_id):
    """Quick check for new replies during campaign sending"""
    try:
        # Get count of replies for this campaign
        current_reply_count = replies_collection.count_documents({
            "campaign_id": campaign_id
        })
        
        # Check for new replies (this will fetch and save any new ones)
        check_response = check_campaign_replies(campaign_id)
        
        # Get updated count
        updated_reply_count = replies_collection.count_documents({
            "campaign_id": campaign_id
        })
        
        new_replies = updated_reply_count - current_reply_count
        
        if new_replies > 0:
            print(f"🔔 {new_replies} new replies found for campaign {campaign_id}")
            
        return {
            'campaign_id': campaign_id,
            'new_replies': new_replies,
            'total_replies': updated_reply_count
        }
        
    except Exception as e:
        print(f"Error checking current campaign replies: {e}")
        return {'error': str(e)}

if __name__ == '__main__':
    # Initialize database when the app starts
    init_tracking_db()
    print(f"App listening on port {PORT}")
    print(f"Frontend available at: http://localhost:{PORT}/app")
    app.run(host="0.0.0.0" ,debug=True, port=PORT)

