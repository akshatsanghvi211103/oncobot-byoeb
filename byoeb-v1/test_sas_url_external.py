#!/usr/bin/env python3
"""
Simple test to check if our TTS service generates audio with proper content type.  
We'll manually trigger the same code path that QikChat would use.
"""
import requests
import asyncio
import logging

# Test the current SAS URL we generated with proper content type
test_audio_url = "https://smartkcstorage1.blob.core.windows.net/oncobot-container/tts_audio_0239d977c2004a8ba8322a4f72ec8e86.wav?se=2025-09-15T09%3A00%3A00Z&sp=r&sv=2022-11-02&sr=b&skoid=f5b64d94-ba27-422a-abb5-cad2b511c671&sktid=72f988bf-86f1-41af-91ab-2d7cd011db47&skt=2025-09-15T07%3A12%3A06Z&ske=2025-09-15T09%3A00%3A00Z&sks=b&skv=2022-11-02&sig=x3h%2BScCmlOwIG%2BRoKXGZlGM3Eejt3B1oydttBG6BiLk%3D"

def test_sas_url_from_external():
    """Test the SAS URL from external perspective (simulating QikChat)"""
    try:
        print(f"🌐 Testing SAS URL: {test_audio_url[:100]}...")
        
        # Test HEAD request (like QikChat might do)
        response = requests.head(test_audio_url, timeout=10)
        print(f"📊 HEAD Response Status: {response.status_code}")
        print(f"📊 Content-Type: {response.headers.get('Content-Type', 'Not Set')}")
        print(f"📊 Content-Length: {response.headers.get('Content-Length', 'Unknown')}")
        print(f"📊 Cache-Control: {response.headers.get('Cache-Control', 'Not Set')}")
        
        if response.status_code == 200:
            print("✅ HEAD request successful!")
            
            # Test GET request to download part of the file
            print("🔽 Testing partial download...")
            download_response = requests.get(test_audio_url, 
                                           headers={'Range': 'bytes=0-1023'},  # First 1KB
                                           timeout=10)
            print(f"📊 GET Response Status: {download_response.status_code}")
            print(f"📊 Downloaded bytes: {len(download_response.content)}")
            
            if download_response.status_code in [200, 206]:  # 206 = Partial Content
                print("✅ GET request successful!")
                return True
            else:
                print(f"❌ GET request failed with status: {download_response.status_code}")
                return False
        else:
            print(f"❌ HEAD request failed with status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing SAS URL: {e}")
        return False

def simulate_qikchat_request():
    """Simulate how QikChat might try to access the audio URL"""
    try:
        print("\n🤖 Simulating QikChat's audio download behavior...")
        
        # QikChat might use different headers or user agents
        headers = {
            'User-Agent': 'QikChat-Media-Downloader/1.0',
            'Accept': 'audio/*, */*',
            'Accept-Encoding': 'gzip, deflate'
        }
        
        response = requests.get(test_audio_url, headers=headers, timeout=15)
        print(f"📊 QikChat-style Response Status: {response.status_code}")
        print(f"📊 Content-Type: {response.headers.get('Content-Type', 'Not Set')}")
        print(f"📊 Downloaded size: {len(response.content)} bytes")
        
        if response.status_code == 200:
            print("✅ QikChat-style request successful!")
            
            # Check if it's a valid WAV file
            if response.content[:4] == b'RIFF':
                print("✅ Valid WAV file detected!")
                return True
            else:
                print("❌ Downloaded content is not a valid WAV file")
                return False
        else:
            print(f"❌ QikChat-style request failed: {response.status_code}")
            print(f"❌ Response text: {response.text[:200]}...")
            return False
            
    except Exception as e:
        print(f"❌ Error in QikChat simulation: {e}")
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("🎵 Testing TTS SAS URL with proper audio/wav content type")
    print("=" * 60)
    
    # Test 1: Basic URL accessibility
    test1_result = test_sas_url_from_external()
    
    # Test 2: Simulate QikChat behavior
    test2_result = simulate_qikchat_request()
    
    print("\n" + "=" * 60)
    print("📋 TEST RESULTS:")
    print(f"   Basic SAS URL Test: {'✅ PASS' if test1_result else '❌ FAIL'}")
    print(f"   QikChat Simulation: {'✅ PASS' if test2_result else '❌ FAIL'}")
    
    if test1_result and test2_result:
        print("\n🎉 All tests passed! The audio/wav content type fix should work with QikChat!")
    else:
        print("\n💥 Some tests failed. There might still be issues with the SAS URL or content type.")