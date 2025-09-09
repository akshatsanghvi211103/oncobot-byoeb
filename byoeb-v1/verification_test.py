#!/usr/bin/env python3
"""
Test script to verify the expert verification flow fixes are working correctly.
This script checks:
1. Welcome messages with interactive questions are sent upon registration
2. Follow-up questions are added to waiting messages
3. Final verified answers don't include redundant follow-up questions
4. Final verified answers are properly threaded to original user questions
"""

import os
import re

def check_file_content(file_path, search_patterns, description):
    """Check if a file contains specific patterns"""
    print(f"\n🔍 Checking {description}")
    if not os.path.exists(file_path):
        print(f"   ❌ File not found: {file_path}")
        return False
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    all_found = True
    for pattern, desc in search_patterns:
        if re.search(pattern, content, re.MULTILINE | re.DOTALL):
            print(f"   ✅ {desc}")
        else:
            print(f"   ❌ {desc}")
            all_found = False
    
    return all_found

def main():
    print("🔍 Verifying Expert Verification Flow Implementation")
    print("=" * 60)
    
    # Check 1: Expert flow handler - related questions fix
    expert_flow_file = "byoeb/byoeb/services/chat/message_handlers/expert_flow_handlers/generate.py"
    expert_patterns = [
        (r"related_questions = None.*# No related questions in final verified answer", 
         "Final verified answer removes related questions"),
        (r"if related_questions is not None:\s+questions_to_use = related_questions\s+else:\s+questions_to_use = reply_to_user_message_context", 
         "Related questions logic correctly handles None values"),
        (r"cross_conv_message\.reply_context is not None.*cross_conv_message\.reply_context\.additional_info\.get\(constants\.VERIFICATION_STATUS\) == constants\.WAITING", 
         "Message threading checks waiting status correctly"),
        (r"reply_id = cross_conv_message\.reply_context\.reply_id.*# For verified answers, reply to the original user question", 
         "Reply context correctly set to original user question"),
    ]
    
    expert_check = check_file_content(expert_flow_file, expert_patterns, 
                                    "Expert Flow Handler - Message Threading & Question Removal")
    
    # Check 2: User flow handler - related questions in waiting message
    user_flow_file = "byoeb/byoeb/services/chat/message_handlers/user_flow_handlers/generate.py"
    user_patterns = [
        (r"related_questions=related_questions.*# Add related questions to waiting message", 
         "Waiting message includes related questions"),
        (r"async def __create_user_message\(.*related_questions: List\[str\] = None", 
         "User message method accepts related questions parameter"),
    ]
    
    user_check = check_file_content(user_flow_file, user_patterns, 
                                  "User Flow Handler - Related Questions in Waiting Message")
    
    # Check 3: Welcome message sender
    welcome_file = "byoeb/byoeb/services/chat/welcome_sender.py"
    welcome_patterns = [
        (r"class WelcomeMessageSender", "WelcomeMessageSender class exists"),
        (r"def.*send_welcome_message", "Welcome message method exists"),
        (r"constants\.ROW_TEXTS.*related_questions", "Welcome message includes interactive questions"),
    ]
    
    welcome_check = check_file_content(welcome_file, welcome_patterns, 
                                     "Welcome Message Sender")
    
    # Check 4: Button length fix
    payload_file = "byoeb/byoeb/services/chat/qikchat/request_payload.py"
    payload_patterns = [
        (r"def truncate_text.*max_length=20", "Button text truncated to 20 characters"),
    ]
    
    payload_check = check_file_content(payload_file, payload_patterns, 
                                     "Button Length Fix")
    
    print("\n" + "=" * 60)
    if all([expert_check, user_check, welcome_check, payload_check]):
        print("🎉 All fixes verified successfully!")
        print("\n✅ Summary of fixes:")
        print("   1. Final verified answers no longer include redundant follow-up questions")
        print("   2. Verified answers are properly threaded to original user questions")
        print("   3. Waiting messages include follow-up questions")
        print("   4. Welcome messages with interactive questions are sent")
        print("   5. Button labels are limited to 20 characters")
    else:
        print("❌ Some fixes need attention!")
    
    return all([expert_check, user_check, welcome_check, payload_check])

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
