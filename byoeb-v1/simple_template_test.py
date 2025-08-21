#!/usr/bin/env python3
"""
Simple Qikchat Template Message Test
Tests template messages for 24+ hour re-engagement
"""

import asyncio
import aiohttp
import json

async def test_single_template():
    """Test one template message only to minimize API calls"""
    api_key = "04zg-Ir9t-kfaZ"
    base_url = "https://api.qikchat.in/v1"
    
    headers = {
        "QIKCHAT-API-KEY": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    print("🧪 Testing Template Message for Re-engagement")
    print("=" * 50)
    
    # First, let's check what templates are available
    print("📋 Checking available templates...")
    
    async with aiohttp.ClientSession() as session:
        # Check templates endpoint
        try:
            async with session.get(f"{base_url}/templates", headers=headers) as response:
                if response.status == 200:
                    templates_data = await response.json()
                    print("✅ Available templates:")
                    print(json.dumps(templates_data, indent=2))
                else:
                    print(f"❌ Templates endpoint: {response.status}")
        except Exception as e:
            print(f"❌ Templates check error: {str(e)}")
        
        # Try with language string and empty components
        print("\n🎯 Testing Template with Language + Empty Components:")
        
        template_complete = {
            "to_contact": "919739811075",
            "type": "template", 
            "template": {
                "name": "testing",
                "language": "en",
                "components": []  # Empty components array
            }
        }
        
        print(f"\n📦 Complete Template Format:")
        print(json.dumps(template_complete, indent=2))
        
        try:
            async with session.post(
                f"{base_url}/messages",
                headers=headers,
                json=template_complete
            ) as response:
                response_data = await response.json()
                
                print(f"📡 Response Status: {response.status}")
                print(f"📄 Response: {json.dumps(response_data, indent=2)}")
                
                if response.status == 200:
                    message_id = response_data.get("data", [{}])[0].get("id", "Unknown")
                    print(f"✅ COMPLETE TEMPLATE QUEUED: {message_id}")
                    print("🎉 SUCCESS! This template should work for re-engagement!")
                    print("📱 Check your dashboard - this message should DELIVER!")
                else:
                    print(f"❌ Complete template failed: {response.status}")
                    
        except Exception as e:
            print(f"❌ Complete template error: {str(e)}")

    print("\n" + "=" * 50)
    print("💡 About WhatsApp Business API Costs:")
    print("• Template messages: Usually charged per message")
    print("• Free-form messages: Often free within 24-hour window")
    print("• Check your Qikchat dashboard for exact pricing")
    print("\n🎯 Solution for your use case:")
    print("1. Use templates for initial contact or re-engagement (24+ hours)")
    print("2. Once user replies, you have 24 hours for free-form messages")
    print("3. Create approved templates in Qikchat dashboard for common scenarios")

if __name__ == "__main__":
    asyncio.run(test_single_template())
