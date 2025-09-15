#!/usr/bin/env python3
"""
Test TTS service with MP3 output format for QikChat compatibility.
"""
import asyncio
import logging
import sys
import os

# Add the project paths to sys.path
sys.path.append(os.path.abspath('.'))
sys.path.append(os.path.abspath('./byoeb'))
sys.path.append(os.path.abspath('./byoeb-core'))
sys.path.append(os.path.abspath('./byoeb-integrations'))

async def test_mp3_tts():
    """Test TTS service with MP3 output"""
    try:
        # Import Azure Speech Translator directly to test MP3 generation
        from byoeb_integrations.translators.speech.azure.async_azure_speech_translator import AsyncAzureSpeechTranslator
        from byoeb_integrations.media_storage.azure.async_azure_blob_storage import AsyncAzureBlobStorage
        from azure.identity import DefaultAzureCredential
        
        print("🎵 Testing MP3 TTS Generation...")
        
        # Create token provider
        credential = DefaultAzureCredential()
        def token_provider():
            token = credential.get_token("https://cognitiveservices.azure.com/.default")
            return token.token
        
        # Initialize speech translator (default speech_voice="female" should work)
        speech_translator = AsyncAzureSpeechTranslator(
            region="eastus",  # Replace with your region
            resource_id="/subscriptions/cef13953-6a76-4434-9a65-1d95481f83c7/resourceGroups/smartkc/providers/Microsoft.CognitiveServices/accounts/smartkc-cs-speech",  # Replace with your resource ID
            token_provider=token_provider,
            speech_voice="female",  # Explicitly set to female
            country_code="IN"  # Use Indian voices
        )
        
        # Test text
        test_text = "Hello! This is a test of MP3 audio generation for QikChat integration."
        
        print(f"🎙️ Generating MP3 audio for: '{test_text}'")
        
        try:
            # Generate MP3 audio (use "en" not "en-US" to match voice dict)
            audio_bytes = await speech_translator.atext_to_speech(
                input_text=test_text,
                source_language="en"
            )
        except Exception as speech_error:
            print(f"❌ Speech generation error: {speech_error}")
            # Try with different voice setup
            speech_translator.change_speech_voice("female")
            audio_bytes = await speech_translator.atext_to_speech(
                input_text=test_text,
                source_language="en"
            )
        
        if audio_bytes:
            print(f"✅ Generated {len(audio_bytes)} bytes of MP3 audio")
            
            # Check if it starts with MP3 header
            if audio_bytes[:3] == b'ID3' or audio_bytes[:2] == b'\xff\xfb':
                print("✅ Valid MP3 file detected!")
            else:
                print(f"❓ Unexpected audio format detected. First few bytes: {audio_bytes[:10]}")
            
            # Initialize blob storage
            blob_storage = AsyncAzureBlobStorage(
                storage_account_name="smartkcstorage1",
                container_name="oncobot-container",
                credential=credential
            )
            
            # Upload test MP3 file
            import uuid
            test_filename = f"test_mp3_tts_{uuid.uuid4().hex}.mp3"
            
            print(f"📤 Uploading MP3 to blob storage as: {test_filename}")
            
            status_code, error = await blob_storage.aupload_bytes(
                file_name=test_filename,
                data=audio_bytes,
                file_type=".mp3"
            )
            
            if status_code == 201:
                print("✅ Upload successful!")
                
                # Generate SAS URL
                sas_url = await blob_storage.get_blob_sas_url(test_filename, expiry_hours=1)
                print(f"🔗 SAS URL: {sas_url[:100]}...")
                
                # Test the URL
                import requests
                response = requests.head(sas_url, timeout=10)
                print(f"📊 HTTP Status: {response.status_code}")
                print(f"📊 Content-Type: {response.headers.get('Content-Type', 'Not Set')}")
                print(f"📊 Content-Length: {response.headers.get('Content-Length', 'Unknown')}")
                
                if response.status_code == 200 and response.headers.get('Content-Type') == 'audio/mpeg':
                    print("🎉 SUCCESS! MP3 TTS is working correctly for QikChat!")
                    return True
                else:
                    print("❌ URL test failed")
                    return False
            else:
                print(f"❌ Upload failed: {error}")
                return False
        else:
            print("❌ Failed to generate audio")
            return False
            
    except Exception as e:
        print(f"❌ Error in MP3 TTS test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(test_mp3_tts())
    if result:
        print("\n🎉 MP3 TTS integration is ready for QikChat!")
    else:
        print("\n💥 MP3 TTS test failed!")