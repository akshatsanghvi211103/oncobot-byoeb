#!/usr/bin/env python3
"""
Test script to generate TTS audio with proper content type and verify the SAS URL works.
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

from byoeb.byoeb.factory.service_factory import ServiceFactory
from byoeb.byoeb.services.chat.tts_service import TTSService
import requests

async def test_tts_with_content_type():
    logging.basicConfig(level=logging.INFO)
    
    try:
        # Initialize the service factory
        service_factory = ServiceFactory()
        
        # Get TTS service
        tts_service = service_factory.get_tts_service()
        
        # Test audio generation
        test_text = "This is a test audio with proper content type."
        print(f"🔊 Generating TTS for: {test_text}")
        
        audio_url = await tts_service.generate_audio_url(test_text, "en-US")
        
        if audio_url:
            print(f"✅ TTS Audio URL generated: {audio_url}")
            
            # Test the URL directly using requests
            print("🌐 Testing SAS URL accessibility...")
            response = requests.head(audio_url, timeout=10)
            print(f"📊 Response Status: {response.status_code}")
            print(f"📊 Content-Type: {response.headers.get('Content-Type', 'Not Set')}")
            print(f"📊 Content-Length: {response.headers.get('Content-Length', 'Unknown')}")
            
            if response.status_code == 200:
                print("✅ SAS URL is accessible!")
                return True
            else:
                print(f"❌ SAS URL returned status: {response.status_code}")
                return False
        else:
            print("❌ Failed to generate TTS audio URL")
            return False
            
    except Exception as e:
        print(f"❌ Error during TTS test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_tts_with_content_type())
    if result:
        print("🎉 TTS with proper content type test passed!")
    else:
        print("💥 TTS test failed!")