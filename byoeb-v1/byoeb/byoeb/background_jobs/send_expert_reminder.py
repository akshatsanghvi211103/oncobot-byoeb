#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Expert Reminder Background Job
Sends reminder messages to experts for pending verification queries.
Runs every 1 minute to check for unanswered expert verification messages.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# Removed UTF-8 encoding setup to fix subprocess issues

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from byoeb.chat_app.configuration.config import app_config
from byoeb.factory import MongoDBFactory
from byoeb.services.databases.mongo_db import MessageMongoDBService, UserMongoDBService
from byoeb.services.channel.qikchat import QikchatService
from byoeb_core.models.byoeb.message_context import ByoebMessageContext, MessageContext, User, MessageTypes
from byoeb.models.message_category import MessageCategory
from byoeb.services.chat import utils as chat_utils

REMINDER_MESSAGE = "Kindly verify the answer to this remaining question"
# No minimum threshold - remind about any unanswered questions
TEMPLATE_NAME = "expert_reminder"  # Template name for inactive experts
MAX_LAST_ACTIVE_DURATION_SECONDS = 86400  # 24 hours (same as main system)

async def is_active_expert(user_id: str):
    """
    Check if expert is active based on last activity timestamp.
    Uses same logic as main system.
    """
    # return False
    try:
        SINGLETON = "singleton"
        mongo_factory = MongoDBFactory(config=app_config, scope=SINGLETON)
        user_db_service = UserMongoDBService(app_config, mongo_factory)
        
        result = await user_db_service.get_user_activity_timestamp(user_id)
        if result is None:
            print(f"Expert {user_id} not found in database - treating as inactive")
            return False
            
        user_timestamp, cached = result
        last_active_duration_seconds = chat_utils.get_last_active_duration_seconds(user_timestamp)
        print(f"[DEBUG] Expert last active duration: {last_active_duration_seconds} seconds")
        
        if last_active_duration_seconds >= MAX_LAST_ACTIVE_DURATION_SECONDS and cached:
            print("[DEBUG] Invalidating cache")
            await user_db_service.invalidate_user_cache(user_id)
            result = await user_db_service.get_user_activity_timestamp(user_id)
            if result is None:
                print(f"Expert {user_id} still not found after cache invalidation - treating as inactive")
                return False
            user_timestamp, cached = result
            last_active_duration_seconds = chat_utils.get_last_active_duration_seconds(user_timestamp)
            print(f"[DEBUG] Expert last active duration after cache refresh: {last_active_duration_seconds} seconds")
            
        if last_active_duration_seconds >= MAX_LAST_ACTIVE_DURATION_SECONDS:
            print(f"Expert inactive (last active: {last_active_duration_seconds}s >= {MAX_LAST_ACTIVE_DURATION_SECONDS}s)")
            return False
            
        print(f"Expert is active (last active: {last_active_duration_seconds}s < {MAX_LAST_ACTIVE_DURATION_SECONDS}s)")
        return True
        
    except Exception as e:
        print(f"Error checking expert activity for {user_id}: {e}")
        return False

async def get_pending_expert_verifications():
    """
    Get pending expert verification messages that need reminders for ALL experts.
    Returns list of message IDs that need reminders.
    """
    try:
        SINGLETON = "singleton"
        mongo_factory = MongoDBFactory(config=app_config, scope=SINGLETON)
        message_db_service = MessageMongoDBService(app_config, mongo_factory)
        
        # Get message collection with retry logic for DNS issues
        collection_name = app_config["databases"]["mongo_db"]["message_collection"]
        
        # Retry connection up to 3 times for DNS/network issues
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"[INFO] Attempting database connection (attempt {attempt + 1}/{max_retries})")
                message_collection_client = await message_db_service._get_collection_client(collection_name)
                print(f"[INFO] Database connection successful")
                break
            except Exception as conn_error:
                if "DNS" in str(conn_error) or "timeout" in str(conn_error).lower():
                    print(f"[WARNING] DNS/network error on attempt {attempt + 1}: {conn_error}")
                    if attempt < max_retries - 1:
                        import asyncio
                        print(f"[INFO] Retrying in 5 seconds...")
                        await asyncio.sleep(5)
                        continue
                    else:
                        print(f"[ERROR] All connection attempts failed")
                        raise
                else:
                    # Not a DNS/network error, re-raise immediately
                    raise
        
        # Calculate timestamp thresholds
        now = datetime.now()
        window_start_time = now - timedelta(days=3)  # Check last 3 days
        
        window_start_timestamp = str(int(window_start_time.timestamp()))
        
        print(f"Checking expert verification messages from last 3 days for ALL experts")
        print(f"   Window: {window_start_time} to {now}")
        
        # Query for ALL expert verification messages in the last 3 days (removed phone number filter)
        query = {
            "message_data.message_category": MessageCategory.BOT_TO_EXPERT_VERIFICATION.value,
            "timestamp": {
                "$gte": window_start_timestamp  # Check last 3 days (no upper threshold)
            }
        }
        
        verification_messages = await message_collection_client.afetch_all(query)
        print(f"[INFO] Found {len(verification_messages)} verification messages")
        
        pending_verifications = []
        
        for msg in verification_messages:
            message_id = msg.get("_id")
            message_data = msg.get("message_data", {})
            message_context = message_data.get("message_context", {})
            verification_text = message_context.get("message_english_text", "")
            
            # Get the expert info from the verification message
            expert_user_data = message_data.get("user", {})
            expert_phone_id = expert_user_data.get("phone_number_id")
            expert_user_id = expert_user_data.get("user_id", "")
            expert_user_type = expert_user_data.get("user_type", "medical")  # Default to medical
            
            print(f"[INFO] Checking verification message: ID={message_id}")
            print(f"   Expert: {expert_phone_id} (type: {expert_user_type})")
            print(f"   Text preview: '{verification_text[:50]}...'")
            
            if not expert_phone_id:
                print(f"   ⚠️ Skipping - no expert phone number found")
                continue
            
            # Check if this verification has been answered by looking for expert responses from THIS specific expert
            response_query = {
                "message_data.message_category": MessageCategory.EXPERT_TO_BOT.value,
                "message_data.user.phone_number_id": expert_phone_id,
                "message_data.reply_context.reply_id": message_id,
                "timestamp": {"$gt": msg.get("timestamp")}
            }
            
            expert_responses = await message_collection_client.afetch_all(response_query)
            print(f"   Found {len(expert_responses)} expert responses")
            
            if len(expert_responses) == 0:
                print(f"   No response found - adding to pending list")
                print(f"   Expert user ID: {expert_user_id}")
                
                pending_verifications.append({
                    "message_id": message_id,
                    "verification_text": verification_text,
                    "sent_time": msg.get("timestamp"),
                    "expert_user_id": expert_user_id,
                    "expert_phone_id": expert_phone_id,
                    "expert_user_type": expert_user_type
                })
            else:
                print(f"   Expert already responded - skipping")
        
        # Note: No need to explicitly close collection client as it's managed by the factory
        return pending_verifications
        
    except Exception as e:
        print(f"Error getting pending verifications: {e}")
        import traceback
        traceback.print_exc()
        return []

async def send_reminder_message(verification_message_id: str, expert_user_id: str, expert_phone_id: str, expert_user_type: str = "medical", original_verification_text: str = ""):
    """
    Send reminder message to expert using QikChat service.
    Uses activity detection to send template or text message.
    Includes the original verification question in the reminder.
    """
    try:
        print(f"Sending reminder for verification: {verification_message_id}")
        
        # Check if expert is active
        is_active = await is_active_expert(expert_user_id)
        print(f"[DEBUG] Expert activity status: {'Active' if is_active else 'Inactive'}")
        print(f"[DEBUG] Expert type: {expert_user_type}")
        
        # Create QikChat service
        qikchat_service = QikchatService()
        
        # Create expert user context
        expert_user = User(
            phone_number_id=expert_phone_id,
            user_type=expert_user_type,
            user_language="en",
            user_id=expert_user_id
        )
        
        # Create reminder message with original question
        if original_verification_text.strip():
            # Extract just the user question (before the bot's answer)
            question_part = original_verification_text.split('\n')[0] if '\n' in original_verification_text else original_verification_text
            question_part = question_part[:200] + "..." if len(question_part) > 200 else question_part
            reminder_text = f"Q: *{question_part}*\n\n{REMINDER_MESSAGE}"
        else:
            reminder_text = REMINDER_MESSAGE
        
        # Determine message type and content based on activity
        if is_active:
            # Send regular text message for active experts
            message_type = MessageTypes.REGULAR_TEXT.value
            message_text = reminder_text
            print("[INFO] Sending regular text reminder to active expert")
        else:
            # Send template message for inactive experts
            message_type = MessageTypes.TEMPLATE_BUTTON.value
            message_text = reminder_text  # Fallback text
            print(f"[INFO] Sending template '{TEMPLATE_NAME}' reminder to inactive expert")
        
        # Create reminder message context
        additional_info = {}
        if not is_active:
            # Add template information for inactive experts with question variable
            question_variable = original_verification_text.split('\n')[0] if original_verification_text.strip() else "the question"
            question_variable = question_variable[:150] + "..." if len(question_variable) > 150 else question_variable
            
            additional_info = {
                "template_name": TEMPLATE_NAME,
                "template_language": "en",
                "template_variables": {
                    "1": "1",
                    "2": question_variable
                }
            }
        
        reminder_message_context = MessageContext(
            message_id=f"reminder_{verification_message_id}_{int(datetime.now().timestamp())}",
            message_english_text=message_text,
            message_source_text=message_text,
            message_type=message_type,
            timestamp=str(int(datetime.now().timestamp())),
            additional_info=additional_info
        )
        
        # Create BYOeB message context for reminder
        reminder_byoeb_message = ByoebMessageContext(
            channel_type="qikchat",
            message_category=MessageCategory.BOT_TO_EXPERT.value,
            user=expert_user,
            message_context=reminder_message_context,
            incoming_timestamp=int(datetime.now().timestamp()),
            outgoing_timestamp=int(datetime.now().timestamp())
        )
        
        # Prepare and send the reminder
        requests = await qikchat_service.prepare_requests(reminder_byoeb_message)
        responses, message_ids = await qikchat_service.send_requests(requests)
        
        print(f"Reminder sent successfully!")
        print(f"   Response: {responses}")
        print(f"   Message IDs: {message_ids}")
        
        return True
        
    except Exception as e:
        print(f"Error sending reminder: {e}")
        import traceback
        traceback.print_exc()
        return False

async def send_consolidated_reminder(expert_user_id: str, verifications: list):
    """
    Send one consolidated reminder message with all pending questions.
    
    Args:
        expert_user_id: The expert's user ID
        verifications: List of pending verification dictionaries
    """
    try:
        print(f"[INFO] Sending consolidated reminder for {len(verifications)} questions")
        
        # Get expert's phone number and user type from the first verification (all should be for same expert)
        expert_phone_id = verifications[0]["expert_phone_id"] if verifications else None
        expert_user_type = verifications[0]["expert_user_type"] if verifications else "medical"
        if expert_phone_id == "919969557231":
            print("Skipping")
            print(verifications)
            print("Skipping this above one")
            return False
        if not expert_phone_id:
            print(f"[ERROR] No expert phone number found in verifications")
            return False
        
        # Check if expert is active
        is_active = await is_active_expert(expert_user_id)
        print(f"[DEBUG] Consolidated reminder - Expert activity result: is_active = {is_active}")
        print(f"[DEBUG] Expert type: {expert_user_type}")
        expert_user = User(
            phone_number_id=expert_phone_id,
            user_type=expert_user_type,
            language_type="en",
            user_id=expert_user_id
        )
        
        # Create consolidated message with all questions
        question_list = []
        for i, verification in enumerate(verifications, 1):
            verification_text = verification.get("verification_text", "").strip()
            # Extract the first line (usually the question)
            question = verification_text.split('\n')[0] if verification_text else f"Verification {verification['message_id']}"
            question_list.append(f"{i}. {question}")
        
        questions_text = "\n".join(question_list)
        
        if is_active:
            # Active expert gets text message with all questions
            reminder_text = f"You have {len(verifications)} pending questions awaiting your response:\n\n{questions_text}\n\nKindly provide your answers at your earliest convenience."
            message_type = MessageTypes.REGULAR_TEXT.value
            additional_info = {}
            print("[DEBUG] Taking ACTIVE branch - sending text message")
            print("[INFO] Sending consolidated text reminder to active expert")
        else:
            # Inactive expert gets template message
            reminder_text = f"You have {len(verifications)} pending questions to answer."
            message_type = MessageTypes.TEMPLATE_BUTTON.value
            additional_info = {
                "template_name": TEMPLATE_NAME,
                "template_language": "en",
                "template_variables": {
                    "1": str(len(verifications)),
                    "2": questions_text[:500] + ("..." if len(questions_text) > 500 else "")
                }
            }
            print("[DEBUG] Taking INACTIVE branch - sending template message")
            print(f"[INFO] Sending consolidated template '{TEMPLATE_NAME}' reminder to inactive expert")
        
        # Create consolidated reminder message context
        consolidated_message_id = f"consolidated_reminder_{expert_user_id}_{int(datetime.now().timestamp())}"
        
        reminder_message_context = MessageContext(
            message_id=consolidated_message_id,
            message_english_text=reminder_text,
            message_source_text=reminder_text,
            message_type=message_type,
            timestamp=str(int(datetime.now().timestamp())),
            additional_info=additional_info
        )
        
        # Create BYOeB message context for reminder
        reminder_byoeb_message = ByoebMessageContext(
            channel_type="qikchat",
            message_category=MessageCategory.BOT_TO_EXPERT.value,
            user=expert_user,
            message_context=reminder_message_context,
            incoming_timestamp=int(datetime.now().timestamp()),
            outgoing_timestamp=int(datetime.now().timestamp())
        )
        
        # Prepare and send the consolidated reminder
        qikchat_service = QikchatService()
        
        if not is_active:
            # For inactive experts, update additional_info for template and use system's template handling
            print("[DEBUG] Setting up template message for inactive expert")
            
            # Clean questions text for WhatsApp template parameters (no newlines, tabs, or >4 spaces)
            clean_questions_text = questions_text.replace('\n', ' | ').replace('\t', ' ').replace('\r', ' ')
            # Replace multiple spaces with single space, but preserve up to 4 spaces
            import re
            clean_questions_text = re.sub(r' {5,}', ' ', clean_questions_text)  # Replace 5+ spaces with 1
            clean_questions_text = clean_questions_text[:500] + ("..." if len(clean_questions_text) > 500 else "")
            
            reminder_byoeb_message.message_context.additional_info = {
                "template_name": TEMPLATE_NAME,
                "template_language": "en",  # String, not object
                "template_parameters": [
                    str(len(verifications)),  # Parameter 1: number of questions
                    clean_questions_text  # Parameter 2: cleaned questions list
                ]
            }
            reminder_byoeb_message.message_context.message_type = MessageTypes.TEMPLATE_BUTTON.value
            print(f"[DEBUG] Template parameters: {reminder_byoeb_message.message_context.additional_info['template_parameters']}")
        
        # Use prepare_requests for both active and inactive (system handles template conversion)
        print("[DEBUG] Preparing requests through system")
        requests = await qikchat_service.prepare_requests(reminder_byoeb_message)
        print(f"[DEBUG] Prepared {len(requests)} request(s)")
        
        # Debug: show details of each request
        for i, req in enumerate(requests):
            print(f"[DEBUG] Request {i}: type={req.get('type', 'unknown')}, to_contact={req.get('to_contact', 'unknown')}")
            if req.get('type') == 'template':
                print(f"[DEBUG]   Template name: {req.get('template', {}).get('name', 'unknown')}")
            elif req.get('type') == 'text':
                print(f"[DEBUG]   Text body: {req.get('text', {}).get('body', 'unknown')[:50]}...")
        
        # Send only the appropriate request type based on expert activity
        if not is_active and len(requests) > 1:
            # For inactive experts, send only template version if available
            template_requests = [req for req in requests if req.get('type') == 'template']
            if template_requests:
                print("[DEBUG] Sending template request for inactive expert")
                responses, message_ids = await qikchat_service.send_requests([template_requests[0]])
            else:
                print("[DEBUG] No template request found, sending first request")
                responses, message_ids = await qikchat_service.send_requests([requests[0]])
        else:
            # For active experts or single request, send first/only request
            print(f"[DEBUG] Sending {'first' if len(requests) > 1 else 'only'} request for active expert")
            responses, message_ids = await qikchat_service.send_requests([requests[0]])
        
        print(f"[DEBUG] Sent 1 request, got {len(message_ids)} message IDs")
        
        print(f"Consolidated reminder sent successfully!")
        print(f"   Questions included: {len(verifications)}")
        print(f"   Message type sent: {reminder_byoeb_message.message_context.message_type}")
        print(f"   Template info: {additional_info}")
        print(f"   Response: {responses}")
        print(f"   Message IDs: {message_ids}")
        
        # Print full message details for debugging
        print(f"[DEBUG] Full message context:")
        print(f"  - Message ID: {reminder_byoeb_message.message_context.message_id}")
        print(f"  - Message Type: {reminder_byoeb_message.message_context.message_type}")
        print(f"  - Additional Info: {reminder_byoeb_message.message_context.additional_info}")
        print(f"  - Message Text: {reminder_byoeb_message.message_context.message_english_text[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"Error sending consolidated reminder: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """
    Main function to check for pending verifications and send reminders.
    """
    print(f"Starting expert reminder job at {datetime.now()}")
    
    try:
        # Get pending verifications
        pending_verifications = await get_pending_expert_verifications()
        
        if not pending_verifications:
            print("No pending verifications found - all experts are up to date!")
            return
        
        print(f"Found {len(pending_verifications)} pending verifications")
        
        # Group all pending verifications by expert (in case there are multiple experts later)
        expert_verifications = {}
        for verification in pending_verifications:
            expert_user_id = verification["expert_user_id"]
            if expert_user_id not in expert_verifications:
                expert_verifications[expert_user_id] = []
            expert_verifications[expert_user_id].append(verification)
        
        # Send one consolidated reminder per expert
        for expert_user_id, verifications in expert_verifications.items():
            print(f"[INFO] Processing consolidated reminder for expert: {expert_user_id}")
            print(f"   Number of pending questions: {len(verifications)}")
            
            success = await send_consolidated_reminder(expert_user_id, verifications)
            
            if success:
                print(f"Consolidated reminder sent for expert: {expert_user_id}")
            else:
                print(f"Failed to send consolidated reminder for expert: {expert_user_id}")
        
        print(f"Expert reminder job completed successfully!")
        
    except Exception as e:
        print(f"Expert reminder job failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())