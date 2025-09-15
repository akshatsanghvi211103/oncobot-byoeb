#!/usr/bin/env python3
"""
Direct test of the QikChat integration with TTS to see if the audio/wav content type resolves the 403 issue.
"""
import asyncio
import logging
import json
import sys
import os

# Add the project paths to sys.path
sys.path.append(os.path.abspath('.'))
sys.path.append(os.path.abspath('./byoeb'))
sys.path.append(os.path.abspath('./byoeb-core'))
sys.path.append(os.path.abspath('./byoeb-integrations'))

from byoeb_integrations.channel.qikchat.request_payload import QikChatRequestPayload

async def test_direct_qikchat_tts():
    """Test QikChat integration directly with a TTS audio URL"""
    
    # Create a test URL with the correct content type we just fixed
    test_audio_url = "https://smartkcstorage1.blob.core.windows.net/oncobot-container/tts_audio_0239d977c2004a8ba8322a4f72ec8e86.wav?se=2025-09-15T09%3A00%3A00Z&sp=r&sv=2022-11-02&sr=b&skoid=f5b64d94-ba27-422a-abb5-cad2b511c671&sktid=72f988bf-86f1-41af-91ab-2d7cd011db47&skt=2025-09-15T07%3A12%3A06Z&ske=2025-09-15T09%3A00%3A00Z&sks=b&skv=2022-11-02&sig=x3h%2BScCmlOwIG%2BRoKXGZlGM3Eejt3B1oydttBG6BiLk%3D"
    
    # Create a test message with audio
    from byoeb_core.models.v1.v1_models import Message, MessageType, MessageSource
    
    test_message = Message(
        message_type=MessageType.TEXT,
        text_message="This is a test message with TTS audio",
        source=MessageSource.BOT,
        additional_info={
            "audio_url": test_audio_url
        }
    )
    
    # Use QikChat payload converter
    qikchat_payload = QikChatRequestPayload()
    
    # Convert to QikChat format
    messages = [test_message]
    
    try:
        # Import from the handler to get QikChat service
        from byoeb.byoeb.handler.qikchat_handler import QikChatHandler
        
        handler = QikChatHandler()
        qik_chat_service = handler.qik_chat_service
        
        # Create payload and send
        payload_data = qikchat_payload.create_payload(messages, "test_user", "test_session")
        
        print(f"📤 Sending QikChat payload with audio URL:")
        print(f"   Audio URL: {test_audio_url[:100]}...")
        print(f"   Content: {json.dumps(payload_data, indent=2)}")
        
        response = await qik_chat_service.send_message(payload_data)
        
        if response:
            print(f"✅ QikChat response: {response}")
            return True
        else:
            print("❌ Failed to send message to QikChat")
            return False
            
    except Exception as e:
        print(f"❌ Error testing QikChat TTS: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(test_direct_qikchat_tts())
    if result:
        print("🎉 QikChat TTS test with audio/wav content type passed!")
    else:
        print("💥 QikChat TTS test failed!")