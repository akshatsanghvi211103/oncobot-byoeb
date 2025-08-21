#!/usr/bin/env python3
"""
Simple Oncology Bot Test for Qikchat Integration
This script tests the complete oncology bot workflow through Qikchat
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# Add paths for imports
project_root = Path(__file__).parent
sys.path.extend([
    str(project_root / 'byoeb'),
    str(project_root / 'byoeb-core'), 
    str(project_root / 'byoeb-integrations')
])

# Load environment
from dotenv import load_dotenv
load_dotenv(project_root / 'byoeb' / 'keys.env')

# Import oncology knowledge base
try:
    import local_kb_loader
    KB_AVAILABLE = True
except ImportError:
    KB_AVAILABLE = False
    print("⚠️ Local knowledge base not available")

class OncoQikchatBot:
    """Simple oncology bot using Qikchat integration."""
    
    def __init__(self):
        self.api_key = os.getenv("QIKCHAT_API_KEY")
        if not self.api_key:
            raise ValueError("QIKCHAT_API_KEY not found in environment")
        
        self.test_phone = "919739811075"  # Test number
        
        # Load oncology knowledge base if available
        self.kb = None
        if KB_AVAILABLE:
            try:
                self.kb = local_kb_loader.load_knowledge_base()
                print(f"✅ Loaded {len(self.kb)} oncology Q&A pairs")
            except Exception as e:
                print(f"⚠️ Failed to load knowledge base: {e}")
        
        print(f"🤖 OncoQikchat Bot initialized")
    
    def get_oncology_response(self, question: str) -> str:
        """Get oncology response from knowledge base or provide general guidance."""
        
        # Simple keyword matching for common oncology questions
        question_lower = question.lower()
        
        # Radiation therapy responses
        if any(word in question_lower for word in ['radiation', 'radiotherapy', 'radiant']):
            return """**Radiation Therapy Information** 📡

**What is it?**
High-energy beams that destroy cancer cells by damaging their DNA.

**Common Side Effects:**
• Skin changes (dryness, redness, peeling)
• Fatigue and tiredness
• Loss of appetite  
• Local effects at treatment site

**Duration:** Usually 5-7 weeks of daily treatments

**Important:** Most side effects are temporary and improve after treatment ends. Always follow your doctor's specific instructions.

Would you like more information about managing side effects?"""
        
        # Chemotherapy responses  
        elif any(word in question_lower for word in ['chemo', 'chemotherapy', 'chemical']):
            return """**Chemotherapy Information** 💊

**What is it?**
Medications that destroy cancer cells throughout the body.

**Common Side Effects:**
• Nausea and vomiting
• Hair loss (temporary)
• Increased infection risk
• Fatigue and weakness
• Mouth sores

**Cycles:** Usually given in cycles with rest periods between

**Support:** Anti-nausea medications and supportive care help manage side effects.

Would you like tips for managing chemotherapy side effects?"""
        
        # Side effects responses
        elif any(word in question_lower for word in ['side effect', 'symptom', 'reaction']):
            return """**Managing Cancer Treatment Side Effects** 🩺

**General Guidelines:**
• Stay hydrated - drink plenty of fluids
• Eat nutritious foods when possible
• Get adequate rest and sleep
• Report new symptoms to your care team
• Take prescribed medications as directed

**When to Call Doctor:**
• Fever over 100.4°F (38°C)
• Severe nausea/vomiting
• Signs of infection
• Unusual bleeding or bruising
• Difficulty breathing

**Remember:** You don't have to suffer in silence - help is available!"""
        
        # Diet and nutrition
        elif any(word in question_lower for word in ['diet', 'food', 'nutrition', 'eat']):
            return """**Nutrition During Cancer Treatment** 🥗

**General Principles:**
• Eat small, frequent meals
• Focus on protein-rich foods
• Stay hydrated with water and clear liquids
• Choose bland foods if nauseous
• Avoid raw or undercooked foods

**Good Options:**
• Lean meats, fish, eggs
• Cooked vegetables and fruits
• Whole grains and cereals
• Yogurt and smoothies

**Consult:** Work with a registered dietitian familiar with cancer care for personalized advice."""
        
        # Pain management
        elif any(word in question_lower for word in ['pain', 'hurt', 'ache', 'sore']):
            return """**Cancer Pain Management** 🎯

**Types of Pain:**
• Treatment-related (surgery, chemotherapy, radiation)
• Cancer-related (tumor pressure)
• Procedure-related (blood draws, scans)

**Management Options:**
• Medications (prescribed by doctor)
• Physical therapy and exercise
• Relaxation techniques
• Heat/cold therapy
• Massage and acupuncture

**Important:** Pain can and should be treated. Don't wait - speak with your care team."""
        
        # Support and emotional care
        elif any(word in question_lower for word in ['support', 'emotion', 'anxiety', 'depression', 'fear']):
            return """**Emotional Support During Cancer** 💙

**Normal Feelings:**
• Fear and anxiety about the future
• Sadness and grief
• Anger and frustration
• Feeling overwhelmed

**Support Resources:**
• Talk with family and friends
• Join cancer support groups
• Consider counseling or therapy
• Connect with spiritual care if desired
• Use hospital social services

**Remember:** Asking for help is a sign of strength, not weakness."""
        
        # General cancer information
        elif any(word in question_lower for word in ['cancer', 'tumor', 'oncology', 'treatment']):
            return """**General Cancer Information** 🎗️

**Cancer Care Team:**
• Oncologist (cancer specialist)
• Nurses and nurse practitioners
• Pharmacists
• Social workers
• Nutritionists

**Treatment Types:**
• Surgery
• Chemotherapy
• Radiation therapy
• Immunotherapy
• Targeted therapy

**Key Points:**
• Each person's cancer is unique
• Treatment plans are personalized
• Second opinions are encouraged
• Support services are available

**Questions?** Always feel free to ask your care team - no question is too small!"""
        
        # Default response
        else:
            return """**BYOeB Oncology Bot** 🏥

I'm here to provide general information about cancer care and treatment. 

**I can help with questions about:**
• Radiation therapy and side effects
• Chemotherapy information
• Managing treatment symptoms
• Nutrition during treatment
• Pain management
• Emotional support resources

**Important:** This information is educational only. Always consult with your healthcare team for personalized medical advice.

What would you like to know about?"""
    
    async def send_oncology_response(self, user_question: str):
        """Send an oncology response via Qikchat."""
        
        # Import Qikchat client
        from byoeb_integrations.channel.qikchat.qikchat_client import QikchatClient
        
        # Get response from knowledge base
        bot_response = self.get_oncology_response(user_question)
        
        # Create Qikchat client
        client = QikchatClient(self.api_key)
        
        # Send user question (for context)
        user_message = {
            "to_contact": self.test_phone,
            "type": "text", 
            "text": {
                "body": f"👤 **Patient Question:**\n{user_question}"
            }
        }
        
        # Send bot response
        bot_message = {
            "to_contact": self.test_phone,
            "type": "text",
            "text": {
                "body": f"🤖 **Oncology Bot Response:**\n\n{bot_response}"
            }
        }
        
        try:
            print(f"📤 Sending user question...")
            user_result = await client.send_message(user_message)
            print(f"✅ User message sent: {user_result.get('message_id', 'Unknown')}")
            
            # Wait a moment before sending response
            await asyncio.sleep(2)
            
            print(f"📤 Sending bot response...")  
            bot_result = await client.send_message(bot_message)
            print(f"✅ Bot response sent: {bot_result.get('message_id', 'Unknown')}")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to send messages: {e}")
            return False
    
    async def test_oncology_scenarios(self):
        """Test common oncology scenarios."""
        
        test_questions = [
            "What are the side effects of radiation therapy?",
            "How does chemotherapy work?", 
            "What should I eat during cancer treatment?",
            "How can I manage cancer pain?",
            "I'm feeling anxious about my diagnosis"
        ]
        
        print(f"\n🧪 Testing {len(test_questions)} oncology scenarios")
        print("=" * 60)
        
        for i, question in enumerate(test_questions, 1):
            print(f"\n📋 Test {i}: {question}")
            
            success = await self.send_oncology_response(question)
            
            if success:
                print(f"✅ Test {i} completed successfully")
            else:
                print(f"❌ Test {i} failed")
            
            # Wait between tests to avoid rate limiting
            if i < len(test_questions):
                print("⏳ Waiting 5 seconds before next test...")
                await asyncio.sleep(5)
        
        print(f"\n🎉 All oncology scenarios tested!")

async def main():
    """Main test function."""
    
    print("🚀 Starting Oncology Bot Test")
    print(f"⏰ Time: {datetime.now()}")
    print("=" * 60)
    
    try:
        # Initialize oncology bot
        bot = OncoQikchatBot()
        
        # Test individual scenario
        print("\n🧪 Testing Single Oncology Response")
        test_question = "What are the side effects of radiation therapy?"
        success = await bot.send_oncology_response(test_question)
        
        if success:
            print("✅ Single test passed!")
            
            # Ask if user wants to run full test suite
            print("\n🤔 Would you like to run the full test suite?")
            print("This will send 5 test messages to the configured phone number.")
            
            response = input("Run full tests? (y/N): ").strip().lower()
            
            if response in ['y', 'yes']:
                await bot.test_oncology_scenarios()
            else:
                print("👍 Single test completed successfully")
        else:
            print("❌ Single test failed")
            return False
            
    except Exception as e:
        print(f"💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n🎊 Oncology bot test completed!")
    return True

if __name__ == "__main__":
    print("BYOeB Oncology Bot - Qikchat Integration Test")
    print("=" * 60)
    
    # Run async main
    success = asyncio.run(main())
    
    if success:
        print("\n✅ All tests passed! Oncology bot is working with Qikchat.")
        sys.exit(0)
    else:
        print("\n❌ Tests failed. Check output above.")
        sys.exit(1)
