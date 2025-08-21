#!/usr/bin/env python3
"""
Qikchat API Diagnostic Tool
Helps identify why messages are failing to deliver
"""

import asyncio
import aiohttp
import json
import os

class QikchatDiagnostic:
    def __init__(self):
        # Get API key directly (since we know it from the test file)
        self.api_key = "04zg-Ir9t-kfaZ"  # From your keys.env file
        
        if not self.api_key:
            raise ValueError("API key not provided")
        
        self.base_url = "https://api.qikchat.in/v1"
        self.headers = {
            "QIKCHAT-API-KEY": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        print("🔍 Qikchat Diagnostic Tool")
        print("=" * 50)
        print(f"🔑 API Key: {self.api_key[:8]}...")
        print(f"🌐 Base URL: {self.base_url}")
        print()

    async def check_account_status(self):
        """Check account status and credits"""
        print("📊 Checking Account Status...")
        
        try:
            async with aiohttp.ClientSession() as session:
                # Try to get account info
                endpoints_to_try = [
                    "/account",
                    "/account/info", 
                    "/me",
                    "/profile",
                    "/balance"
                ]
                
                for endpoint in endpoints_to_try:
                    url = f"{self.base_url}{endpoint}"
                    try:
                        async with session.get(url, headers=self.headers) as response:
                            if response.status == 200:
                                data = await response.json()
                                print(f"✅ Account Info ({endpoint}): {json.dumps(data, indent=2)}")
                                return data
                            else:
                                print(f"❌ {endpoint}: {response.status}")
                    except Exception as e:
                        print(f"❌ {endpoint}: {str(e)}")
                
                print("⚠️ Could not retrieve account information")
                return None
                
        except Exception as e:
            print(f"❌ Account check failed: {str(e)}")
            return None

    async def test_phone_number_formats(self, base_number="919739811075"):
        """Test different phone number formats"""
        print("📱 Testing Phone Number Formats...")
        
        # Different formats to try
        formats = [
            base_number,                    # 919739811075
            f"+{base_number}",             # +919739811075
            base_number[2:],               # 9739811075 (without country code)
            f"91{base_number[2:]}",        # 919739811075 (explicit country code)
            f"+91{base_number[2:]}",       # +919739811075
        ]
        
        test_message = {
            "type": "text",
            "text": {
                "body": "🔍 Diagnostic test message - please ignore"
            }
        }
        
        results = []
        
        async with aiohttp.ClientSession() as session:
            for i, phone_format in enumerate(formats, 1):
                print(f"\n📞 Test {i}: {phone_format}")
                
                message_data = {
                    "to_contact": phone_format,
                    **test_message
                }
                
                try:
                    async with session.post(
                        f"{self.base_url}/messages",
                        headers=self.headers,
                        json=message_data
                    ) as response:
                        response_data = await response.json()
                        
                        if response.status == 200:
                            message_id = response_data.get("data", [{}])[0].get("id", "Unknown")
                            print(f"✅ Queued successfully: {message_id}")
                            results.append({
                                "format": phone_format,
                                "status": "queued",
                                "message_id": message_id,
                                "response": response_data
                            })
                        else:
                            print(f"❌ Failed: {response.status} - {response_data}")
                            results.append({
                                "format": phone_format,
                                "status": "failed",
                                "error": response_data
                            })
                            
                except Exception as e:
                    print(f"❌ Error: {str(e)}")
                    results.append({
                        "format": phone_format,
                        "status": "error",
                        "error": str(e)
                    })
        
        return results

    async def check_message_status(self, message_id):
        """Check the status of a specific message"""
        print(f"\n📩 Checking Message Status: {message_id}")
        
        endpoints_to_try = [
            f"/messages/{message_id}",
            f"/messages/{message_id}/status",
            f"/message/{message_id}",
            "/messages"  # List all messages
        ]
        
        async with aiohttp.ClientSession() as session:
            for endpoint in endpoints_to_try:
                url = f"{self.base_url}{endpoint}"
                try:
                    async with session.get(url, headers=self.headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            print(f"✅ Status from {endpoint}:")
                            print(json.dumps(data, indent=2))
                            return data
                        else:
                            print(f"❌ {endpoint}: {response.status}")
                except Exception as e:
                    print(f"❌ {endpoint}: {str(e)}")
        
        return None

    async def test_template_message(self):
        """Test with a template message if required"""
        print("\n📋 Testing Template Message...")
        
        # Some WhatsApp Business APIs require templates for first contact
        template_message = {
            "to_contact": "919739811075",
            "type": "template",
            "template": {
                "name": "hello_world",  # Common default template
                "language": {
                    "code": "en_US"
                }
            }
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.base_url}/messages",
                    headers=self.headers,
                    json=template_message
                ) as response:
                    response_data = await response.json()
                    
                    if response.status == 200:
                        print("✅ Template message queued successfully")
                        return response_data
                    else:
                        print(f"❌ Template message failed: {response.status} - {response_data}")
                        return None
                        
            except Exception as e:
                print(f"❌ Template message error: {str(e)}")
                return None

    async def run_full_diagnostic(self):
        """Run complete diagnostic"""
        print("🚀 Starting Full Diagnostic...")
        print("=" * 50)
        
        # 1. Check account status
        account_info = await self.check_account_status()
        
        # 2. Test phone number formats
        format_results = await self.test_phone_number_formats()
        
        # 3. Test template message
        template_result = await self.test_template_message()
        
        # 4. Check status of a recent message if available
        if format_results:
            for result in format_results:
                if result.get("status") == "queued" and result.get("message_id"):
                    await asyncio.sleep(2)  # Wait a bit for processing
                    await self.check_message_status(result["message_id"])
                    break
        
        # 5. Summary and recommendations
        print("\n" + "=" * 50)
        print("📋 DIAGNOSTIC SUMMARY")
        print("=" * 50)
        
        print("\n💡 Possible Solutions:")
        print("1. ✅ Ensure the recipient has WhatsApp installed")
        print("2. 📱 Try different phone number formats")
        print("3. 🔐 Verify your WhatsApp Business account is approved")
        print("4. 💳 Check if you have sufficient credits/balance")
        print("5. 📋 You might need to use message templates for first contact")
        print("6. ⏰ Check rate limits - you might be sending too fast")
        print("7. 🌍 Ensure the country code is correct for the region")
        
        print("\n🔗 Next Steps:")
        print("- Check your Qikchat dashboard for detailed error messages")
        print("- Verify the recipient phone number is active on WhatsApp")
        print("- Contact Qikchat support if the issue persists")

async def main():
    try:
        diagnostic = QikchatDiagnostic()
        await diagnostic.run_full_diagnostic()
    except Exception as e:
        print(f"❌ Diagnostic failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
