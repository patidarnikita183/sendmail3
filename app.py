from flask import Flask, request, redirect, url_for, session, jsonify, render_template,Response
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

load_dotenv()  
# import urllib.parse
app = Flask(__name__)
app.secret_key = 'any_secret_key'  


MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL,tls=True)
db = client["email_tracking"]

# Collections
campaigns_collection = db["campaigns"]
recipients_collection = db["recipients"]
email_opens_collection = db["email_opens"]
link_clicks_collection = db["link_clicks"]

# Configuration
CLIENT_ID =os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TENANT_ID =os.getenv("TENANT_ID")
PORT = os.getenv("PORT")
REDIRECT_URI = os.getenv("REDIRECT_URI")
# REDIRECT_URI = f"https://8d6e-106-222-213-67.ngrok-free.app:{PORT}/callback"
BASE_URL = os.getenv("BASE_URL")

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


# Add SocketIO support after your app initialization
socketio = SocketIO(app, cors_allowed_origins="*")

# Add your BASE_URL configuration (update with your actual domain/ngrok URL)
# BASE_URL = "http://localhost:9000"  # Update this with your actual domain or ngrok URL
# BASE_URL =  "https://a31a-2401-4900-8821-dad7-3d1e-864e-454a-65e0.ngrok-free.app"
# Database initialization function
def init_tracking_db():
    """Initialize tracking database with indexes"""
    try:
        # Create indexes for better performance
        campaigns_collection.create_index("id", unique=True)
        recipients_collection.create_index("tracking_id", unique=True)
        recipients_collection.create_index("campaign_id")
        email_opens_collection.create_index("tracking_id")
        link_clicks_collection.create_index("tracking_id")
        
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
            "created_at":  datetime.now(timezone.utc),
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
            "sent_at": datetime.now(timezone.utc),
            "delivery_status": "sent"
        }
        
        recipients_collection.insert_one(recipient_data)
        
    except Exception as e:
        print(f"Error saving email tracking: {e}")

# Function to add tracking to email content
def add_email_tracking(content, tracking_id):
    """Add tracking pixel and link tracking to email content"""
    
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

    # Insert tracking elements
    if '<body' in tracked_content:
        body_start = tracked_content.find('>', tracked_content.find('<body'))
        if body_start != -1:
            tracked_content = (tracked_content[:body_start+1] + 
                             tracking_pixel + css_tracker + view_online + 
                             tracked_content[body_start+1:])
    else:
        tracked_content = tracking_pixel + css_tracker + view_online + tracked_content
    
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
                "opened_at": datetime.now(timezone.utc),
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
                "clicked_at": datetime.now(timezone.utc),
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
                "opened_at": datetime.now(timezone.utc),
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

# Analytics routes
@app.route('/api/analytics/campaign/<campaign_id>')
def get_campaign_analytics(campaign_id):
    """Get analytics for a specific campaign"""
    try:
        # Get campaign info
        campaign = campaigns_collection.find_one({"id": campaign_id})
        
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Get recipients count
        total_sent = recipients_collection.count_documents({"campaign_id": campaign_id})
        
        # Get unique opens count
        unique_opens_pipeline = [
            {"$match": {"tracking_id": {"$in": [r["tracking_id"] for r in recipients_collection.find({"campaign_id": campaign_id}, {"tracking_id": 1})]}}},
            {"$group": {"_id": "$tracking_id"}},
            {"$count": "unique_opens"}
        ]
        unique_opens_result = list(email_opens_collection.aggregate(unique_opens_pipeline))
        unique_opens = unique_opens_result[0]["unique_opens"] if unique_opens_result else 0
        
        # Get total opens count
        total_opens = email_opens_collection.count_documents({
            "tracking_id": {"$in": [r["tracking_id"] for r in recipients_collection.find({"campaign_id": campaign_id}, {"tracking_id": 1})]}
        })
        
        # Get unique clicks count
        unique_clicks_pipeline = [
            {"$match": {"tracking_id": {"$in": [r["tracking_id"] for r in recipients_collection.find({"campaign_id": campaign_id}, {"tracking_id": 1})]}}},
            {"$group": {"_id": "$tracking_id"}},
            {"$count": "unique_clicks"}
        ]
        unique_clicks_result = list(link_clicks_collection.aggregate(unique_clicks_pipeline))
        unique_clicks = unique_clicks_result[0]["unique_clicks"] if unique_clicks_result else 0
        
        # Get total clicks count
        total_clicks = link_clicks_collection.count_documents({
            "tracking_id": {"$in": [r["tracking_id"] for r in recipients_collection.find({"campaign_id": campaign_id}, {"tracking_id": 1})]}
        })
        
        # Get detailed recipient data
        recipients_data = []
        for recipient in recipients_collection.find({"campaign_id": campaign_id}):
            tracking_id = recipient["tracking_id"]
            opens_count = email_opens_collection.count_documents({"tracking_id": tracking_id})
            clicks_count = link_clicks_collection.count_documents({"tracking_id": tracking_id})
            
            first_open = email_opens_collection.find_one(
                {"tracking_id": tracking_id},
                sort=[("opened_at", 1)]
            )
            first_open_time = first_open["opened_at"] if first_open else None
            
            recipients_data.append({
                'email': recipient["email"],
                'name': recipient["name"],
                'tracking_id': tracking_id,
                'opens': opens_count,
                'clicks': clicks_count,
                'first_open': first_open_time.isoformat() if first_open_time else None
            })
        
        # Calculate rates
        open_rate = (unique_opens / total_sent * 100) if total_sent > 0 else 0
        click_rate = (unique_clicks / total_sent * 100) if total_sent > 0 else 0
        click_to_open_rate = (unique_clicks / unique_opens * 100) if unique_opens > 0 else 0
        
        return jsonify({
            'campaign_id': campaign_id,
            'campaign_name': campaign.get("name"),
            'subject': campaign.get("subject"),
            'total_sent': total_sent,
            'unique_opens': unique_opens,
            'total_opens': total_opens,
            'unique_clicks': unique_clicks,
            'total_clicks': total_clicks,
            'open_rate': round(open_rate, 2),
            'click_rate': round(click_rate, 2),
            'click_to_open_rate': round(click_to_open_rate, 2),
            'recipients': recipients_data
        })
        
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
    """Send personalized emails to multiple recipients via Outlook with tracking"""
    try:
        # Authentication check
        global ACCESS_TOKEN
        access_token = session.get('access_token')
        if not access_token:
            # access_token = ACCESS_TOKEN
            # if not access_token:
            return jsonify({'error': 'User not authenticated. Please sign in first.'}), 401
        # access_token = """"""
        print("1")
        # Generate campaign ID
        campaign_id = str(uuid.uuid4())
        
        # Handle both form data and JSON data
        recipients = []
        if request.content_type and 'multipart/form-data' in request.content_type:
            print("11")
            subject = request.form.get('subject')
            print("111")
            message = request.form.get('message')
            print("1111")
            recipients_text = request.form.get('recipients_text', '')
            print("11111")
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
            print("2")
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
            
        # Save campaign to database WITH TRACKING
        save_campaign(campaign_id, subject, message, len(recipients))
        
        # Remove duplicates and validate emails
        seen_emails = set()
        valid_recipients = []
        invalid_recipients = []
        
        for recipient_data in recipients:
            email = recipient_data.get('email', '').strip().lower()
            name = recipient_data.get('name', '').strip()
            
            if email and email not in seen_emails:
                if validate_email(email):
                    valid_recipients.append({
                        'name': name or email.split('@')[0], 
                        'email': email
                    })
                    seen_emails.add(email)
                else:
                    invalid_recipients.append(email)
        
        if not valid_recipients:
            return jsonify({'error': 'No valid email addresses found'}), 400

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
                
                # ADD TRACKING TO EMAIL CONTENT
                personalized_message = personalized_message + link
                tracked_message = add_email_tracking(personalized_message, tracking_id)
                # return jsonify({"res":tracked_message})
                # Create email data for Outlook API
                send_mail_data = {
                    "message": {
                        "subject": subject,
                        "body": {
                            "contentType": "HTML",  # Important: Use HTML for tracking
                            "content": f"""
                                {tracked_message}
                            """  # Make sure this is a string, not raw HTML code
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
            'tracking_data': tracking_data,
            'tracking_enabled': True,
            'analytics_url': f'{BASE_URL}/api/analytics/campaign/{campaign_id}'
        }
        
        if invalid_recipients:
            response_data['invalid_recipients'] = invalid_recipients
            
        if failed_recipients:
            response_data['failed_recipients'] = failed_recipients
        
        print(f"📊 Campaign {campaign_id} sent with tracking enabled!")
        print(f"📈 View analytics at: {BASE_URL}/api/analytics/campaign/{campaign_id}")
            
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
    
if __name__ == '__main__':
    # Initialize database when the app starts
    init_tracking_db()
    print(f"App listening on port {PORT}")
    print(f"Frontend available at: http://localhost:{PORT}/app")
    app.run(host="0.0.0.0" ,debug=True, port=PORT)

