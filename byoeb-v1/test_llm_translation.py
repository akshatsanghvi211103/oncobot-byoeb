#!/usr/bin/env python3
"""
Test script to verify LLM-based translation is working correctly.
This script tests the translation functionality end-to-end.
"""

import asyncio
import logging
from byoeb.chat_app.configuration.dependency_setup import text_translator

# Set up logging to see translation logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_translation():
    """Test LLM-based translation functionality."""
    
    print("🔤 Testing LLM-based Translation")
    print("=" * 50)
    
    # Test cases
    test_cases = [
        {
            "input": "Hello, how are you?",
            "source": "en",
            "target": "hi",
            "description": "Simple greeting English to Hindi"
        },
        {
            "input": "After your radiation therapy, it's important to continue eating a balanced diet.",
            "source": "en", 
            "target": "hi",
            "description": "Medical advice English to Hindi"
        },
        {
            "input": "Thank you for your help.",
            "source": "en",
            "target": "kn", 
            "description": "Gratitude English to Kannada"
        },
        {
            "input": "This is already in English.",
            "source": "en",
            "target": "en",
            "description": "Same language (should return as-is)"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i}: {test_case['description']} ---")
        print(f"📝 Original ({test_case['source']}): {test_case['input']}")
        
        try:
            translated = await text_translator.atranslate_text(
                input_text=test_case['input'],
                source_language=test_case['source'],
                target_language=test_case['target']
            )
            print(f"🔄 Translated ({test_case['target']}): {translated}")
            print("✅ Translation successful!")
            
        except Exception as e:
            print(f"❌ Translation failed: {str(e)}")
            logger.error(f"Translation error for test case {i}: {e}")
    
    print(f"\n🎉 Translation testing completed!")

if __name__ == "__main__":
    try:
        asyncio.run(test_translation())
    except Exception as e:
        print(f"❌ Test script failed: {e}")
        logger.error(f"Test script error: {e}")