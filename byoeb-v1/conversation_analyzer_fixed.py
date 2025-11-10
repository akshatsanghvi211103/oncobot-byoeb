#!/usr/bin/env python3
"""
Clean Conversation Analyzer with Proper Reply Context Linking

This script uses the correct message linking logic based on reply_context.reply_id
and cross_conversation_context to properly group related messages.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from byoeb.chat_app.configuration.dependency_setup import message_db_service, user_db_service
import asyncio
from typing import List, Dict
from collections import defaultdict
from datetime import datetime

class ConversationAnalyzerFixed:
    def __init__(self):
        self.message_service = message_db_service
        self.user_service = user_db_service
        self.users_info = {}
        self.conversations_data = {}
        
    async def fetch_messages_after_timestamp(self, timestamp: str) -> List[dict]:
        """Fetch all messages from database after the given timestamp."""
        message_client = await self.message_service._get_collection_client(
            self.message_service.collection_name
        )
        
        query = {"timestamp": {"$gt": timestamp}}
        messages_raw = await message_client.afetch_all(query)
        return messages_raw

    async def fetch_users_info(self) -> None:
        """Fetch user information to identify experts vs regular users."""
        user_client = await self.user_service._get_collection_client(
            self.user_service.collection_name
        )
        
        users_raw = await user_client.afetch_all({})
        
        for user_data in users_raw:
            user_info = user_data.get("User", {})
            user_id = user_info.get("user_id")
            if user_id:
                self.users_info[user_id] = user_info

    def analyze_conversations_properly(self, messages_raw: List[dict]) -> None:
        """Analyze messages using proper reply_context linkage."""
        user_questions = {}  # question_id -> question_message
        expert_verifications = {}  # verification_id -> question_id
        conversations = {}  # question_id -> list of all related messages
        
        # Step 1: Find all user questions (ID1s)
        for msg_data in messages_raw:
            message_data = msg_data.get("message_data", {})
            message_category = message_data.get("message_category")
            
            if isinstance(message_category, list):
                message_category = message_category[0] if message_category else None
            
            if message_category == "byoebuser_to_bot":
                user_data = message_data.get("user", {})
                user_type = user_data.get("user_type", "")
                
                # Only regular users, not experts
                if user_type not in ["byoebexpert", "byoebexpert2"]:
                    message_context = message_data.get("message_context", {})
                    question_id = message_context.get("message_id")
                    
                    if question_id:
                        user_questions[question_id] = msg_data
                        conversations[question_id] = [msg_data]
        
        # Step 2: Find expert verification requests (ID2s) and link to questions
        for msg_data in messages_raw:
            message_data = msg_data.get("message_data", {})
            message_category = message_data.get("message_category")
            
            if isinstance(message_category, list):
                message_category = message_category[0] if message_category else None
                
            if message_category == "bot_to_byoebexpert_verification":
                message_context = message_data.get("message_context", {})
                verification_id = message_context.get("message_id")
                
                # Find original question via cross_conversation_context
                cross_context = message_data.get("cross_conversation_context", {})
                if cross_context:
                    messages_context = cross_context.get("messages_context", [])
                    for ctx_msg in messages_context:
                        reply_context = ctx_msg.get("reply_context", {})
                        question_id = reply_context.get("reply_id")
                        
                        if question_id in user_questions:
                            expert_verifications[verification_id] = question_id
                            conversations[question_id].append(msg_data)
                            break
        
        # Step 3: Link all other messages via reply_context
        for msg_data in messages_raw:
            message_data = msg_data.get("message_data", {})
            reply_context = message_data.get("reply_context", {})
            reply_id = reply_context.get("reply_id") if reply_context else None
            
            if reply_id:
                target_conversation = None
                
                # Replying to user question (ID1)?
                if reply_id in user_questions:
                    target_conversation = reply_id
                
                # Replying to expert verification (ID2)?
                elif reply_id in expert_verifications:
                    target_conversation = expert_verifications[reply_id]
                
                if target_conversation:
                    # Avoid duplicates
                    msg_id = message_data.get("message_context", {}).get("message_id")
                    existing_ids = [m.get("message_data", {}).get("message_context", {}).get("message_id") 
                                  for m in conversations[target_conversation]]
                    if msg_id not in existing_ids:
                        conversations[target_conversation].append(msg_data)
        
        # Step 4: Process each conversation
        for question_id, conversation_messages in conversations.items():
            question_msg = user_questions[question_id]
            self.process_conversation(question_id, question_msg, conversation_messages)
    
    def process_conversation(self, question_id: str, question_msg: dict, conversation_messages: List[dict]):
        """Process a single conversation and extract all relevant data."""
        question_data = question_msg.get("message_data", {})
        question_context = question_data.get("message_context", {})
        
        # Initialize conversation data
        conv_data = {
            "patient_phone": self.extract_phone_number(question_data),
            "patient_message_indic": question_context.get("message_source_text", "---"),
            "patient_message_eng": question_context.get("message_english_text", "---"),
            "message_timestamp": question_msg.get("timestamp", "---"),
            "message_modality": self.determine_modality(question_context),
            "message_class": question_msg.get("message_class", "---"),
            "message_lang": self.extract_language(question_data),
            "response_text_eng": "---",
            "response_text_indic": "---",
            "expert_phone": "---",
            "expert_verification": "---",
            "expert_feedback": "---",
            "final_response_eng": "---",
            "final_response_indic": "---",
            "final_response_timestamp": "---"
        }
        
        # Process each message in the conversation
        for msg_data in conversation_messages:
            self.process_message_in_conversation(msg_data, conv_data, question_id)
        
        # Store the processed conversation
        self.conversations_data[question_id] = conv_data
    
    def process_message_in_conversation(self, msg_data: dict, conv_data: dict, question_id: str):
        """Process a single message within a conversation."""
        message_data = msg_data.get("message_data", {})
        message_category = message_data.get("message_category")
        message_context = message_data.get("message_context", {})
        
        if isinstance(message_category, list):
            message_category = message_category[0] if message_category else None
        
        source_text = message_context.get("message_source_text", "")
        english_text = message_context.get("message_english_text", "")
        timestamp = msg_data.get("timestamp", "---")
        
        # Handle bot responses to user
        if message_category == "bot_to_byoebuser_response":
            additional_info = message_context.get("additional_info", {})
            verification_status = additional_info.get("verification_status")
            
            # Check if this is an expert-verified final response
            reply_context = message_data.get("reply_context", {})
            reply_additional_info = reply_context.get("additional_info") if reply_context else None
            reply_verification_status = reply_additional_info.get("verification_status") if reply_additional_info else None
            reply_id = reply_context.get("reply_id") if reply_context else None
            
            # Final response after expert verification (has reply_context with verification_status)
            if reply_id == question_id and reply_verification_status == "verified":
                conv_data["final_response_eng"] = english_text
                conv_data["final_response_indic"] = source_text
                conv_data["final_response_timestamp"] = timestamp
            
            # Direct final response (replying to question with verified status)
            elif reply_id == question_id and verification_status == "verified" and conv_data["final_response_eng"] == "---":
                conv_data["final_response_eng"] = english_text
                conv_data["final_response_indic"] = source_text
                conv_data["final_response_timestamp"] = timestamp
            
            # Waiting message (pending verification)
            elif verification_status == "pending" and conv_data["response_text_eng"] == "---":
                conv_data["response_text_eng"] = english_text
                conv_data["response_text_indic"] = source_text
        
        # Handle expert responses
        elif message_category in ["byoebexpert_to_bot", "byoebuser_to_bot"]:
            user_data = message_data.get("user", {})
            user_type = user_data.get("user_type", "")
            user_phone = user_data.get("phone_number_id", "")
            
            if user_type in ["byoebexpert", "byoebexpert2"]:
                conv_data["expert_phone"] = user_phone
                
                # Yes/No verification
                if english_text.lower().strip() in ["yes", "no"]:
                    conv_data["expert_verification"] = english_text.title()
                else:
                    # Expert feedback
                    if conv_data["expert_feedback"] == "---":
                        conv_data["expert_feedback"] = english_text
                    else:
                        conv_data["expert_feedback"] += f" | {english_text}"
    
    def extract_phone_number(self, message_data: dict) -> str:
        """Extract phone number from message data."""
        user_data = message_data.get("user", {})
        return user_data.get("phone_number_id", "---")

    def extract_language(self, message_data: dict) -> str:
        """Extract language from message data."""
        user_data = message_data.get("user", {})
        return user_data.get("user_language", "---")

    def determine_modality(self, message_context: dict) -> str:
        """Determine message modality (text/audio)."""
        message_type = message_context.get("message_type", "")
        return "audio" if "audio" in message_type else "text"

    def format_conversations_readable(self) -> str:
        """Format conversations in a readable paragraph format."""
        output_lines = []
        output_lines.append("Conversation Analysis Report")
        output_lines.append("=" * 50)
        output_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output_lines.append(f"Total conversations: {len(self.conversations_data)}")
        output_lines.append("")
        
        for i, (question_id, conv_data) in enumerate(self.conversations_data.items(), 1):
            output_lines.append(f"CONVERSATION {i}")
            output_lines.append("-" * 20)
            output_lines.append(f"Patient Phone Number: {conv_data['patient_phone']}")
            output_lines.append(f"Patient Message (Indic): {conv_data['patient_message_indic']}")
            output_lines.append(f"Patient Message (English): {conv_data['patient_message_eng']}")
            
            # Convert timestamp to readable format
            try:
                timestamp_int = int(conv_data['message_timestamp'])
                readable_time = datetime.fromtimestamp(timestamp_int).strftime("%Y-%m-%d %H:%M:%S")
                output_lines.append(f"Message Timestamp: {readable_time}")
            except:
                output_lines.append(f"Message Timestamp: {conv_data['message_timestamp']}")
                
            output_lines.append(f"Message Modality: {conv_data['message_modality']}")
            output_lines.append(f"Message/Query Class: {conv_data['message_class']}")
            output_lines.append(f"Message Language: {conv_data['message_lang']}")
            
            # Response information
            if conv_data['response_text_eng'] != "---":
                output_lines.append(f"Response Text (English): {conv_data['response_text_eng']}")
                output_lines.append(f"Response Text (Indic): {conv_data['response_text_indic']}")
            
            # Expert interaction
            if conv_data['expert_verification'] != "---":
                output_lines.append("")
                output_lines.append("--- Expert Interaction ---")
                output_lines.append(f"Expert Phone Number: {conv_data['expert_phone']} (Type: byoebexpert)")
                output_lines.append(f"Expert Verification (Yes/No): {conv_data['expert_verification']}")
                
                if conv_data['expert_feedback'] != "---":
                    output_lines.append(f"Expert Feedback: {conv_data['expert_feedback']}")
            
            # Final response
            if conv_data['final_response_eng'] != "---":
                try:
                    timestamp_int = int(conv_data['final_response_timestamp'])
                    readable_time = datetime.fromtimestamp(timestamp_int).strftime("%Y-%m-%d %H:%M:%S")
                    output_lines.append(f"Final Response ({readable_time}) to user: {conv_data['final_response_eng']}")
                except:
                    output_lines.append(f"Final Response (English) to user: {conv_data['final_response_eng']}")
                    
                output_lines.append(f"Final Response (Indic): {conv_data['final_response_indic']}")
                output_lines.append(f"Final Response Timestamp: {conv_data['final_response_timestamp']}")
            
            output_lines.append("")
            output_lines.append("=" * 80)
            output_lines.append("")
        
        return "\n".join(output_lines)

async def main():
    analyzer = ConversationAnalyzerFixed()
    
    # Fetch user info
    await analyzer.fetch_users_info()
    
    # Fetch messages after timestamp
    timestamp = "1762796657"  # Using string format as in original
    messages = await analyzer.fetch_messages_after_timestamp(timestamp)
    
    print("🚀 Starting fixed conversation analysis...")
    
    # Analyze conversations with proper linking
    analyzer.analyze_conversations_properly(messages)
    
    # Generate readable output
    readable_output = analyzer.format_conversations_readable()
    
    # Write to file
    output_file = "conversations_fixed.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(readable_output)
    
    print(f"✅ Fixed analysis complete!")
    print(f"📊 Total user conversations: {len(analyzer.conversations_data)}")
    print(f"📄 Output written to: {output_file}")

if __name__ == "__main__":
    asyncio.run(main())