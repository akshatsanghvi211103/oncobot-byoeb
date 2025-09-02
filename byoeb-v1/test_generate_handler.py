#!/usr/bin/env python3
"""
Test the complete knowledge base integration in the generate handler
"""
import asyncio
import sys
import os

# Add the byoeb directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'byoeb'))

async def test_generate_handler():
    """Test that the generate handler can retrieve chunks from KB"""
    try:
        print("🧪 Testing complete message generation flow...")
        
        from byoeb.services.chat.message_handlers.user_flow_handlers.generate import ByoebUserGenerateResponse
        
        # Create handler instance
        handler = ByoebUserGenerateResponse()
        
        # Test chunk retrieval
        test_questions = [
            "what is cancer?",
            "side effects of radiotherapy",
            "cancer treatment options"
        ]
        
        for question in test_questions:
            print(f"\n🔎 Testing: '{question}'")
            chunks = await handler._ByoebUserGenerateResponse__aretrieve_chunks(question, 3)
            print(f"✅ Retrieved {len(chunks)} chunks")
            
            if chunks:
                print(f"  First chunk: {chunks[0].text[:100]}...")
                if chunks[0].metadata:
                    print(f"  Source: {chunks[0].metadata.source}")
        
        print("\n🎉 Generate handler knowledge base integration is working!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing generate handler: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_generate_handler())
    sys.exit(0 if result else 1)
