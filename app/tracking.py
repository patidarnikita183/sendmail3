import re
import base64
from flask import request, Response, render_template_string, jsonify, redirect
from datetime import datetime, timezone, timedelta
from .config import Config
from .database import (
    recipients_collection, email_opens_collection, link_clicks_collection,
    unsubscribes_collection, replies_collection, campaigns_collection
)
from urllib.parse import quote, unquote

def add_email_tracking(content, tracking_id):
    """Add tracking pixel, link tracking, and unsubscribe link to email content"""
    tracking_pixel = f'<img src="{Config.BASE_URL}/track/open/{tracking_id}" width="1" height="1" style="display:none;" alt="" border="0">'
    css_tracker = f'<div style="background:url(\'{Config.BASE_URL}/track/open/{tracking_id}\') no-repeat;width:1px;height:1px;display:none;"></div>'
    view_online = f'''
    <div style="text-align: center; padding: 10px; background: #f8f9fa; margin: 10px 0; border-radius: 5px; font-size: 12px;">
        <a href="{Config.BASE_URL}/track/view-online/{tracking_id}" style="color: #6c757d; text-decoration: none;">
            📱 View this email in your browser
        </a>
    </div>
    '''
    unsubscribe_link = f'''
    <div style="text-align: center; padding: 15px; background: #f8f9fa; margin: 20px 0; border-radius: 5px; border-top: 1px solid #dee2e6;">
        <p style="margin: 0; font-size: 12px; color: #6c757d;">
            Don't want to receive these emails? 
            <a href="{Config.BASE_URL}/unsubscribe/{tracking_id}" style="color: #dc3545; text-decoration: none;">
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
        if original_url.startswith('http') and Config.BASE_URL not in original_url:
            tracking_url = f"{Config.BASE_URL}/track/click/{tracking_id}/{quote(original_url, safe='')}"
            return f"""<br><br>
                    <a href={tracking_url} style="display: inline-block; background: #00bcf2; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 5px;">
                        🔗 {tracking_url}
                    </a>"""
        return original_url

    tracked_content = re.sub(r'https?://[^\s]+', replace_link, content)
    
    if '<body' in tracked_content:
        body_end = tracked_content.rfind('</body>')
        if body_end != -1:
            tracked_content = tracked_content[:body_end] + unsubscribe_link + tracked_content[body_end:]
        body_start = tracked_content.find('>', tracked_content.find('<body'))
        if body_start != -1:
            tracked_content = tracked_content[:body_start+1] + tracking_pixel + css_tracker + view_online + tracked_content[body_start+1:]
    else:
        tracked_content = tracking_pixel + css_tracker + view_online + tracked_content + unsubscribe_link
    
    return tracked_content

def is_email_unsubscribed(email, sender_email):
    """Check if an email address has unsubscribed from a specific client"""
    try:
        unsubscribe_record = unsubscribes_collection.find_one({
            "email": email.lower(),
            "sender_email": sender_email.lower()
        })
        return unsubscribe_record is not None
    except Exception as e:
        print(f"Error checking unsubscribe status: {e}")
        return False

def record_unsubscribe(email, tracking_id, campaign_id):
    """Record an unsubscribe"""
    try:
        campaign = campaigns_collection.find_one({"id": campaign_id})
        if not campaign:
            return False
        sender_email = campaign.get("sender_email", "hello@123").lower()
        
        unsubscribe_data = {
            "email": email.lower(),
            "sender_email": sender_email,
            "tracking_id": tracking_id,
            "campaign_id": campaign_id,
            "unsubscribed_at": datetime.now(timezone(timedelta(hours=5, minutes=30))),
            "ip_address": request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr),
            "user_agent": request.headers.get('User-Agent', '')
        }
        
        unsubscribes_collection.update_one(
            {"email": email.lower(), "sender_email": sender_email},
            {"$set": unsubscribe_data},
            upsert=True
        )
        
        print(f"🚫 UNSUBSCRIBED: {email} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return True
    except Exception as e:
        print(f"Error recording unsubscribe: {e}")
        return False

def save_reply_tracking(message_id, campaign_id, tracking_id, sender_email, sender_name, subject, body_content, received_at, thread_id=None):
    """Save reply tracking data for SPECIFIC campaign only"""
    try:
        reply_data = {
            "message_id": message_id,
            "campaign_id": campaign_id,
            "tracking_id": tracking_id,
            "sender_email": sender_email.lower(),
            "sender_name": sender_name,
            "subject": subject,
            "body_content": body_content[:1000],
            "received_at": received_at,
            "thread_id": thread_id,
            "processed_at": datetime.now(timezone(timedelta(hours=5, minutes=30)))
        }
        
        replies_collection.update_one(
            {"message_id": message_id, "campaign_id": campaign_id},
            {"$set": reply_data},
            upsert=True
        )
        
        print(f"💬 REPLY TRACKED for Campaign {campaign_id}: {sender_name} ({sender_email}) - {received_at.strftime('%Y-%m-%d %H:%M:%S')}")
        return True
    except Exception as e:
        print(f"Error saving reply tracking: {e}")
        return False

def extract_tracking_id_from_email(email_content, subject):
    """Extract tracking ID from email content or subject"""
    try:
        tracking_pattern = r'/track/(?:open|click|view-online)/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'
        matches = re.findall(tracking_pattern, email_content, re.IGNORECASE)
        if matches:
            return matches[0]
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
            sort=[("sent_at", -1)]
        )
        if recipient:
            return recipient.get("campaign_id"), recipient.get("tracking_id")
        return None, None
    except Exception as e:
        print(f"Error finding campaign by recipient email: {e}")
        return None, None