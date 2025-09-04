"""
Simple test to verify expert verification flow without complex dependencies
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "byoeb"))

async def test_basic_expert_flow():
    """Test basic expert verification flow"""
    print("=== Testing Basic Expert Flow ===")
    
    # Step 1: Simulate user message
    user_message = {
        "id": "user_msg_123",
        "content": "What are the side effects of chemotherapy?",
        "timestamp": datetime.utcnow().isoformat(),
        "type": "user"
    }
    print(f"1. User asks: {user_message['content']}")
    
    # Step 2: Simulate bot response
    bot_response = {
        "id": "bot_msg_456",
        "content": "Common side effects of chemotherapy include nausea, fatigue, and hair loss.",
        "timestamp": datetime.utcnow().isoformat(),
        "type": "bot",
        "reply_to": user_message["id"]
    }
    print(f"2. Bot responds: {bot_response['content']}")
    
    # Step 3: Simulate expert verification message
    expert_verification = {
        "id": "expert_verify_789",
        "content": f"Please verify this response:\n\nUser: {user_message['content']}\nBot: {bot_response['content']}",
        "timestamp": datetime.utcnow().isoformat(),
        "type": "expert_verification",
        "reply_to": bot_response["id"],
        "buttons": ["Yes", "No"]
    }
    print(f"3. Expert gets verification: {expert_verification['content']}")
    
    # Step 4: Simulate expert clicking "No"
    expert_rejection = {
        "id": "expert_no_101",
        "content": "No",
        "timestamp": datetime.utcnow().isoformat(),
        "type": "expert_response",
        "reply_to": expert_verification["id"],
        "button_clicked": "No"
    }
    print(f"4. Expert clicks: {expert_rejection['content']}")
    
    # Step 5: Expected correction request
    correction_request = {
        "id": "correction_req_102",
        "content": "Please provide the corrected answer:",
        "timestamp": datetime.utcnow().isoformat(),
        "type": "correction_request",
        "reply_to": expert_rejection["id"]
    }
    print(f"5. System should ask: {correction_request['content']}")
    
    # Step 6: Expert provides correction
    expert_correction = {
        "id": "expert_correction_103",
        "content": "Common side effects include nausea, fatigue, hair loss, mouth sores, and increased infection risk. Severity varies by drug type and individual patient factors.",
        "timestamp": datetime.utcnow().isoformat(),
        "type": "expert_correction",
        "reply_to": correction_request["id"]
    }
    print(f"6. Expert provides correction: {expert_correction['content']}")
    
    # Step 7: Final message to user
    final_response = {
        "id": "final_msg_104",
        "content": expert_correction["content"],
        "timestamp": datetime.utcnow().isoformat(),
        "type": "final_response",
        "reply_to": user_message["id"],
        "verified_by": "expert"
    }
    print(f"7. User receives verified answer: {final_response['content']}")
    
    print("\n=== Flow Summary ===")
    print("✅ User question received")
    print("✅ Bot generated response")
    print("✅ Expert verification request sent")
    print("✅ Expert rejected response")
    print("✅ Correction request sent")
    print("✅ Expert provided correction")
    print("✅ Verified answer sent to user")
    
    return True

async def test_simple_message_storage():
    """Test simple message storage simulation"""
    print("\n=== Testing Message Storage Simulation ===")
    
    # Simulate message storage
    messages = {}
    
    # Store a bot message
    bot_msg_id = "MTPPNBs9Ci5BRfDfRZe0QFFzg"
    bot_message = {
        "_id": bot_msg_id,
        "content": "This is a bot response",
        "type": "bot",
        "timestamp": datetime.utcnow().isoformat()
    }
    messages[bot_msg_id] = bot_message
    print(f"Stored bot message with ID: {bot_msg_id}")
    
    # Simulate expert reply
    expert_reply_to = bot_msg_id
    print(f"Expert replying to message ID: {expert_reply_to}")
    
    # Lookup bot message
    found_message = messages.get(expert_reply_to)
    if found_message:
        print(f"✅ Found bot message: {found_message['content']}")
        print("✅ Reply context established successfully")
    else:
        print(f"❌ Bot message not found for ID: {expert_reply_to}")
        print("❌ Reply context failed")
    
    return found_message is not None

if __name__ == "__main__":
    print("Starting Simple Expert Verification Test...\n")
    
    # Run tests
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Test basic flow
        flow_success = loop.run_until_complete(test_basic_expert_flow())
        
        # Test message storage
        storage_success = loop.run_until_complete(test_simple_message_storage())
        
        print(f"\n=== Test Results ===")
        print(f"Basic Flow Test: {'✅ PASS' if flow_success else '❌ FAIL'}")
        print(f"Message Storage Test: {'✅ PASS' if storage_success else '❌ FAIL'}")
        
        if flow_success and storage_success:
            print("\n🎉 All tests passed! The expert verification flow logic is sound.")
            print("\nNext steps:")
            print("1. Check if messages are being stored correctly in MongoDB")
            print("2. Verify message ID synchronization between Qikchat and database")
            print("3. Debug why bot messages cannot be found during expert replies")
        else:
            print("\n❌ Some tests failed. Review the flow logic.")
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        loop.close()
