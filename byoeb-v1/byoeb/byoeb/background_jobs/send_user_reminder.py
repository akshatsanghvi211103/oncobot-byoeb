#!/usr/bin/env python3
"""
User Reminder System

This script sends reminders to users on Tuesdays and Fridays at 11 AM.
Active users (last activity within 24 hours) get text messages.
Inactive users get template messages.

The script is designed to be run by the background job scheduler.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta

# Add project root to path (same as expert reminder)
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# Import required modules (same as expert reminder)
from byoeb.chat_app.configuration.config import app_config
from byoeb.factory import MongoDBFactory
from byoeb.services.databases.mongo_db import UserMongoDBService
from byoeb.services.channel.qikchat import QikchatService
from byoeb_core.models.byoeb.message_context import ByoebMessageContext, MessageContext, User, MessageTypes
from byoeb.models.message_category import MessageCategory

# Constants
TEMPLATE_NAME = "user_reminders"  # Template name for inactive users
MAX_LAST_ACTIVE_DURATION_SECONDS = 86400  # 24 hours

# Load bot configuration
import json
config_path = os.path.join(os.path.dirname(__file__), 'bot_config.json')
with open(config_path, 'r', encoding='utf-8') as f:
    bot_config = json.load(f)



async def send_reminder_message(user_id, phone_number_id, language, use_template=True):
    """
    Send a reminder message to a user (copied from expert reminder pattern).
    """
    try:
        print(f"   📤 Sending {'template' if use_template else 'text'} message in {language}")
        
        # Create QikChat service
        qikchat_service = QikchatService()
        
        # Create user context
        user = User(
            phone_number_id=phone_number_id,
            user_type="byoebuser",
            user_language=language,
            user_id=user_id
        )
        
        # Get reminder text from bot_config
        reminder_messages = bot_config["template_messages"]["user"]["reminder"]["message"]
        message_text = reminder_messages.get(language, reminder_messages.get('en', 'Default reminder message'))
        
        # Determine message type and additional info
        if use_template:
            message_type = MessageTypes.TEMPLATE_BUTTON.value
            additional_info = {
                "template_name": TEMPLATE_NAME,
                "template_language": language,
                "template_parameters": ["1", "friendly reminder"]
            }

            # Create message context
            reminder_message_context = MessageContext(
                message_id=f"user_reminder_{user_id}_{int(datetime.now().timestamp())}",
                # message_english_text=message_text,
                # message_source_text=message_text,
                message_type=message_type,
                timestamp=str(int(datetime.now().timestamp())),
                additional_info=additional_info
            )
        else:
            message_type = MessageTypes.REGULAR_TEXT.value
            additional_info = {}
        
            # Create message context
            reminder_message_context = MessageContext(
                message_id=f"user_reminder_{user_id}_{int(datetime.now().timestamp())}",
                message_english_text=message_text,
                message_source_text=message_text,
                message_type=message_type,
                timestamp=str(int(datetime.now().timestamp())),
                additional_info=additional_info
            )
        
        # Create BYOeB message context
        reminder_byoeb_message = ByoebMessageContext(
            channel_type="qikchat",
            message_category=MessageCategory.BOT_TO_USER.value,
            user=user,
            message_context=reminder_message_context,
            incoming_timestamp=int(datetime.now().timestamp()),
            outgoing_timestamp=int(datetime.now().timestamp())
        )
        
        # Prepare and send the reminder
        requests = await qikchat_service.prepare_requests(reminder_byoeb_message)
        responses, message_ids = await qikchat_service.send_requests(requests)
        
        print(f"   ✅ Reminder sent successfully!")
        return True
        
    except Exception as e:
        print(f"   ❌ Error sending reminder message: {e}")
        import traceback
        traceback.print_exc()
        return False

async def send_user_reminders():
    """
    Main function to send reminders to all users (using expert reminder DB pattern).
    """
    try:
        print(f"🚀 Starting user reminder job at: {datetime.now()}")
        print(f"📅 Current day: {datetime.now().strftime('%A')}")
        
        # Get user collection using same pattern as expert reminder
        SINGLETON = "singleton"
        mongo_factory = MongoDBFactory(config=app_config, scope=SINGLETON)
        user_db_service = UserMongoDBService(app_config, mongo_factory)
        
        user_collection_name = app_config["databases"]["mongo_db"]["user_collection"]
        user_collection_client = await user_db_service._get_collection_client(user_collection_name)
        
        # Get ALL byoeb users (not just specific phone numbers)
        query = {"User.user_type": "byoebuser"}
        all_users = await user_collection_client.afetch_all(query)
        print(f"👥 Found {len(all_users)} byoeb users to process")
        
        # Process each user
        sent_count = 0
        failed_count = 0
        
        for i, user_doc in enumerate(all_users, 1):
            try:
                # Access nested User structure
                user_data = user_doc.get("User", {})
                user_id = user_data.get("user_id")
                phone_number_id = user_data.get("phone_number_id")
                user_language = user_data.get("user_language", "en")
                activity_timestamp = user_data.get("activity_timestamp")
                
                if not user_id or not phone_number_id:
                    print(f"⚠️  Skipping user {i}: Missing user_id or phone_number_id")
                    failed_count += 1
                    continue
                
                print(f"📱 Processing user {i}/{len(all_users)}: {user_id}")
                
                # Check if user is active (same logic as expert reminder)
                is_active = False
                if activity_timestamp:
                    activity_time = datetime.fromtimestamp(activity_timestamp)
                    threshold_time = datetime.now() - timedelta(hours=24)
                    is_active = activity_time > threshold_time
                    print(f"   📅 Activity: {activity_time.strftime('%b %d %H:%M:%S')}")
                    print(f"   📅 Threshold: {threshold_time.strftime('%b %d %H:%M:%S')}")
                    print(f"   🔍 User is {'ACTIVE' if is_active else 'INACTIVE'}")
                else:
                    print(f"   ⚠️  No activity timestamp - treating as inactive")
                # is_active = False
                # Send appropriate reminder based on activity (FIXED LOGIC)
                if is_active:
                    print(f"   📝 Active user - sending text reminder")
                    success = await send_reminder_message(user_id, phone_number_id, user_language, use_template=False)
                else:
                    print(f"   🔔 Inactive user - sending template reminder")
                    success = await send_reminder_message(user_id, phone_number_id, user_language, use_template=True)
                
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
                
                # Small delay between messages to avoid rate limiting
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"❌ Error processing user {i}: {e}")
                failed_count += 1
                continue
        
        print(f"\n{'='*60}")
        print(f"📊 USER REMINDER SUMMARY")
        print(f"{'='*60}")
        print(f"✅ Successfully sent: {sent_count}")
        print(f"❌ Failed to send: {failed_count}")
        print(f"👥 Total users processed: {len(all_users)}")
        print(f"🏁 User reminder job completed at: {datetime.now()}")
        
    except Exception as e:
        print(f"❌ Error in user reminder job: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """
    Entry point for the user reminder script.
    """
    print("🔔 User Reminder System")
    print("=" * 50)
    await send_user_reminders()

if __name__ == "__main__":
    asyncio.run(main())