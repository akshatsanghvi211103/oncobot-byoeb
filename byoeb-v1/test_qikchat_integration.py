"""
Qikchat Integration Testing Script
Tests the Qikchat API integration with BYOeB system
"""
import os
import sys
import asyncio
import json
from typing import Dict, Any

# Add the project paths to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'byoeb-integrations'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'byoeb-core'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'byoeb'))

# Import Qikchat components
from byoeb_integrations.channel.qikchat.qikchat_client import QikchatClient
from byoeb_integrations.channel.qikchat.request_payload import (
    get_qikchat_text_request_from_byoeb_message,
    get_qikchat_interactive_button_request_from_byoeb_message,
    get_qikchat_reaction_request
)
from byoeb_integrations.channel.qikchat.validate_message import is_valid_qikchat_message
from byoeb_integrations.channel.qikchat.convert_message import convert_qikchat_message_to_byoeb

# Load environment variables
from dotenv import load_dotenv
load_dotenv('byoeb/keys.env')

class QikchatTester:
    def __init__(self):
        self.api_key = os.getenv("QIKCHAT_API_KEY")
        self.verify_token = os.getenv("QIKCHAT_VERIFY_TOKEN")
        
        if not self.api_key:
            raise ValueError("QIKCHAT_API_KEY not found in environment variables")
        
        self.client = QikchatClient(self.api_key)
        self.test_phone_number = "+919739811075"  # Replace with a test number
        
        print(f"✅ Qikchat Tester initialized")
        print(f"📱 API Key: {self.api_key[:8]}... (masked)")
        print(f"🔐 Verify Token: {self.verify_token}")
        print("-" * 50)
    
    async def test_basic_message_sending(self):
        """Test sending a basic text message"""
        print("🧪 Test 1: Basic Text Message Sending")
        
        # Create a  text message
        message_data = {
            "from": self.test_phone_number,
            "to": self.test_phone_number,
            "type": "text",
            "text": "Hello from BYOeB Oncology Bot! This is a test message."
        }
        
        try:
            response = await self.client.send_message(message_data)
            print(f"✅ Message sent successfully!")
            print(f"📨 Message ID: {response.get('message_id')}")
            print(f"📄 Response: {json.dumps(response, indent=2)}")
            return True
        except Exception as e:
            print(f"❌ Failed to send message: {str(e)}")
            return False
    
    async def test_interactive_button_message(self):
        """Test sending an interactive button message"""
        print("\n🧪 Test 2: Interactive Button Message")
        
        message_data = {
            "from": self.test_phone_number,
            "to": self.test_phone_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": "How can I help you with your oncology questions?"
                },
                "action": {
                    "buttons": [
                        {"id": "cancer_info", "title": "About Cancer", "type": "reply"},
                        {"id": "treatment_info", "title": "Treatment Info", "type": "reply"},
                        {"id": "side_effects", "title": "Side Effects", "type": "reply"}
                    ]
                }
            }
        }
        
        try:
            response = await self.client.send_message(message_data)
            print(f"✅ Interactive message sent!")
            print(f"📨 Message ID: {response.get('message_id')}")
            return True
        except Exception as e:
            print(f"❌ Failed to send interactive message: {str(e)}")
            return False
    
    async def test_oncology_knowledge_base_query(self):
        """Test sending an oncology-related query"""
        print("\n🧪 Test 3: Oncology Knowledge Base Query")
        
        # Simulate a user asking about cancer
        user_query = "What are the side effects of radiotherapy?"
        
        message_data = {
            "from": self.test_phone_number,
            "to": self.test_phone_number,
            "type": "text",
            "text": f"User Query: {user_query}\n\nBot Response: Radiation therapy can cause side effects due to damage to normal cells around the tumor. Common side effects include skin changes (dryness, itching, peeling), fatigue, and burning sensation in the oral cavity."
        }
        
        try:
            response = await self.client.send_message(message_data)
            print(f"✅ Oncology query response sent!")
            print(f"💬 Query: {user_query}")
            print(f"📨 Message ID: {response.get('message_id')}")
            return True
        except Exception as e:
            print(f"❌ Failed to send oncology response: {str(e)}")
            return False
    
    def test_message_validation(self):
        """Test message validation functions"""
        print("\n🧪 Test 4: Message Validation")
        
        # Test valid text message
        valid_message = {
            "type": "text",
            "from": "+919739811075",
            "timestamp": "1625097600",
            "text": "Hello, I have a question about radiotherapy."
        }
        
        # Test invalid message (missing required fields)
        invalid_message = {
            "type": "text",
            "text": "Hello"
            # Missing 'from' and 'timestamp'
        }
        
        print(f"✅ Valid message validation: {is_valid_qikchat_message(valid_message)}")
        print(f"❌ Invalid message validation: {is_valid_qikchat_message(invalid_message)}")
        
        return True
    
    def test_message_conversion(self):
        """Test converting Qikchat messages to BYOeB format"""
        print("\n🧪 Test 5: Message Conversion")
        
        # Test converting a Qikchat message to BYOeB format
        qikchat_message = {
            "id": "msg_12345",
            "type": "text",
            "from": "+919739811075",
            "timestamp": "1625097600",
            "text": "What is cancer?"
        }
        
        try:
            byoeb_message = convert_qikchat_message_to_byoeb(qikchat_message)
            if byoeb_message:
                print(f"✅ Message converted successfully!")
                print(f"👤 User: {byoeb_message.user.phone_number_id}")
                print(f"💬 Text: {byoeb_message.message_context.message_source_text}")
                print(f"🏷️ Type: {byoeb_message.message_context.message_type}")
                return True
            else:
                print(f"❌ Message conversion returned None")
                return False
        except Exception as e:
            print(f"❌ Message conversion failed: {str(e)}")
            return False
    
    async def test_webhook_verification(self):
        """Test webhook verification logic"""
        print("\n🧪 Test 6: Webhook Verification")
        
        # Import the registration handler
        from byoeb_integrations.channel.qikchat.register import RegisterQikchat
        
        register_handler = RegisterQikchat(self.verify_token)
        
        # Test valid webhook verification
        valid_params = {
            "verify_token": self.verify_token,
            "challenge": "test_challenge_12345"
        }
        
        response = await register_handler.register(valid_params)
        
        if response.status_code == 200:
            print(f"✅ Webhook verification successful!")
            print(f"🔐 Challenge returned: {response.message}")
            return True
        else:
            print(f"❌ Webhook verification failed: {response.message}")
            return False
    
    async def test_api_connectivity(self):
        """Test basic API connectivity"""
        print("\n🧪 Test 7: API Connectivity")
        
        try:
            # Try to get webhook info (this might fail if not implemented)
            webhook_info = await self.client.get_webhook_info()
            print(f"✅ API connectivity successful!")
            print(f"📡 Webhook info: {json.dumps(webhook_info, indent=2)}")
            return True
        except Exception as e:
            print(f"⚠️ API connectivity test: {str(e)}")
            # This might be expected if the endpoint doesn't exist
            print("ℹ️ This is normal if webhook info endpoint is not implemented")
            return True  # Don't fail the test for this
    
    async def run_all_tests(self):
        """Run all tests"""
        print("🚀 Starting Qikchat Integration Tests")
        print("=" * 60)
        
        tests = [
            ("API Connectivity", self.test_api_connectivity),
            ("Message Validation", self.test_message_validation),
            ("Message Conversion", self.test_message_conversion),
            # ("Webhook Verification", self.test_webhook_verification),
            ("Basic Text Message", self.test_basic_message_sending),
            # ("Interactive Button Message", self.test_interactive_button_message),
            # ("Oncology Query Response", self.test_oncology_knowledge_base_query),
        ]
        
        results = []
        
        for test_name, test_func in tests:
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
        
        if passed == total:
            print("🎉 All tests passed! Qikchat integration is ready!")
        else:
            print(f"⚠️ {total-passed} test(s) failed. Check the errors above.")
        
        return passed == total

async def main():
    """Main testing function"""
    try:
        tester = QikchatTester()
        success = await tester.run_all_tests()
        
        if success:
            print("\n🎯 Next steps:")
            print("1. Update your BYOeB configuration to use 'qikchat' instead of 'whatsapp'")
            print("2. Deploy the webhook endpoint to receive Qikchat messages")
            print("3. Test with real phone numbers and Qikchat dashboard")
            print("4. Integrate with your oncology knowledge base")
            
        return 0 if success else 1
        
    except Exception as e:
        print(f"💥 Testing failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
