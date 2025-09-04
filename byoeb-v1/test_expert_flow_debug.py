#!/usr/bin/env python3
"""
Test script to debug expert verification flow
This will help us understand why messages aren't being found in the database
"""

import asyncio
import json
from datetime import datetime
from byoeb.chat_app.configuration.dependency_setup import setup_dependencies
from byoeb.services.databases.mongo_db.message_db import MessageMongoDBService
from byoeb_core.models.byoeb.message_context import ByoebMessageContext, MessageContext
from byoeb_core.models.byoeb.user import User

async def test_message_storage_and_lookup():
    """Test message storage and lookup to understand the database flow"""
    
    print("🧪 Starting Expert Flow Debug Test")
    print("=" * 50)
    
    # Setup dependencies
    await setup_dependencies()
    from byoeb.chat_app.configuration.dependency_setup import message_db_service
    
    # Create a test expert verification message
    test_message_id = "test_expert_verification_123"
    test_qikchat_id = "MTPPNBs9Ci5BRfDfRZe0QFFzg"  # The ID we're looking for
    
    print(f"📝 Creating test message with ID: {test_message_id}")
    
    test_message = ByoebMessageContext(
        channel_type="qikchat",
        message_category="bot_to_expert_verification",
        user=User(
            user_id="test_expert",
            user_type="byoebexpert",
            user_language="en",
            phone_number_id="919739811075"
        ),
        message_context=MessageContext(
            message_id=test_message_id,
            message_type="interactive_button",
            message_source_text="Test verification message",
            message_english_text="Test verification message",
            additional_info={
                "verification_status": "pending"
            }
        ),
        incoming_timestamp=int(datetime.now().timestamp())
    )
    
    # Test 1: Store the message with original ID
    print(f"\n🗄️ Test 1: Storing message with original ID")
    create_queries = message_db_service.message_create_queries([test_message])
    print(f"Create query: {json.dumps(create_queries[0], indent=2)}")
    
    await message_db_service.create_messages({"create": create_queries})
    print(f"✅ Message stored with ID: {test_message_id}")
    
    # Test 2: Try to find the message with original ID
    print(f"\n🔍 Test 2: Looking up message with original ID")
    found_messages = await message_db_service.get_bot_messages([test_message_id])
    print(f"Found {len(found_messages)} messages with ID '{test_message_id}'")
    
    # Test 3: Update the message ID to simulate Qikchat response
    print(f"\n🔄 Test 3: Updating message ID to simulate Qikchat response")
    success = await message_db_service.update_message_id(test_message_id, test_qikchat_id)
    print(f"Update success: {success}")
    
    # Test 4: Try to find the message with new Qikchat ID
    print(f"\n🔍 Test 4: Looking up message with Qikchat ID")
    found_messages = await message_db_service.get_bot_messages([test_qikchat_id])
    print(f"Found {len(found_messages)} messages with ID '{test_qikchat_id}'")
    
    if found_messages:
        message = found_messages[0]
        print(f"✅ Message found!")
        print(f"   - Message ID: {message.message_context.message_id}")
        print(f"   - Message category: {message.message_category}")
        print(f"   - Verification status: {message.message_context.additional_info.get('verification_status')}")
    else:
        print(f"❌ No message found with Qikchat ID")
    
    # Test 5: List all messages to see what's actually in the database
    print(f"\n📋 Test 5: Listing all messages in database")
    try:
        # Get all messages (we'll limit this for testing)
        all_messages = await message_db_service.get_latest_bot_messages_by_timestamp("0")
        print(f"Total messages in database: {len(all_messages)}")
        for i, msg in enumerate(all_messages[-5:]):  # Show last 5 messages
            print(f"   {i}: ID={msg.message_context.message_id}, Category={msg.message_category}")
    except Exception as e:
        print(f"Error listing messages: {e}")
    
    print("\n" + "=" * 50)
    print("🧪 Expert Flow Debug Test Complete")

if __name__ == "__main__":
    asyncio.run(test_message_storage_and_lookup())
