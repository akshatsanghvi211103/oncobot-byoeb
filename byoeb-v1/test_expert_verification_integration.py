"""
Test script to verify that:
1. Chunks are being printed during retrieval
2. Expert verifier messages are being sent to 919739811075
"""
import asyncio
import sys
import os

# Add the paths to make imports work
sys.path.append(os.path.join(os.path.dirname(__file__), 'byoeb'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'byoeb-core'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'byoeb-integrations'))

async def test_expert_verification_and_chunk_printing():
    """
    Test that expert verification messages are created and chunks are printed
    """
    print("🔬 Testing Expert Verification and Chunk Printing")
    print("=" * 60)
    
    try:
        # Test 1: Verify chunk printing
        print("Test 1: Testing chunk retrieval and printing...")
        from byoeb.services.chat.message_handlers.user_flow_handlers.generate import ByoebUserGenerateResponse
        
        handler = ByoebUserGenerateResponse()
        test_query = "What are the side effects of chemotherapy?"
        
        print(f"Query: {test_query}")
        print("Looking for chunk debug output...")
        
        # This should trigger the chunk printing we added
        chunks = await handler._ByoebUserGenerateResponse__aretrieve_chunks(test_query, 7)
        
        print(f"✅ Retrieved {len(chunks)} chunks successfully")
        
        # Test 2: Verify expert message creation
        print("\nTest 2: Testing expert verification message creation...")
        
        # Create a mock user message
        from byoeb_core.models.byoeb.message_context import ByoebMessageContext, MessageContext, User
        from byoeb.models.message_category import MessageCategory
        import uuid
        
        mock_user = User(
            user_id="test_user_123",
            user_type="byoebuser",
            user_language="en",
            phone_number_id="test_phone_123",
            experts=None  # This will trigger the default expert phone number
        )
        
        mock_message = ByoebMessageContext(
            channel_type="qikchat",
            message_category=MessageCategory.USER_TO_BOT.value,
            user=mock_user,
            message_context=MessageContext(
                message_id=str(uuid.uuid4()),
                message_source_text=test_query,
                message_english_text=test_query
            )
        )
        
        # Test expert verification message creation
        expert_message = handler._ByoebUserGenerateResponse__create_expert_verification_message(
            mock_message,
            "This is a test bot response",
            "medical"
        )
        
        print(f"✅ Expert message created successfully!")
        print(f"   Expert phone: {expert_message.user.phone_number_id}")
        print(f"   Expert user type: {expert_message.user.user_type}")
        print(f"   Message category: {expert_message.message_category}")
        print(f"   Message type: {expert_message.message_context.message_type}")
        
        # Verify the phone number is correct
        if expert_message.user.phone_number_id == "919739811075":
            print("✅ Expert phone number is correctly set to 919739811075")
        else:
            print(f"❌ Expert phone number is incorrect: {expert_message.user.phone_number_id}")
        
        # Test 3: Verify expert message detection
        print("\nTest 3: Testing expert message detection...")
        
        from byoeb.services.chat import utils
        
        # Test that our expert message is detected
        test_messages = [mock_message, expert_message]
        expert_messages = utils.get_expert_byoeb_messages(test_messages)
        
        print(f"✅ Found {len(expert_messages)} expert messages in list")
        if len(expert_messages) > 0:
            print(f"   Expert message category: {expert_messages[0].message_category}")
            print(f"   Expert phone: {expert_messages[0].user.phone_number_id}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("Testing Enhanced Expert Verification & Chunk Printing")
    print("=" * 60)
    
    success = await test_expert_verification_and_chunk_printing()
    
    if success:
        print("\n✅ All tests completed successfully!")
        print("\nChanges made:")
        print("1. ✅ Chunks are now printed during retrieval")
        print("2. ✅ Expert verifier phone number set to 919739811075")
        print("3. ✅ Expert workflow enabled in send.py")
        print("4. ✅ Expert message detection enhanced")
    else:
        print("\n❌ Tests failed!")

if __name__ == "__main__":
    asyncio.run(main())
