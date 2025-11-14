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

def strip_patient_context(message: str) -> str:
    """
    Strip patient context from the beginning of expert verification messages.
    New simplified patient context format:
    [Patient Name]
    Age: [age], Gender: [gender], DOB: [dob]
    
    [Rest of message]
    """
    lines = message.split('\n')
    
    # Look for pattern: name line followed by details line (Age:, Gender:, DOB:)
    if len(lines) >= 3:
        # Check if second line contains age/gender/dob pattern
        second_line = lines[1] if len(lines) > 1 else ""
        if any(keyword in second_line for keyword in ["Age:", "Gender:", "DOB:"]):
            # Skip the first two lines (patient name and details) and any empty lines after
            remaining_lines = lines[2:]
            # Skip any empty lines after patient context
            while remaining_lines and not remaining_lines[0].strip():
                remaining_lines.pop(0)
            
            stripped = '\n'.join(remaining_lines)
            print(f"🔧 DEBUG: Stripped patient context from verification message")
            print(f"🔧 DEBUG: Patient context found - Name: '{lines[0]}', Details: '{second_line}'")
            return stripped
    
    return message

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
        
        # Calculate time window (past 24 hours (#TODO rn) for new corrections)
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=24)
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
                        
                        # Strip patient context before parsing the verification message
                        clean_verification_text = strip_patient_context(verification_text)
                        
                        # Parse the verification message to extract user query and bot answer
                        lines = clean_verification_text.split('\n')
                        
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
    Update KB1_Expert with the corrected Q&A pairs after anonymization.
    Creates the expert corrections knowledge base and inserts validated entries.
    """
    if not corrected_conversations:
        print("ℹ️  No corrected conversations to add to KB1_Expert")
        return
    
    print(f"\n{'='*80}")
    print(f"📋 UPDATING KB1_EXPERT WITH {len(corrected_conversations)} CORRECTIONS")
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
    
    # Initialize Azure Search client for KB1_Expert
    from azure.search.documents.aio import SearchClient
    from azure.search.documents.indexes.aio import SearchIndexClient
    from azure.search.documents.indexes.models import (
        SearchIndex, SimpleField, SearchableField, VectorSearch, 
        HnswAlgorithmConfiguration, VectorSearchProfile,
        SearchField, SearchFieldDataType
    )
    
    # KB1_Expert configuration
    kb_expert_service_name = app_config["vector_store"]["azure_vector_search"]["service_name"]
    kb_expert_index_name = "oncobot_expert_index"
    kb_expert_endpoint = f"https://{kb_expert_service_name}.search.windows.net"
    
    print(f"🔗 Connecting to KB1_Expert:")
    print(f"   Service: {kb_expert_service_name}")
    print(f"   Index: {kb_expert_index_name}")
    print(f"   Endpoint: {kb_expert_endpoint}")
    
    # Create index client to check/create index
    index_client = SearchIndexClient(
        endpoint=kb_expert_endpoint,
        credential=DefaultAzureCredential()
    )
    
    # Check if index exists - create only if it doesn't exist
    index_exists = False
    try:
        existing_index = await index_client.get_index(kb_expert_index_name)
        index_exists = True
        print(f"✅ Index '{kb_expert_index_name}' already exists - will append new corrections")
    except Exception as e:
        print(f"📋 Index '{kb_expert_index_name}' doesn't exist - will create it")
    
    if not index_exists:
        print(f"🔨 Creating index '{kb_expert_index_name}' with full metadata schema...")
        
        # Create index with schema for expert corrections
        fields = [
                SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                SearchableField(name="question", type=SearchFieldDataType.String),
                SearchableField(name="answer", type=SearchFieldDataType.String), 
                SearchableField(name="combined_text", type=SearchFieldDataType.String),
                SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="category", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="question_number", type=SearchFieldDataType.Int32, filterable=True),
                SimpleField(name="expert_validated", type=SearchFieldDataType.Boolean, filterable=True),
                # Correction metadata fields (flattened for Azure Search)
                SimpleField(name="expert_no_message_id", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="original_verification_id", type=SearchFieldDataType.String, filterable=True),
                SearchableField(name="expert_correction", type=SearchFieldDataType.String),
                SearchableField(name="original_bot_answer", type=SearchFieldDataType.String),
                SimpleField(name="corrected_timestamp", type=SearchFieldDataType.DateTimeOffset, filterable=True),
                SimpleField(name="created_at", type=SearchFieldDataType.DateTimeOffset, filterable=True),
                SearchableField(name="original_question", type=SearchFieldDataType.String),
                SearchableField(name="original_answer", type=SearchFieldDataType.String),
                SearchField(
                    name="text_vector_3072",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True,
                    vector_search_dimensions=3072,
                    vector_search_profile_name="vector-profile"
                )
        ]
        
        # Configure vector search
        from azure.search.documents.indexes.models import HnswAlgorithmConfiguration
        
        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(
                    name="vector-config",
                    parameters={
                        "m": 4,
                        "ef_construction": 400,
                        "ef_search": 500,
                        "metric": "cosine"
                    }
                )
            ],
            profiles=[
                VectorSearchProfile(
                    name="vector-profile",
                    algorithm_configuration_name="vector-config"
                )
            ]
        )
        
        # Create the index
        index = SearchIndex(
            name=kb_expert_index_name,
            fields=fields,
            vector_search=vector_search
        )
        
        result = await index_client.create_index(index)
        print(f"✅ Successfully created index '{kb_expert_index_name}'")
    
    # Close index client and create search client
    await index_client.close()
    
    search_client = SearchClient(
        endpoint=kb_expert_endpoint,
        index_name=kb_expert_index_name,
        credential=DefaultAzureCredential()
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
        
        # Get embeddings for the corrected Q&A pair
        from byoeb_integrations.embeddings.llama_index.azure_openai import AzureOpenAIEmbed
        
        # Initialize embedding function (same as dependency_setup.py)
        azure_openai_embed = AzureOpenAIEmbed(
            model=app_config["embeddings"]["azure"]["model"],
            deployment_name=app_config["embeddings"]["azure"]["deployment_name"],
            azure_endpoint=app_config["embeddings"]["azure"]["endpoint"],
            token_provider=token_provider,
            api_version=app_config["embeddings"]["azure"]["api_version"]
        )
        embedding_fn = azure_openai_embed.get_embedding_function()
        
        # Generate embedding for the combined text
        combined_text = f"Question: {final_question}\nAnswer: {final_answer}"
        text_embedding = await embedding_fn.aget_text_embedding(combined_text)
        
        kb_entry = {
            'id': kb_entry_id,
            'question': final_question,
            'answer': final_answer,
            'category': 'Expert Corrected',  # Updated to match existing KB1 style
            'question_number': None,  # No question number for corrected entries
            'combined_text': combined_text,
            'source': 'oncobot_expert_knowledge_base',  # Unique source for expert corrections
            'expert_validated': True,  # Flag to identify expert corrections
            'text_vector_3072': text_embedding,  # Embedding vector for search
            # Flattened correction metadata fields
            'expert_no_message_id': conv['expert_no_message_id'],
            'original_verification_id': conv['original_verification_id'],
            'expert_correction': conv['expert_correction'],
            'original_bot_answer': conv['bot_answer'],
            'corrected_timestamp': datetime.fromtimestamp(float(conv['expert_no_timestamp'])).isoformat() + 'Z',
            'created_at': datetime.now().isoformat() + 'Z',
            'original_question': question,
            'original_answer': corrected_answer
        }
        
        # Check if this correction already exists in KB1_Expert to avoid duplicates
        try:
            print(f"🔍 Checking for duplicate correction with verification ID: {conv['original_verification_id']}")
            duplicate_query = f"original_verification_id eq '{conv['original_verification_id']}'"
            duplicate_results = await search_client.search(search_text="*", filter=duplicate_query, top=1)
            
            duplicate_found = False
            async for result in duplicate_results:
                duplicate_found = True
                print(f"⚠️  Duplicate correction found - skipping (existing ID: {result['id']})")
                break
                
            if duplicate_found:
                print(f"   ⏭️  Skipping duplicate correction for verification ID: {conv['original_verification_id']}")
                continue
                
        except Exception as e:
            print(f"⚠️  Warning: Could not check for duplicates: {e} - proceeding with insertion")
        
        generalizable_conversations.append(kb_entry)
        
        print(f"\n✅ APPROVED FOR KB1_EXPERT - CORRECTION #{i}")
        print(f"{'─'*60}")
        print(f"🆔 KB Entry ID: {kb_entry_id}")
        print(f"❓ Final Question: {final_question}")
        print(f"✅ Final Answer: {final_answer[:300]}...")
        print(f"📊 KB Entry Structure:")
        print(f"   - ID: {kb_entry['id']}")
        print(f"   - Source: {kb_entry['source']}")
        print(f"   - Category: {kb_entry['category']}")
        print(f"   - Expert Validated: {kb_entry['expert_validated']}")
        print(f"   - Combined Text: {kb_entry['combined_text'][:300]}...")
        
        # Actually insert into KB1_Expert
        try:
            print(f"📤 Inserting document into KB1_Expert index...")
            result = await search_client.upload_documents([kb_entry])
            print(f"✅ Successfully inserted document {kb_entry_id} into KB1_Expert")
            print(f"   Upload result: {result}")
        except Exception as e:
            print(f"❌ Error inserting document {kb_entry_id}: {e}")
            # Continue with other documents even if one fails
        
    # Close search client
    await search_client.close()
    
    print(f"\n{'='*60}")
    print(f"✅ KB1_EXPERT UPDATE COMPLETE")
    print(f"   Found {len(corrected_conversations)} total corrections from past 24 hours")
    print(f"   Successfully added {len(generalizable_conversations)} new expert-validated entries to KB1_Expert")
    filtered_out = len(corrected_conversations) - len(generalizable_conversations)
    if filtered_out > 0:
        print(f"   Filtered out {filtered_out} corrections (duplicates, non-generalizable, or processing errors)")
    print(f"   KB1_Expert incrementally updated with new corrections only")
    print(f"   Expert-validated entries will be prioritized in future LLM responses")

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