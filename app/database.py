from pymongo import MongoClient
from datetime import datetime, timezone, timedelta
from .config import Config

client = MongoClient(Config.MONGO_URL, tls=True)
db = client["email_tracking"]

# Collections
campaigns_collection = db["campaigns"]
recipients_collection = db["recipients"]
email_opens_collection = db["email_opens"]
link_clicks_collection = db["link_clicks"]
unsubscribes_collection = db["unsubscribes"]
replies_collection = db["replies"]
senders_collection = db["senders"]

def init_tracking_db():
    """Initialize tracking database with indexes"""
    try:
        campaigns_collection.create_index("id", unique=True)
        recipients_collection.create_index("tracking_id", unique=True)
        recipients_collection.create_index("campaign_id")
        email_opens_collection.create_index("tracking_id")
        link_clicks_collection.create_index("tracking_id")
        unsubscribes_collection.create_index([("email", 1), ("sender_email", 1)], unique=True)
        unsubscribes_collection.create_index("sender_email")
        unsubscribes_collection.create_index("tracking_id")
        unsubscribes_collection.create_index("unsubscribed_at")
        replies_collection.create_index([("campaign_id", 1), ("message_id", 1)], unique=True)
        replies_collection.create_index("campaign_id")
        replies_collection.create_index("tracking_id")
        replies_collection.create_index("sender_email")
        replies_collection.create_index("received_at")
        senders_collection.create_index("email", unique=True)
        senders_collection.create_index("campaign_id")
        senders_collection.create_index("created_at")
        
        print("✅ Campaign-specific replies MongoDB database initialized")
        print("✅ Email tracking MongoDB database initialized")
    except Exception as e:
        print(f"Error initializing database: {e}")

def save_sender_info(email, name, campaign_id):
    """Save sender information with campaign ID"""
    try:
        sender_data = {
            "email": email.lower(),
            "name": name,
            "campaign_id": campaign_id,
            "created_at": datetime.now(timezone(timedelta(hours=5, minutes=30))),
            "last_updated": datetime.now(timezone(timedelta(hours=5, minutes=30)))
        }
        senders_collection.update_one(
            {"email": email.lower()},
            {"$set": sender_data},
            upsert=True
        )
        print(f"📝 SENDER SAVED: {name} ({email}) - Campaign: {campaign_id}")
        return True
    except Exception as e:
        print(f"Error saving sender info: {e}")
        return False

def save_campaign(campaign_id, subject, message, total_recipients, sender_email):
    """Save campaign to database"""
    try:
        campaign_data = {
            "id": campaign_id,
            "name": f"Campaign {campaign_id}",
            "subject": subject,
            "content": message,
            "status": "sending",
            "created_at": datetime.now(timezone(timedelta(hours=5, minutes=30))),
            "sent_at": None,
            "total_recipients": total_recipients,
            "sender_email": sender_email
        }
        campaigns_collection.update_one(
            {"id": campaign_id},
            {"$set": campaign_data},
            upsert=True
        )
    except Exception as e:
        print(f"Error saving campaign: {e}")

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