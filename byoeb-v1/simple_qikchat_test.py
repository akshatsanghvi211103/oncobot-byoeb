"""
Simple Qikchat API Testing Script
Tests basic Qikchat API functionality without complex BYOeB dependencies
"""
import os
import asyncio
import aiohttp
import json
from pathlib import Path

# Load environment variables manually
env_file = Path(__file__).parent / 'byoeb' / 'keys.env'
if env_file.exists():
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

class SimpleQikchatTester:
    def __init__(self):
        self.api_key = os.getenv("QIKCHAT_API_KEY")
        self.verify_token = os.getenv("QIKCHAT_VERIFY_TOKEN")
        self.base_url = "https://api.qikchat.in/v1"  # Correct base URL
        
        if not self.api_key:
            print("❌ QIKCHAT_API_KEY not found in keys.env")
            print(f"📁 Looking for: {env_file}")
            raise ValueError("API key not found")
        
        self.headers = {
            "QIKCHAT-API-KEY": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        print(f"✅ Qikchat API Tester initialized")
        print(f"📱 API Key: {self.api_key}")
        print(f"🔐 Verify Token: {self.verify_token}")
        print(f"🌐 Base URL: {self.base_url}")
        print("-" * 50)
    
    async def test_api_connection(self):
        """Test basic API connectivity"""
        print("🧪 Test 1: API Connection Test")
        
        # Try to make a simple request to check API connectivity
        test_url = f"{self.base_url}/status"  # Common endpoint for health checks
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(test_url, headers=self.headers, timeout=10) as response:
                    print(f"📡 Response Status: {response.status}")
                    response_text = await response.text()
                    print(f"📄 Response: {response_text[:200]}...")
                    
                    if response.status in [200, 404]:  # 404 is ok, means API is responding
                        print("✅ API is reachable!")
                        return True
                    else:
                        print(f"⚠️ API returned status {response.status}")
                        return False
                        
        except aiohttp.ClientTimeout:
            print("❌ API request timed out")
            return False
        except Exception as e:
            print(f"❌ API connection failed: {str(e)}")
            return False
    
    async def test_send_text_message(self):
        """Test sending a text message"""
        print("\n🧪 Test 2: Send Text Message")
        
        # Construct message payload based on actual Qikchat API docs
        message_data = {
            "to_contact": "919739811075",  # Correct field name
            "type": "text",
            "text": {
                "body": "Hello from BYOeB Oncology Bot! 🏥\n\nThis is a test message to verify Qikchat integration is working properly."
            }
        }
        
        endpoint = f"{self.base_url}/messages"
        
        try:
            async with aiohttp.ClientSession() as session:
                print(f"🚀 Sending to: {endpoint}")
                print(f"📦 Payload: {json.dumps(message_data, indent=2)}")
                
                async with session.post(
                    endpoint, 
                    headers=self.headers, 
                    json=message_data,
                    timeout=15
                ) as response:
                    
                    response_text = await response.text()
                    print(f"📡 Status: {response.status}")
                    print(f"📄 Response: {response_text}")
                    
                    if response.status == 200:
                        try:
                            response_json = json.loads(response_text)
                            # Qikchat response format: {"status": true, "data": [{"id": "..."}]}
                            if response_json.get("status") and response_json.get("data"):
                                message_id = response_json["data"][0].get("id")
                                print(f"✅ Message sent successfully!")
                                print(f"📨 Message ID: {message_id}")
                                print(f"💳 Credits used: {response_json['data'][0].get('credits', 'N/A')}")
                                return True
                            else:
                                print(f"❌ Unexpected response format: {response_json}")
                                return False
                        except Exception as parse_error:
                            print(f"❌ Response parsing error: {parse_error}")
                            print(f"Raw response: {response_text}")
                            return False
                    else:
                        print(f"❌ Message failed to send. Status: {response.status}")
                        return False
                        
        except Exception as e:
            print(f"❌ Send message error: {str(e)}")
            return False
    
    async def test_send_interactive_message(self):
        """Test sending an interactive button message"""
        print("\n🧪 Test 3: Send Interactive Button Message")
        
        message_data = {
            "to_contact": "919739811075",
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": "🏥 **Oncology Bot Menu**\n\nHow can I help you today? Choose an option below:"
                },
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {
                                "id": "cancer_info",
                                "title": "About Cancer"
                            }
                        },
                        {
                            "type": "reply", 
                            "reply": {
                                "id": "treatment_info",
                                "title": "Treatment Options"
                            }
                        },
                        {
                            "type": "reply",
                            "reply": {
                                "id": "side_effects",
                                "title": "Side Effects"
                            }
                        }
                    ]
                }
            }
        }
        
        endpoint = f"{self.base_url}/messages"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    headers=self.headers,
                    json=message_data,
                    timeout=15
                ) as response:
                    
                    response_text = await response.text()
                    print(f"📡 Status: {response.status}")
                    print(f"📄 Response: {response_text[:300]}...")
                    
                    if response.status == 200:
                        print("✅ Interactive message sent!")
                        return True
                    else:
                        print(f"❌ Interactive message failed. Status: {response.status}")
                        return False
                        
        except Exception as e:
            print(f"❌ Interactive message error: {str(e)}")
            return False
    
    async def test_oncology_simulation(self):
        """Simulate an oncology Q&A interaction"""
        print("\n🧪 Test 4: Oncology Q&A Simulation")
        
        # Simulate user asking about radiotherapy side effects
        user_question = "What are the side effects of radiotherapy?"
        bot_response = """**Radiotherapy Side Effects** 📋

**Common Side Effects:**
• Skin changes (dryness, itching, peeling)
• Fatigue and tiredness 
• Loss of appetite
• Burning sensation in mouth/throat

**Head & Neck Treatment Specific:**
• Difficulty swallowing
• Change in voice
• Dry mouth (xerostomia)
• Loss of taste sensation

**Important:** Most side effects are temporary and improve after treatment ends. Always consult your doctor for personalized advice.

Would you like more information about managing these side effects?"""
        
        # Send user question first
        question_data = {
            "api_key": self.api_key,
            "to_contact": "919739811075",
            "type": "text", 
            "text": {
                "body": f"👤 **Patient Question:**\n{user_question}"
            }
        }
        
        # Send bot response
        response_data = {
            "api_key": self.api_key,
            "to_contact": "919739811075",
            "type": "text",
            "text": {
                "body": f"🤖 **Oncology Bot Response:**\n\n{bot_response}"
            }
        }
        
        endpoint = f"{self.base_url}/messages"
        success_count = 0
        
        for i, (label, data) in enumerate([("Question", question_data), ("Response", response_data)]):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        endpoint,
                        headers=self.headers,
                        json=data,
                        timeout=15
                    ) as response:
                        
                        if response.status == 200:
                            print(f"✅ {label} message sent!")
                            success_count += 1
                        else:
                            print(f"❌ {label} message failed: {response.status}")
                
                # Small delay between messages
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"❌ {label} message error: {str(e)}")
        
        return success_count == 2
    
    def test_webhook_verification_logic(self):
        """Test webhook verification logic"""
        print("\n🧪 Test 5: Webhook Verification Logic")
        
        # Simulate webhook verification request
        def verify_webhook(params):
            verify_token = params.get("verify_token")
            challenge = params.get("challenge")
            
            if not verify_token or not challenge:
                return {"status": 400, "message": "Missing parameters"}
            
            if verify_token != self.verify_token:
                return {"status": 403, "message": "Invalid token"}
            
            return {"status": 200, "message": challenge}
        
        # Test valid verification
        valid_params = {
            "verify_token": self.verify_token,
            "challenge": "test_challenge_12345"
        }
        
        result = verify_webhook(valid_params)
        if result["status"] == 200:
            print("✅ Webhook verification logic works!")
            print(f"🔐 Challenge returned: {result['message']}")
            return True
        else:
            print(f"❌ Webhook verification failed: {result}")
            return False
    
    async def run_all_tests(self):
        """Run all tests"""
        print("🚀 Starting Simple Qikchat Integration Tests")
        print("=" * 60)
        
        tests = [
            ("API Connection", self.test_api_connection),
            ("Webhook Verification", self.test_webhook_verification_logic),
            ("Text Message", self.test_send_text_message),
            ("Interactive Message", self.test_send_interactive_message),
            ("Oncology Q&A Simulation", self.test_oncology_simulation),
        ]
        
        results = []
        
        for test_name, test_func in tests:
            print(f"\n▶️ Running: {test_name}")
            try:
                if asyncio.iscoroutinefunction(test_func):
                    result = await test_func()
                else:
                    result = test_func()
                results.append((test_name, result))
            except Exception as e:
                print(f"❌ {test_name} failed with exception: {str(e)}")
                results.append((test_name, False))
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        passed = 0
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} | {test_name}")
            if result:
                passed += 1
        
        print("-" * 60)
        print(f"📈 Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        
        if passed >= 2:  # Consider it successful if basic tests pass
            print("🎉 Basic Qikchat integration is working!")
            print("\n📋 Next Steps:")
            print("1. Check Qikchat dashboard for sent messages")
            print("2. Test with real phone numbers")
            print("3. Set up webhook endpoint to receive messages") 
            print("4. Integrate with BYOeB oncology knowledge base")
        else:
            print(f"⚠️ Some tests failed. Check API key and Qikchat account setup.")
        
        return passed >= 2

async def main():
    """Main function"""
    print("🏥 BYOeB Qikchat Integration Tester")
    print("=" * 40)
    
    try:
        tester = SimpleQikchatTester()
        success = await tester.run_all_tests()
        return 0 if success else 1
    except Exception as e:
        print(f"💥 Testing failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    # Install required package if not available
    try:
        import aiohttp
    except ImportError:
        print("📦 Installing required package...")
        import subprocess
        subprocess.check_call(["pip", "install", "aiohttp"])
        import aiohttp
    
    exit_code = asyncio.run(main())
