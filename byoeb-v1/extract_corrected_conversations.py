#!/usr/bin/env python3
"""
Extract Corrected Conversations
Retrieves conversations from the past hour where experts said "No" and provided corrections.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add the byoeb directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "byoeb"))

from byoeb.chat_app.configuration.config import app_config
from byoeb.factory.mongo_db import MongoDBFactory
from byoeb.services.databases.mongo_db.message_db import MessageMongoDBService
from byoeb.models.message_category import MessageCategory

async def get_corrected_conversations():
    """
    Get conversations where expert said "No" and provided corrections in the past hour.
    """
    try:
        # Initialize database connection
        SINGLETON = "singleton"
        mongo_factory = MongoDBFactory(config=app_config, scope=SINGLETON)
        message_db_service = MessageMongoDBService(app_config, mongo_factory)
        
        # Get message collection
        collection_name = app_config["databases"]["mongo_db"]["message_collection"]
        message_collection_client = await message_db_service._get_collection_client(collection_name)
        
        # Calculate time window (past 1 hour)
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        one_hour_ago_timestamp = str(int(one_hour_ago.timestamp()))
        
        print(f"🔍 Searching for corrected conversations from: {one_hour_ago} to {now}")
        print(f"   Timestamp range: {one_hour_ago_timestamp} - {int(now.timestamp())}")
        
        # Find expert responses where they said "No" in the past hour
        expert_no_responses_query = {
            "message_data.message_category": {"$in": [MessageCategory.EXPERT_TO_BOT.value]},
            "timestamp": {"$gte": one_hour_ago_timestamp},
            "message_data.message_context.message_english_text": "No"
        }
        
        expert_no_responses = await message_collection_client.afetch_all(expert_no_responses_query)
        print(f"📝 Found {len(expert_no_responses)} expert 'No' responses in the past hour")
        
        corrected_conversations = []
        
        for i, no_response in enumerate(expert_no_responses):
            print(f"🔍 Processing expert 'No' response {i+1}/{len(expert_no_responses)}")
            
            conversation = {
                "expert_no_message_id": no_response.get("_id"),
                "expert_no_timestamp": no_response.get("timestamp"),
                "original_verification_id": None,
                "user_query": None,
                "bot_answer": None,
                "expert_correction": None,
                "final_corrected_message": None
            }
            
            # Get the original verification message that this "No" is replying to
            reply_context = no_response.get("message_data", {}).get("reply_context", {})
            original_verification_id = reply_context.get("reply_id")
            
            if original_verification_id:
                conversation["original_verification_id"] = original_verification_id
                
                # Get the original verification message
                verification_query = {"_id": original_verification_id}
                verification_messages = await message_collection_client.afetch_all(verification_query)
                
                verification_msg = None
                if verification_messages and len(verification_messages) > 0:
                    verification_msg = verification_messages[0]
                    
                    if verification_msg:
                        message_context = verification_msg.get("message_data", {}).get("message_context", {})
                        verification_text = message_context.get("message_english_text", "")
                        
                        # Parse the verification message to extract user query and bot answer
                        print(f"   📋 Verification text: '{verification_text[:100]}...'")
                        lines = verification_text.split('\n')
                        
                        # Handle different verification message formats
                        if len(lines) >= 3:
                            # Format: line 0 = question, line 1 = answer, line 2 = "Is the answer correct?"
                            conversation["user_query"] = lines[0].strip()
                            conversation["bot_answer"] = lines[1].strip()
                            print(f"   📋 Parsed - Query: '{conversation['user_query'][:50]}...'")
                            print(f"   📋 Parsed - Answer: '{conversation['bot_answer'][:50]}...'")
                        else:
                            # Fallback to original parsing logic
                            for i, line in enumerate(lines):
                                if line.startswith("Question:"):
                                    conversation["user_query"] = line.replace("Question:", "").strip()
                                elif line.startswith("Bot_Answer:"):
                                    # Bot answer might span multiple lines
                                    bot_answer_lines = [line.replace("Bot_Answer:", "").strip()]
                                    # Look for continuation lines
                                    for j in range(i + 1, len(lines)):
                                        if lines[j].startswith("Is the answer correct?"):
                                            break
                                        bot_answer_lines.append(lines[j].strip())
                                    conversation["bot_answer"] = " ".join(bot_answer_lines).strip()
                else:
                    print(f"⚠️  Verification message not found for ID: {original_verification_id}")
                
                # Find the expert's correction message (should be from same expert, after the "No" response)
                expert_user_id = no_response.get("message_data", {}).get("user", {}).get("user_id")
                no_timestamp = no_response.get("timestamp")
                
                correction_query = {
                    "message_data.message_category": {"$in": [MessageCategory.EXPERT_TO_BOT.value]},
                    "message_data.user.user_id": expert_user_id,
                    "timestamp": {"$gt": no_timestamp}
                }
                print(f"   📋 Looking for corrections from expert {expert_user_id} after timestamp {no_timestamp}")
                
                correction_messages = await message_collection_client.afetch_all(correction_query)
                print(f"   📋 Found {len(correction_messages) if correction_messages else 0} correction messages")
                
                correction_timestamp = None
                if correction_messages:
                    # Find the correction that's not just "No"
                    for correction_msg in correction_messages:
                        correction_context = correction_msg.get("message_data", {}).get("message_context", {})
                        correction_text = correction_context.get("message_english_text", "").strip()
                        if correction_text and correction_text.lower() != "no":
                            conversation["expert_correction"] = correction_text
                            print(f"   ✅ Expert correction found: '{correction_text[:50]}...'")
                            correction_timestamp = correction_msg.get("timestamp")
                            break
                else:
                    print(f"   ❌ No correction message found from expert {expert_user_id}")
                
                # Look for the final corrected message sent to user (after the correction)
                if correction_timestamp and verification_msg:
                    # Get the original user ID from cross_conversation_context
                    cross_context = verification_msg.get("message_data", {}).get("cross_conversation_context", {})
                    user_id = None
                    if cross_context and cross_context.get("user"):
                        user_id = cross_context.get("user", {}).get("user_id")
                    
                    if user_id:
                        # Find bot response to user after the correction timestamp
                        user_response_query = {
                            "message_data.message_category": MessageCategory.BOT_TO_USER_RESPONSE.value,
                            "timestamp": {"$gte": correction_timestamp},
                            "message_data.user.user_id": user_id
                        }
                        print(f"   📋 Looking for final message to user {user_id} after {correction_timestamp}")
                        
                        user_responses = await message_collection_client.afetch_all(user_response_query)
                        print(f"   📋 Found {len(user_responses) if user_responses else 0} user response messages")
                        
                        if user_responses:
                            user_response = user_responses[0]
                            user_context = user_response.get("message_data", {}).get("message_context", {})
                            final_message = user_context.get("message_english_text", "").strip()
                            conversation["final_corrected_message"] = final_message
                            print(f"   ✅ Final corrected message found: '{final_message[:50]}...'")
                    else:
                        print(f"   ❌ Could not find user ID from verification message")
            
            # Only add conversations that have meaningful data
            if conversation["user_query"] and conversation["expert_correction"]:
                corrected_conversations.append(conversation)
        
        return corrected_conversations
        
    except Exception as e:
        print(f"❌ Error retrieving corrected conversations: {e}")
        import traceback
        traceback.print_exc()
        return []

def print_conversations(conversations):
    """Print the corrected conversations in a readable format."""
    print(f"\n{'='*80}")
    print(f"📋 CORRECTED CONVERSATIONS FROM PAST HOUR")
    print(f"{'='*80}")
    print(f"Found: {len(conversations)} conversations with expert corrections\n")
    
    for i, conv in enumerate(conversations, 1):
        print(f"🔍 CONVERSATION #{i}")
        print(f"{'─'*60}")
        print(f"📅 Timestamp: {datetime.fromtimestamp(int(conv['expert_no_timestamp']))}")
        print(f"🆔 Verification ID: {conv['original_verification_id']}")
        
        print(f"\n❓ USER QUERY:")
        print(f"   {conv['user_query'] or 'N/A'}")
        
        print(f"\n🤖 ORIGINAL BOT ANSWER:")
        print(f"   {conv['bot_answer'] or 'N/A'}")
        
        print(f"\n❌ EXPERT RESPONSE:")
        print(f"   No")
        
        print(f"\n✏️ EXPERT CORRECTION:")
        print(f"   {conv['expert_correction'] or 'N/A'}")
        
        print(f"\n✅ FINAL CORRECTED MESSAGE TO USER:")
        print(f"   {conv['final_corrected_message'] or 'Not found - may still be processing'}")
        
        print(f"\n{'═'*60}\n")
    
    if len(conversations) == 0:
        print("ℹ️  No corrected conversations found in the past hour.")
        print("   This could mean:")
        print("   - No expert corrections occurred")
        print("   - All expert responses were 'Yes' (approved)")
        print("   - Messages are older than 1 hour")

async def main():
    """Main function to extract and display corrected conversations."""
    print("🚀 Starting extraction of corrected conversations...")
    
    conversations = await get_corrected_conversations()
    print_conversations(conversations)
    
    print(f"\n✅ Extraction completed! Found {len(conversations)} corrected conversations.")

if __name__ == "__main__":
    asyncio.run(main())