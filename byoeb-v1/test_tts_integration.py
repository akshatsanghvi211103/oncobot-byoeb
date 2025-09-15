#!/usr/bin/env python3
"""
Test script to verify TTS integration with QikChat
"""
import asyncio
import sys
import os

# Add the current directory to Python path so we can import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

async def test_tts_integration():
    """Test TTS service and QikChat integration"""
    print("🧪 Testing TTS Integration with QikChat...")
    
    try:
        # Test 1: Import TTS service
        print("\n1️⃣ Testing TTS service import...")
        from byoeb.chat_app.configuration.dependency_setup import tts_service
        print("✅ TTS service imported successfully")
        
        # Test 2: Check TTS service method
        print("\n2️⃣ Checking TTS service methods...")
        if hasattr(tts_service, 'generate_audio_url'):
            print("✅ TTS service has generate_audio_url method")
        else:
            print("❌ TTS service missing generate_audio_url method")
            print(f"Available methods: {[method for method in dir(tts_service) if not method.startswith('_')]}")
            return
        
        # Test 3: Test audio URL generation
        print("\n3️⃣ Testing audio URL generation...")
        test_text = "Hello, this is a test message for TTS integration."
        test_language = "en"
        
        try:
            audio_url = await tts_service.generate_audio_url(
                text=test_text,
                language=test_language
            )
            if audio_url:
                print(f"✅ Audio URL generated successfully: {audio_url[:50]}...")
                
                # Test 4: Test QikChat audio message format
                print("\n4️⃣ Testing QikChat audio message format...")
                from byoeb_core.models.byoeb_message_context import ByoebMessageContext, MessageContext, User
                from byoeb_core.models.constants import MessageTypes
                
                # Create test message with audio URL
                test_message = ByoebMessageContext(
                    channel_type="qikchat",
                    message_category="bot_to_user_response",
                    user=User(
                        user_id="test_user",
                        user_language="en",
                        user_type="regular",
                        phone_number_id="+1234567890",
                        last_conversations=[]
                    ),
                    message_context=MessageContext(
                        message_id="test_msg_123",
                        message_type=MessageTypes.REGULAR_AUDIO.value,
                        message_source_text=test_text,
                        message_english_text=test_text,
                        additional_info={
                            "audio_url": audio_url,
                            "mime_type": "audio/wav"
                        }
                    ),
                    incoming_timestamp=0
                )
                
                # Test 5: Test utils.has_audio_additional_info
                print("\n5️⃣ Testing audio detection...")
                from byoeb.byoeb.services.chat import utils
                if utils.has_audio_additional_info(test_message):
                    print("✅ Audio message detected correctly")
                else:
                    print("❌ Audio message not detected")
                    return
                
                # Test 6: Test QikChat request payload generation
                print("\n6️⃣ Testing QikChat request payload generation...")
                from byoeb_integrations.channel.qikchat import request_payload
                
                qik_request = await request_payload.get_qikchat_audio_request_from_byoeb_message(test_message)
                print(f"✅ QikChat request generated: {qik_request}")
                
                # Verify request format
                if (qik_request.get("type") == "audio" and 
                    qik_request.get("audio", {}).get("link") == audio_url):
                    print("✅ QikChat audio request format is correct")
                else:
                    print("❌ QikChat audio request format is incorrect")
                    return
                
                print("\n🎉 All TTS integration tests passed!")
                
            else:
                print("❌ TTS service returned empty audio URL")
                
        except Exception as e:
            print(f"❌ Error testing audio URL generation: {e}")
            
    except Exception as e:
        print(f"❌ Error in TTS integration test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_tts_integration())