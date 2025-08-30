#!/usr/bin/env python3
"""
Simple test to verify KB search connectivity and TRAPI consumer functionality
"""
import asyncio
import requests
import json
from datetime import datetime

# Test webhook endpoint
WEBHOOK_URL = "http://localhost:5000/webhook/whk"

async def test_webhook_kb_search():
    """Send a test message to the webhook to trigger KB search"""
    
    # Sample message that should trigger KB search
    test_message = {
        "user": {
            "user_id": "test_user_123",
            "user_name": "Test User",
            "phone_number_id": "+1234567890"
        },
        "message_context": {
            "message_id": f"test_{int(datetime.now().timestamp())}",
            "message_source_text": "What is cancer?",
            "message_english_text": "",
            "additional_info": {}
        },
        "reply_context": {
            "additional_info": {}
        },
        "cross_conversation_id": f"test_conv_{int(datetime.now().timestamp())}"
    }
    
    print("🧪 Testing KB Search via Webhook")
    print("=" * 50)
    print(f"📤 Sending test message: {test_message['message_context']['message_source_text']}")
    
    try:
        response = requests.post(
            WEBHOOK_URL,
            json=test_message,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"📨 Response Status: {response.status_code}")
        print(f"📝 Response Text: {response.text}")
        
        if response.status_code == 200:
            print("✅ Webhook call successful!")
            print("📊 Check the terminal output above for KB search results and TRAPI response generation")
        else:
            print(f"❌ Webhook call failed with status {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed - make sure the webhook server is running on http://localhost:5000")
        print("💡 Start the server with: python -m byoeb.chat_app.run")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_webhook_kb_search())
