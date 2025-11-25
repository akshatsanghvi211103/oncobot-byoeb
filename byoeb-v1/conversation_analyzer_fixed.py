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
import csv
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
            "audio_link": self.extract_audio_link(question_context),
            "response_text_eng": "---",
            "response_text_indic": "---",
            "LLM-answer": "---",
            "expert_phone": "---",
            "expert_type": "---",
            "expert_verification": "---",
            "expert_verification_timestamp": "---",
            "expert_feedback": "---",
            "expert_feedback_timestamp": "---",
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
        
        # Handle expert verification messages
        elif message_category == "bot_to_byoebexpert_verification":
            # Extract LLM answer from verification message
            if conv_data["LLM-answer"] == "---":
                llm_answer = self.extract_llm_answer_from_verification(english_text)
                if llm_answer != "---":
                    conv_data["LLM-answer"] = llm_answer
        
        # Handle expert responses
        elif message_category in ["byoebexpert_to_bot", "byoebuser_to_bot"]:
            user_data = message_data.get("user", {})
            user_type = user_data.get("user_type", "")
            user_phone = user_data.get("phone_number_id", "")
            
            if user_type in ["byoebexpert", "byoebexpert2"]:
                conv_data["expert_phone"] = user_phone
                conv_data["expert_type"] = user_type
                
                # Yes/No verification
                if english_text.lower().strip() in ["yes", "no"]:
                    conv_data["expert_verification"] = english_text.title()
                    conv_data["expert_verification_timestamp"] = timestamp
                else:
                    # Expert feedback
                    if conv_data["expert_feedback"] == "---":
                        conv_data["expert_feedback"] = english_text
                        conv_data["expert_feedback_timestamp"] = timestamp
                    else:
                        conv_data["expert_feedback"] += f" | {english_text}"
                        # Keep the first feedback timestamp
    
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

    def extract_audio_link(self, message_context: dict) -> str:
        """Extract audio link from media_info for audio messages."""
        media_info = message_context.get("media_info", {})
        if media_info:
            media_id = media_info.get("media_id", "")
            if media_id and ("audio" in message_context.get("message_type", "") or media_info.get("mime_type", "").startswith("audio/")):
                return media_id
        return "---"

    def extract_llm_answer_from_verification(self, verification_text: str) -> str:
        """Extract the LLM answer from expert verification message."""
        if not verification_text:
            return "---"
        
        # Strip patient context first (same logic as KB update script)
        lines = verification_text.split('\n')
        
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
                
                clean_verification_text = '\n'.join(remaining_lines)
            else:
                clean_verification_text = verification_text
        else:
            clean_verification_text = verification_text
        
        # Parse the verification message to extract the original LLM answer
        lines = clean_verification_text.split('\n')
        
        # Handle different verification message formats
        if len(lines) >= 3:
            # Format: line 0 = *Question:* question, line 1 = *Answer:* answer, line 2 = "Is the answer correct?"
            for i, line in enumerate(lines):
                if line.strip().startswith("*Answer:*"):
                    # Extract answer after *Answer:*
                    answer_text = line.replace("*Answer:*", "").strip()
                    # Look for continuation lines until "Is the answer correct?"
                    for j in range(i + 1, len(lines)):
                        if "Is the answer correct?" in lines[j]:
                            break
                        answer_text += " " + lines[j].strip()
                    return answer_text
        
        # Fallback parsing logic
        for i, line in enumerate(lines):
            if line.startswith("Answer:") or line.startswith("Bot_Answer:"):
                # Extract answer and look for continuation lines
                answer_lines = [line.replace("Answer:", "").replace("Bot_Answer:", "").strip()]
                for j in range(i + 1, len(lines)):
                    if "Is the answer correct?" in lines[j]:
                        break
                    answer_lines.append(lines[j].strip())
                return " ".join(answer_lines).strip()
        
        return "---"

    def export_conversations_csv(self, filename: str = None) -> str:
        """Export conversations to CSV format with specified fields."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"conversation_analysis_{timestamp}.csv"
        
        # Define CSV headers as per user requirements
        headers = [
            "Patient Number",
            "Patient Message (in Indic)",
            "Patient Message (in Eng)", 
            "Message Timestamp",
            "Message Modality",
            "Audio URL (if modality is audio, else empty)",
            "Message Class (small-talk/logistical/medical...)",
            "Message Lang",
            "Response Text (in Eng)",
            "Response Text (in Indic)",
            "GPT Answer sent to Expert",
            "Expert phone num",
            "Expert Verification (Yes/No)",
            "Expert Verification Timestamp",
            "Expert Feedback",
            "Expert Feedback Timestamp",
            "Final Response (in Eng)",
            "Final Response (in Indic)",
            "Final Response Timestamp"
        ]
        
        with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            
            for i, (question_id, conv_data) in enumerate(self.conversations_data.items(), 1):
                # Convert timestamps to readable format (with quotes to prevent Excel auto-conversion)
                def format_timestamp(ts):
                    if ts == "---":
                        return ""
                    try:
                        formatted_time = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
                        return f"'{formatted_time}"  # Add leading quote to force Excel text format
                    except:
                        return ts
                
                # Helper to replace newlines with /n
                def format_text_for_csv(text):
                    if text == "---":
                        return ""
                    return text.replace('\n', '/n') if text else ""
                
                # Format phone number as string with leading quote to prevent Excel number conversion
                def format_phone_number(phone):
                    if phone == "---":
                        return ""
                    return f"'{phone}"  # Add leading quote to force Excel text format
                
                row = [
                    format_phone_number(conv_data['patient_phone']),  # Patient Number (formatted as string)
                    format_text_for_csv(conv_data['patient_message_indic']),
                    format_text_for_csv(conv_data['patient_message_eng']),
                    format_timestamp(conv_data['message_timestamp']),
                    conv_data['message_modality'],
                    conv_data['audio_link'] if conv_data['message_modality'] == 'audio' else "",
                    conv_data['message_class'],
                    conv_data['message_lang'],
                    format_text_for_csv(conv_data['response_text_eng']),
                    format_text_for_csv(conv_data['response_text_indic']),
                    format_text_for_csv(conv_data['LLM-answer']),
                    conv_data['expert_phone'] if conv_data['expert_phone'] != "---" else "",
                    conv_data['expert_verification'] if conv_data['expert_verification'] != "---" else "",
                    format_timestamp(conv_data['expert_verification_timestamp']),
                    format_text_for_csv(conv_data['expert_feedback']),
                    format_timestamp(conv_data['expert_feedback_timestamp']),
                    format_text_for_csv(conv_data['final_response_eng']),
                    format_text_for_csv(conv_data['final_response_indic']),
                    format_timestamp(conv_data['final_response_timestamp'])
                ]
                
                writer.writerow(row)
        
        return filename

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
            
            # Audio link for audio messages
            if conv_data['audio_link'] != "---":
                output_lines.append(f"Audio Link: {conv_data['audio_link']}")
            
            # Response information
            if conv_data['response_text_eng'] != "---":
                output_lines.append(f"Response Text (English): {conv_data['response_text_eng']}")
                output_lines.append(f"Response Text (Indic): {conv_data['response_text_indic']}")
            
            # LLM answer sent to expert for verification
            if conv_data['LLM-answer'] != "---":
                output_lines.append(f"LLM-answer (sent to expert): {conv_data['LLM-answer']}")
            
            # Expert interaction
            if conv_data['expert_verification'] != "---":
                output_lines.append("")
                output_lines.append("--- Expert Interaction ---")
                
                # Map expert type to readable format
                expert_type_readable = "medical" if conv_data['expert_type'] == "byoebexpert" else "logistical" if conv_data['expert_type'] == "byoebexpert2" else conv_data['expert_type']
                
                output_lines.append(f"Expert Phone Number: {conv_data['expert_phone']} (Type: {conv_data['expert_type']} - {expert_type_readable})")
                
                # Expert verification with timestamp
                verification_text = f"Expert Verification (Yes/No): {conv_data['expert_verification']}"
                if conv_data['expert_verification_timestamp'] != "---":
                    try:
                        timestamp_int = int(conv_data['expert_verification_timestamp'])
                        readable_time = datetime.fromtimestamp(timestamp_int).strftime("%Y-%m-%d %H:%M:%S")
                        verification_text += f" (at {readable_time})"
                    except:
                        pass
                output_lines.append(verification_text)
                
                # Expert feedback with timestamp
                if conv_data['expert_feedback'] != "---":
                    feedback_text = f"Expert Feedback: {conv_data['expert_feedback']}"
                    if conv_data['expert_feedback_timestamp'] != "---":
                        try:
                            timestamp_int = int(conv_data['expert_feedback_timestamp'])
                            readable_time = datetime.fromtimestamp(timestamp_int).strftime("%Y-%m-%d %H:%M:%S")
                            feedback_text += f" (at {readable_time})"
                        except:
                            pass
                    output_lines.append(feedback_text)
            
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
    timestamp = "1763095950"  # Using string format as in original
    messages = await analyzer.fetch_messages_after_timestamp(timestamp)
    
    print("🚀 Starting fixed conversation analysis...")
    
    # Analyze conversations with proper linking
    analyzer.analyze_conversations_properly(messages)
    
    # Generate readable output
    readable_output = analyzer.format_conversations_readable()
    
    # Write readable format to file
    output_file = "conversations_fixed.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(readable_output)
    
    # Export to CSV
    csv_file = analyzer.export_conversations_csv()
    
    print(f"✅ Fixed analysis complete!")
    print(f"📊 Total user conversations: {len(analyzer.conversations_data)}")
    print(f"📄 Readable output written to: {output_file}")
    print(f"📊 CSV export written to: {csv_file}")

if __name__ == "__main__":
    asyncio.run(main())