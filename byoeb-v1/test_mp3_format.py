#!/usr/bin/env python3
"""
Quick test of the fixed MP3 format string.
"""
import azure.cognitiveservices.speech as speechsdk

def test_format_name():
    """Test if the MP3 format name is correct"""
    try:
        # Test if the format exists
        format_val = speechsdk.SpeechSynthesisOutputFormat.Audio48Khz128KbitRateMonoMp3
        print(f"✅ Format found: {format_val}")
        return True
    except AttributeError as e:
        print(f"❌ Format not found: {e}")
        
        # List available MP3 formats
        print("Available MP3 formats:")
        for attr_name in dir(speechsdk.SpeechSynthesisOutputFormat):
            if 'Mp3' in attr_name and not attr_name.startswith('_'):
                print(f"  - {attr_name}")
        return False

if __name__ == "__main__":
    test_format_name()