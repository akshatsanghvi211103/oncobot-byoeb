#!/usr/bin/env python3
"""
Quick test of TTS service with the fixed MP3 format.
"""
import asyncio
import sys
import os

# Add paths for imports
sys.path.append('.')
sys.path.append('byoeb')
sys.path.append('byoeb-core') 
sys.path.append('byoeb-integrations')

async def test_tts_mp3_generation():
    """Test TTS MP3 generation with the fixed format"""
    try:
        from byoeb_integrations.translators.speech.azure.async_azure_speech_translator import AsyncAzureSpeechTranslator
        from azure.identity import DefaultAzureCredential
        
        print("🎵 Testing TTS MP3 generation with fixed format...")
        
        # Create credentials
        credential = DefaultAzureCredential()
        def token_provider():
            token = credential.get_token("https://cognitiveservices.azure.com/.default")
            return token.token
        
        # Initialize speech translator
        speech_translator = AsyncAzureSpeechTranslator(
            region="eastus",
            resource_id="/subscriptions/cef13953-6a76-4434-9a65-1d95481f83c7/resourceGroups/smartkc/providers/Microsoft.CognitiveServices/accounts/smartkc-cs-speech",
            token_provider=token_provider,
            speech_voice="female",
            country_code="IN"
        )
        
        # Test text
        test_text = "This is a test of the fixed MP3 format for QikChat integration."
        
        print(f"🎙️ Generating MP3 audio for: '{test_text}'")
        
        # Generate MP3 audio with fixed format
        audio_bytes = await speech_translator.atext_to_speech(
            input_text=test_text,
            source_language="en"
        )
        
        if audio_bytes and len(audio_bytes) > 0:
            print(f"✅ Generated {len(audio_bytes)} bytes of MP3 audio")
            
            # Check if it's a valid MP3
            if audio_bytes[:3] == b'ID3' or (len(audio_bytes) > 2 and audio_bytes[0] == 0xFF and (audio_bytes[1] & 0xE0) == 0xE0):
                print("✅ Valid MP3 format detected!")
                return True
            else:
                print(f"❓ Unexpected format. First bytes: {audio_bytes[:10]}")
                return False
        else:
            print("❌ No audio bytes generated")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_tts_mp3_generation())
    if result:
        print("🎉 MP3 TTS generation is working correctly!")
    else:
        print("💥 MP3 TTS generation failed!")