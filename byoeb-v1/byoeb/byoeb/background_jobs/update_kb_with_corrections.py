#!/usr/bin/env python3
"""
KB Update Background Job
Updates KB1 with corrected Q&A pairs from expert corrections.
Extracts corrected conversations and appends them to the knowledge base.
"""

import asyncio
import sys
import os
import json
from datetime import datetime, timedelta
import uuid

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from byoeb.chat_app.configuration.config import app_config
from byoeb.factory import MongoDBFactory
from byoeb.services.databases.mongo_db import MessageMongoDBService
from byoeb.models.message_category import MessageCategory

# Import LLM and bot config for anonymization
from byoeb_integrations.llms.azure_openai.async_azure_openai import AsyncAzureOpenAILLM
from azure.identity import get_bearer_token_provider, DefaultAzureCredential
import xml.etree.ElementTree as ET

# Load bot config for anonymization prompts
with open(os.path.join(os.path.dirname(__file__), 'bot_config.json'), 'r', encoding='utf-8') as f:
    bot_config = json.load(f)

async def get_corrected_conversations():
    """
    Get conversations where expert said "No" and provided corrections in the past hour.
    Reuses the same logic from extract_corrected_conversations.py
    """
    try:
        # Initialize database connection
        SINGLETON = "singleton"
        mongo_factory = MongoDBFactory(config=app_config, scope=SINGLETON)
        message_db_service = MessageMongoDBService(app_config, mongo_factory)
        
        # Get message collection
        collection_name = app_config["databases"]["mongo_db"]["message_collection"]
        message_collection_client = await message_db_service._get_collection_client(collection_name)
        
        # Calculate time window (past 1 hour for new corrections)
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        one_hour_ago_timestamp = str(int(one_hour_ago.timestamp()))
        
        print(f"🔍 Searching for corrected conversations from: {one_hour_ago} to {now}")
        print(f"   Timestamp range: {one_hour_ago_timestamp} - {int(now.timestamp())}")
        
        # Find expert responses where they said "No" in the past hour
        expert_no_responses_query = {
            "message_data.message_category": {"$in": [MessageCategory.EXPERT_TO_BOT.value]},
            "timestamp": {"$gte": one_hour_ago_timestamp},
            "message_data.message_context.message_english_text": "No"
        }
        
        expert_no_responses = await message_collection_client.afetch_all(expert_no_responses_query)
        print(f"📝 Found {len(expert_no_responses)} expert 'No' responses in the past hour")
        
        corrected_conversations = []
        
        for i, no_response in enumerate(expert_no_responses):
            print(f"🔍 Processing expert 'No' response {i+1}/{len(expert_no_responses)}")
            
            conversation = {
                "expert_no_message_id": no_response.get("_id"),
                "expert_no_timestamp": no_response.get("timestamp"),
                "original_verification_id": None,
                "user_query": None,
                "bot_answer": None,
                "expert_correction": None,
                "final_corrected_message": None
            }
            
            # Get the original verification message that this "No" is replying to
            reply_context = no_response.get("message_data", {}).get("reply_context", {})
            original_verification_id = reply_context.get("reply_id")
            
            if original_verification_id:
                conversation["original_verification_id"] = original_verification_id
                
                # Get the original verification message
                verification_query = {"_id": original_verification_id}
                verification_messages = await message_collection_client.afetch_all(verification_query)
                
                verification_msg = None
                if verification_messages and len(verification_messages) > 0:
                    verification_msg = verification_messages[0]
                    
                    if verification_msg:
                        message_context = verification_msg.get("message_data", {}).get("message_context", {})
                        verification_text = message_context.get("message_english_text", "")
                        
                        # Parse the verification message to extract user query and bot answer
                        lines = verification_text.split('\n')
                        
                        # Handle different verification message formats
                        if len(lines) >= 3:
                            # Format: line 0 = question, line 1 = answer, line 2 = "Is the answer correct?"
                            conversation["user_query"] = lines[0].strip()
                            conversation["bot_answer"] = lines[1].strip()
                        else:
                            # Fallback to original parsing logic
                            for i, line in enumerate(lines):
                                if line.startswith("Question:"):
                                    conversation["user_query"] = line.replace("Question:", "").strip()
                                elif line.startswith("Bot_Answer:"):
                                    # Bot answer might span multiple lines
                                    bot_answer_lines = [line.replace("Bot_Answer:", "").strip()]
                                    # Look for continuation lines
                                    for j in range(i + 1, len(lines)):
                                        if lines[j].startswith("Is the answer correct?"):
                                            break
                                        bot_answer_lines.append(lines[j].strip())
                                    conversation["bot_answer"] = " ".join(bot_answer_lines).strip()
                
                # Find the expert's correction message
                expert_user_id = no_response.get("message_data", {}).get("user", {}).get("user_id")
                no_timestamp = no_response.get("timestamp")
                
                correction_query = {
                    "message_data.message_category": {"$in": [MessageCategory.EXPERT_TO_BOT.value]},
                    "message_data.user.user_id": expert_user_id,
                    "timestamp": {"$gt": no_timestamp}
                }
                
                correction_messages = await message_collection_client.afetch_all(correction_query)
                
                correction_timestamp = None
                if correction_messages:
                    # Find the correction that's not just "No"
                    for correction_msg in correction_messages:
                        correction_context = correction_msg.get("message_data", {}).get("message_context", {})
                        correction_text = correction_context.get("message_english_text", "").strip()
                        if correction_text and correction_text.lower() != "no":
                            conversation["expert_correction"] = correction_text
                            correction_timestamp = correction_msg.get("timestamp")
                            break
                
                # Get the final corrected message sent to user
                if correction_timestamp and verification_msg:
                    cross_context = verification_msg.get("message_data", {}).get("cross_conversation_context", {})
                    user_id = None
                    if cross_context and cross_context.get("user"):
                        user_id = cross_context.get("user", {}).get("user_id")
                    
                    if user_id:
                        user_response_query = {
                            "message_data.message_category": MessageCategory.BOT_TO_USER_RESPONSE.value,
                            "timestamp": {"$gte": correction_timestamp},
                            "message_data.user.user_id": user_id
                        }
                        
                        user_responses = await message_collection_client.afetch_all(user_response_query)
                        
                        if user_responses:
                            user_response = user_responses[0]
                            user_context = user_response.get("message_data", {}).get("message_context", {})
                            final_message = user_context.get("message_english_text", "").strip()
                            conversation["final_corrected_message"] = final_message
            
            # Only add conversations that have meaningful data
            if conversation["user_query"] and conversation["expert_correction"]:
                corrected_conversations.append(conversation)
        
        return corrected_conversations
        
    except Exception as e:
        print(f"❌ Error retrieving corrected conversations: {e}")
        import traceback
        traceback.print_exc()
        return []

async def anonymize_qa_pair(question, answer, llm_client):
    """
    Use LLM to check if Q&A pair is generalizable and anonymize if needed.
    Returns (is_generalizable, final_question, final_answer)
    """
    try:
        # Get the anonymization prompt from bot_config
        user_prompt = bot_config["llm_response"]["kb_anonymization"]["user_prompt"]
        
        # Format the prompt with the Q&A pair
        formatted_prompt = f"{user_prompt}\n\n<query>{question}</query>\n<response>{answer}</response>"
        
        print(f"   🔍 Checking generalizability for: '{question[:50]}...'")
        
        # Call LLM for anonymization using the correct method signature
        augmented_prompts = [
            {"role": "system", "content": bot_config["llm_response"]["kb_anonymization"]["system_prompt"]},
            {"role": "user", "content": formatted_prompt}
        ]
        
        llm_response, response = await llm_client.agenerate_response(augmented_prompts)
        
        print(f"   📋 LLM Response: {response[:200]}...")
        
        # Parse XML response
        try:
            root = ET.fromstring(response)
            generalizable = root.find('generalizable').text.lower() == 'yes'
            
            if not generalizable:
                print(f"   ❌ Not generalizable - skipping this Q&A pair")
                return False, None, None
            
            # Check if PII present and get anonymized versions
            pii_element = root.find('pii')
            pii_present = pii_element.text.lower() == 'yes' if pii_element is not None and pii_element.text else False
            
            if pii_present:
                # Use anonymized versions
                final_question = root.find('query_anonymized').text or question
                final_answer = root.find('response_anonymized').text or answer
                print(f"   ✅ Generalizable with PII - using anonymized versions")
            else:
                # Use original versions
                final_question = question
                final_answer = answer  
                print(f"   ✅ Generalizable without PII - using original versions")
            
            return True, final_question, final_answer
            
        except ET.ParseError as e:
            print(f"   ⚠️  XML parsing error: {e} - using original versions")
            # Fallback: assume generalizable without PII
            return True, question, answer
            
    except Exception as e:
        print(f"   ❌ Error in anonymization: {e} - skipping this Q&A pair")
        return False, None, None

async def update_kb1_with_corrections(corrected_conversations):
    """
    Update KB1 with the corrected Q&A pairs after anonymization.
    For now, just print the data and return without actually updating.
    """
    if not corrected_conversations:
        print("ℹ️  No corrected conversations to add to KB1")
        return
    
    print(f"\n{'='*80}")
    print(f"📋 PREPARING TO UPDATE KB1 WITH {len(corrected_conversations)} CORRECTIONS")
    print(f"{'='*80}")
    
    # Initialize LLM client for anonymization (same setup as dependency_setup.py)
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), app_config["app"]["azure_cognitive_endpoint"]
    )
    
    llm_client = AsyncAzureOpenAILLM(
        model=app_config["llms"]["azure"]["model"],
        azure_endpoint=app_config["llms"]["azure"]["endpoint"],
        token_provider=token_provider,
        api_version=app_config["llms"]["azure"]["api_version"]
    )
    
    generalizable_conversations = []
    
    for i, conv in enumerate(corrected_conversations, 1):
        print(f"\n🔍 Processing correction {i}/{len(corrected_conversations)}")
        
        # Use the final corrected message as the answer (if available), otherwise use expert correction
        corrected_answer = conv.get("final_corrected_message") or conv.get("expert_correction")
        question = conv['user_query']
        
        # Check generalizability and anonymize if needed
        is_generalizable, final_question, final_answer = await anonymize_qa_pair(
            question, corrected_answer, llm_client
        )
        
        if not is_generalizable:
            print(f"   ⏭️  Skipping non-generalizable Q&A pair")
            continue
        
        # Generate a unique ID for the new KB entry
        kb_entry_id = f"expert_corrected_{uuid.uuid4().hex[:8]}"
        
        kb_entry = {
            'id': kb_entry_id,
            'question': final_question,
            'answer': final_answer,
            'category': 'Expert Corrected',  # Updated to match existing KB1 style
            'question_number': None,  # No question number for corrected entries
            'combined_text': f"Question: {final_question}\nAnswer: {final_answer}",
            'source': 'oncobot_knowledge_base',
            'correction_metadata': {
                'expert_no_message_id': conv['expert_no_message_id'],
                'original_verification_id': conv['original_verification_id'],
                'expert_correction': conv['expert_correction'],
                'original_bot_answer': conv['bot_answer'],
                'corrected_timestamp': conv['expert_no_timestamp'],
                'created_at': datetime.now().isoformat(),
                'original_question': question,
                'original_answer': corrected_answer
            }
        }
        
        generalizable_conversations.append(kb_entry)
        
        print(f"\n✅ APPROVED FOR KB1 - CORRECTION #{i}")
        print(f"{'─'*60}")
        print(f"🆔 KB Entry ID: {kb_entry_id}")
        print(f"❓ Final Question: {final_question}")
        print(f"✅ Final Answer: {final_answer[:300]}...")
        print(f"📊 KB Entry Structure:")
        print(f"   - ID: {kb_entry['id']}")
        print(f"   - Source: {kb_entry['source']}")
        print(f"   - Category: {kb_entry['category']}")
        print(f"   - Combined Text: {kb_entry['combined_text'][:300]}...")
        
        # TODO: Actually update KB1 here - STRICTLY RETURN BEFORE THIS
        print(f"📋 WOULD INSERT INTO KB1: {kb_entry_id}")
        print(f"🛑 RETURNING BEFORE ACTUAL DATABASE UPDATE")
        
    print(f"\n{'='*60}")
    print(f"🛑 KB UPDATE SIMULATION COMPLETE - NO ACTUAL CHANGES MADE")
    print(f"   Found {len(corrected_conversations)} total corrections")
    print(f"   Found {len(generalizable_conversations)} generalizable corrections ready for KB1")
    print(f"   Filtered out {len(corrected_conversations) - len(generalizable_conversations)} non-generalizable corrections")
    print(f"   Next step: Implement actual Azure Search index update")

async def main():
    """
    Main function to extract corrected conversations and update KB1.
    """
    print("🚀 Starting KB update with expert corrections...")
    print(f"📅 Started at: {datetime.now()}")
    
    try:
        # Get corrected conversations from the past hour
        corrected_conversations = await get_corrected_conversations()
        
        if corrected_conversations:
            print(f"✅ Found {len(corrected_conversations)} corrected conversations")
            
            # Update KB1 with corrections (currently just simulation)
            await update_kb1_with_corrections(corrected_conversations)
        else:
            print("ℹ️  No expert corrections found in the past hour")
            
    except Exception as e:
        print(f"❌ Error in KB update process: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"🏁 KB update job completed at: {datetime.now()}")

if __name__ == "__main__":
    asyncio.run(main())