#!/usr/bin/env python3
"""
Test Qikchat with proper template message format
"""

import asyncio
import aiohttp
import json

async def test_template_message():
    api_key = "04zg-Ir9t-kfaZ"
    base_url = "https://api.qikchat.in/v1"
    
    headers = {
        "QIKCHAT-API-KEY": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Try a proper template message format
    template_messages = [
        # Basic template without components
        {
            "to_contact": "919739811075",
            "type": "template",
            "template": {
                "name": "hello_world",
                "language": {
                    "code": "en"
                }
            }
        },
        # Template with components
        {
            "to_contact": "919739811075", 
            "type": "template",
            "template": {
                "name": "hello_world",
                "language": {
                    "code": "en"
                },
                "components": []
            }
        },
        # Simple text with session message flag
        {
            "to_contact": "919739811075",
            "type": "text",
            "text": {
                "body": "Hello! This is a test message from BYOeB Oncology Bot."
            },
            "messaging_product": "whatsapp"
        }
    ]
    
    async with aiohttp.ClientSession() as session:
        for i, template_data in enumerate(template_messages, 1):
            print(f"\n🧪 Template Test {i}:")
            print(f"📦 Payload: {json.dumps(template_data, indent=2)}")
            
            try:
                async with session.post(
                    f"{base_url}/messages",
                    headers=headers,
                    json=template_data
                ) as response:
                    response_data = await response.json()
                    
                    if response.status == 200:
                        message_id = response_data.get("data", [{}])[0].get("id", "Unknown")
                        print(f"✅ Template queued: {message_id}")
                    else:
                        print(f"❌ Failed: {response.status}")
                        print(f"📄 Response: {json.dumps(response_data, indent=2)}")
                        
            except Exception as e:
                print(f"❌ Error: {str(e)}")

# Also test with a different phone number format
async def test_different_number():
    """Test with your own number or a known WhatsApp number"""
    api_key = "04zg-Ir9t-kfaZ"
    base_url = "https://api.qikchat.in/v1"
    
    headers = {
        "QIKCHAT-API-KEY": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Test message to a different number (replace with your WhatsApp number)
    print(f"\n📱 Testing with Different Number...")
    print("💡 Replace this with your own WhatsApp number for testing")
    
    test_message = {
        "to_contact": "919739811075",  # Replace with your number
        "type": "text",
        "text": {
            "body": "Test message to verify delivery"
        }
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{base_url}/messages",
                headers=headers,
                json=test_message
            ) as response:
                response_data = await response.json()
                
                if response.status == 200:
                    print("✅ Message queued successfully")
                    print("🔍 Check your WhatsApp to see if you received it")
                else:
                    print(f"❌ Failed: {response.status} - {response_data}")
                    
        except Exception as e:
            print(f"❌ Error: {str(e)}")

async def main():
    print("🧪 Qikchat Template & Number Testing")
    print("=" * 50)
    
    await test_template_message()
    await test_different_number()
    
    print("\n" + "=" * 50)
    print("💡 Troubleshooting Tips:")
    print("1. Replace the phone number with your own WhatsApp number")
    print("2. Check if the recipient number actually has WhatsApp installed")
    print("3. For business numbers, templates might be required for first contact")
    print("4. Check your Qikchat account status and credits in the dashboard")
    print("5. Verify your WhatsApp Business account is approved")

if __name__ == "__main__":
    asyncio.run(main())
