#!/usr/bin/env python3
"""
Test the updated SAS generation with compatible service version
"""
import requests

# Test the specific URL pattern from our updated system
def test_updated_sas():
    """Test if the updated SAS generation works better"""
    print("🔧 Testing updated SAS generation with service version 2022-11-02")
    print("=" * 60)
    
    # Since we can't easily generate a new SAS programmatically without running the full system,
    # let's simulate what QikChat might be doing that causes the 403
    
    # Test with different User-Agent strings
    test_url = "https://smartkcstorage1.blob.core.windows.net/oncobot-container/tts_audio_d6c7c5c822d1407080bcdb3d0ba06c76.mp3?se=2025-09-15T10%3A30%3A00Z&sp=r&sv=2022-11-02&sr=b&skoid=f5b64d94-ba27-422a-abb5-cad2b511c671&sktid=72f988bf-86f1-41af-91ab-2d7cd011db47&skt=2025-09-15T07%3A40%3A03Z&ske=2025-09-15T10%3A30%3A00Z&sks=b&skv=2022-11-02&sig=xRQwaEUVcHA%2Feuw8FMrC4W8WXLCmSIfC%2Bqho2LL47Js%3D"
    
    user_agents = [
        "Mozilla/5.0 (compatible; QikChat/1.0)",
        "QikChat-Media-Downloader/1.0", 
        "python-requests/2.28.1",
        "curl/7.68.0",
        "",  # No user agent
    ]
    
    for i, ua in enumerate(user_agents, 1):
        print(f"\n🧪 Test {i}: User-Agent = '{ua or 'None'}'")
        try:
            headers = {}
            if ua:
                headers['User-Agent'] = ua
                
            response = requests.head(test_url, headers=headers, timeout=10)
            print(f"   Status: {response.status_code}")
            if response.status_code != 200:
                print(f"   ❌ Failed with {response.status_code}")
            else:
                print(f"   ✅ Success")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # Test with different request methods
    print(f"\n🧪 Testing different HTTP methods:")
    methods = ['HEAD', 'GET']
    for method in methods:
        try:
            if method == 'HEAD':
                response = requests.head(test_url, timeout=10)
            else:
                response = requests.get(test_url, stream=True, timeout=10)
                
            print(f"   {method}: {response.status_code} ({'✅' if response.status_code == 200 else '❌'})")
        except Exception as e:
            print(f"   {method}: Error - {e}")

if __name__ == "__main__":
    test_updated_sas()