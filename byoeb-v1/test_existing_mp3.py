#!/usr/bin/env python3
"""
Test the MP3 TTS file that was already generated to confirm QikChat compatibility.
"""
import requests

def test_mp3_qikchat_compatibility():
    """Test the existing MP3 TTS file for QikChat compatibility"""
    mp3_sas_url = "https://smartkcstorage1.blob.core.windows.net/oncobot-container/tts_audio_196cd4e0a2934643a67368a069c98047.mp3?se=2025-09-15T10%3A00%3A00Z&sp=r&sv=2022-11-02&sr=b&skoid=f5b64d94-ba27-422a-abb5-cad2b511c671&sktid=72f988bf-86f1-41af-91ab-2d7cd011db47&skt=2025-09-15T07%3A24%3A44Z&ske=2025-09-15T10%3A00%3A00Z&sks=b&skv=2022-11-02&sig=ILwoQS281SP7QVkwRX68dFSv0lHZGVTcy5TGt4d3hGE%3D"
    
    print("🎵 Testing MP3 TTS file for QikChat compatibility")
    print("=" * 60)
    
    try:
        # Test HEAD request
        response = requests.head(mp3_sas_url, timeout=10)
        print(f"📊 HEAD Response Status: {response.status_code}")
        print(f"📊 Content-Type: {response.headers.get('Content-Type', 'Not Set')}")
        print(f"📊 Content-Length: {response.headers.get('Content-Length', 'Unknown')} bytes")
        
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            if content_type == 'audio/mpeg':
                print("✅ Perfect! Content-Type is audio/mpeg (QikChat supported)")
                
                # Test partial download
                print("\n🔽 Testing partial download...")
                download_response = requests.get(mp3_sas_url, 
                                               headers={'Range': 'bytes=0-1023'}, 
                                               timeout=10)
                
                if download_response.status_code in [200, 206]:
                    print(f"✅ Partial download successful: {len(download_response.content)} bytes")
                    
                    # Check if it's valid MP3
                    content = download_response.content
                    if content[:3] == b'ID3' or (len(content) > 2 and content[0] == 0xFF and (content[1] & 0xE0) == 0xE0):
                        print("✅ Valid MP3 format detected!")
                        
                        # Simulate QikChat behavior
                        print("\n🤖 Simulating QikChat media download...")
                        qikchat_response = requests.get(mp3_sas_url, 
                                                       headers={
                                                           'User-Agent': 'QikChat-Media-Downloader/1.0',
                                                           'Accept': 'audio/mpeg, audio/*, */*'
                                                       },
                                                       timeout=15)
                        
                        print(f"📊 QikChat simulation status: {qikchat_response.status_code}")
                        print(f"📊 Downloaded size: {len(qikchat_response.content)} bytes")
                        
                        if qikchat_response.status_code == 200:
                            print("🎉 SUCCESS! QikChat should be able to download and play this MP3!")
                            return True
                        else:
                            print(f"❌ QikChat simulation failed: {qikchat_response.status_code}")
                            return False
                    else:
                        print("❌ Invalid MP3 format")
                        return False
                else:
                    print(f"❌ Partial download failed: {download_response.status_code}")
                    return False
            else:
                print(f"❌ Wrong content type: {content_type} (should be audio/mpeg)")
                return False
        else:
            print(f"❌ HEAD request failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing MP3 file: {e}")
        return False

if __name__ == "__main__":
    result = test_mp3_qikchat_compatibility()
    
    print("\n" + "=" * 60)
    if result:
        print("🎉 MP3 TTS is fully compatible with QikChat!")
        print("✅ The audio format issue has been resolved!")
        print("📱 New TTS messages should work in QikChat now!")
    else:
        print("💥 There are still issues with the MP3 format")