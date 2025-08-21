#!/usr/bin/env python3
"""
Template Logic Demo for BYOeB Qikchat Integration
Shows how to implement 24-hour rule without dependencies
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any

class TemplateLogicDemo:
    """
    Demonstrates the 24-hour template logic for Qikchat
    """
    
    def __init__(self):
        # Track last interaction times (in production, store in database)
        self.last_user_interactions = {}
        
    def _is_within_24_hour_window(self, phone_number: str) -> bool:
        """Check if we're within 24-hour window for free-form messages"""
        if phone_number not in self.last_user_interactions:
            return False
            
        last_interaction = self.last_user_interactions[phone_number]
        now = datetime.now()
        time_diff = now - last_interaction
        
        return time_diff < timedelta(hours=24)
    
    def _update_user_interaction_time(self, phone_number: str):
        """Update interaction time when user sends a message"""
        self.last_user_interactions[phone_number] = datetime.now()
        print(f"✅ Updated interaction time for {phone_number}")
    
    def _should_use_template(self, phone_number: str) -> bool:
        """Determine if we should use template (24+ hours since last interaction)"""
        return not self._is_within_24_hour_window(phone_number)
    
    def prepare_oncology_response(
        self,
        user_question: str,
        phone_number: str,
        kb_answer: str
    ) -> Dict[str, Any]:
        """
        Prepare oncology response based on 24-hour rule
        """
        if self._should_use_template(phone_number):
            print(f"🔄 Using TEMPLATE for re-engagement (24+ hours): {phone_number}")
            
            # Template message for re-engagement
            return {
                "to_contact": phone_number,
                "type": "template",
                "template": {
                    "name": "testing",  # Your approved template
                    "language": "en",
                    "components": []
                },
                "cost_estimate": "$0.86",  # Template cost
                "reason": "24+ hours since last interaction"
            }
        else:
            print(f"💬 Using FREE-FORM message (within 24h): {phone_number}")
            
            # Free-form oncology response
            return {
                "to_contact": phone_number,
                "type": "text",
                "text": {
                    "body": f"🏥 **BYOeB Oncology Assistant**\n\n{kb_answer}\n\n📋 Do you have other questions about cancer treatment?"
                },
                "cost_estimate": "$0.00",  # Free within 24h
                "reason": "Within 24-hour window"
            }
    
    async def simulate_oncology_conversation(self):
        """Simulate a complete oncology bot conversation"""
        test_phone = "919739811075"
        
        print("🏥 BYOeB Oncology Bot - Template Logic Demo")
        print("=" * 60)
        
        # Scenario 1: First contact (cold outreach)
        print("\n📱 SCENARIO 1: First Contact (New User)")
        print("-" * 40)
        
        response1 = self.prepare_oncology_response(
            "What are the side effects of radiotherapy?",
            test_phone,
            "Common side effects include skin irritation, fatigue, and localized inflammation. Most are temporary."
        )
        
        print(f"📋 Response Type: {response1['type']}")
        print(f"💰 Cost: {response1['cost_estimate']}")
        print(f"❓ Reason: {response1['reason']}")
        
        # Scenario 2: User replies to template (starts 24h window)
        print("\n📱 SCENARIO 2: User Replies to Template")
        print("-" * 40)
        print("👤 User: 'Thanks! Tell me about radiotherapy side effects'")
        
        # Update interaction time
        self._update_user_interaction_time(test_phone)
        
        response2 = self.prepare_oncology_response(
            "Tell me about radiotherapy side effects",
            test_phone,
            "Radiotherapy side effects include: 1) Skin changes - redness, dryness 2) Fatigue 3) Hair loss in treated area 4) Temporary inflammation. Most improve 2-6 weeks after treatment."
        )
        
        print(f"📋 Response Type: {response2['type']}")
        print(f"💰 Cost: {response2['cost_estimate']}")
        print(f"❓ Reason: {response2['reason']}")
        if response2['type'] == 'text':
            print(f"💬 Message: {response2['text']['body'][:100]}...")
        
        # Scenario 3: Follow-up within 24 hours
        print("\n📱 SCENARIO 3: Follow-up Question (Within 24h)")
        print("-" * 40)
        print("👤 User: 'How can I manage skin irritation?'")
        
        response3 = self.prepare_oncology_response(
            "How can I manage skin irritation?",
            test_phone,
            "For radiation skin care: 1) Use gentle, fragrance-free moisturizers 2) Avoid sun exposure 3) Wear loose clothing 4) Don't use harsh soaps 5) Apply cool compresses for relief"
        )
        
        print(f"📋 Response Type: {response3['type']}")
        print(f"💰 Cost: {response3['cost_estimate']}")
        print(f"❓ Reason: {response3['reason']}")
        
        # Scenario 4: Simulate 24+ hours later
        print("\n📱 SCENARIO 4: User Returns After 25 Hours")
        print("-" * 40)
        
        # Manually set interaction time to 25 hours ago
        old_time = datetime.now() - timedelta(hours=25)
        self.last_user_interactions[test_phone] = old_time
        print(f"⏰ Simulating last interaction: 25 hours ago")
        
        response4 = self.prepare_oncology_response(
            "I have more questions about chemotherapy",
            test_phone,
            "Chemotherapy works by targeting rapidly dividing cancer cells throughout the body..."
        )
        
        print(f"📋 Response Type: {response4['type']}")
        print(f"💰 Cost: {response4['cost_estimate']}")
        print(f"❓ Reason: {response4['reason']}")
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 CONVERSATION SUMMARY")
        print("=" * 60)
        print("✅ Template used for: First contact + 24+ hour re-engagement")
        print("✅ Free-form used for: Active conversation within 24h")
        print("💰 Total estimated cost: $1.72 (2 templates + 2 free messages)")
        print("🎯 Optimal cost management achieved!")

async def main():
    demo = TemplateLogicDemo()
    await demo.simulate_oncology_conversation()

if __name__ == "__main__":
    asyncio.run(main())
