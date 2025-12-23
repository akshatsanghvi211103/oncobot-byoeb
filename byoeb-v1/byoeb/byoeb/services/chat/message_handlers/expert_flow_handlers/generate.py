import re
import json
import uuid
import asyncio
import byoeb.services.chat.constants as constants
from typing import List, Dict, Any
from datetime import datetime, timedelta
from byoeb.chat_app.configuration.config import bot_config, app_config
from byoeb.models.message_category import MessageCategory
from byoeb_core.models.byoeb.message_context import (
    ByoebMessageContext,
    MessageContext,
    ReplyContext,
    MessageTypes
)
from byoeb_core.models.byoeb.user import User
from byoeb.services.chat.message_handlers.base import Handler

class ByoebExpertGenerateResponse(Handler):

    EXPERT_DEFAULT_MESSAGE = bot_config["template_messages"]["expert"]["default"]
    EXPERT_THANK_YOU_MESSAGE = bot_config["template_messages"]["expert"]["thank_you"]
    EXPERT_ASK_FOR_CORRECTION = bot_config["template_messages"]["expert"]["ask_for_correction"]
    EXPERT_ALREADY_VERIFIED_MESSAGE = bot_config["template_messages"]["expert"]["already_answered"]

    USER_VERIFIED_ANSWER_MESSAGES = bot_config["template_messages"]["user"]["verified_answer"]
    USER_WRONG_ANSWER_MESSAGES = bot_config["template_messages"]["user"]["wrong_answer"]
    # USER_WAITING_ANSWER_MESSAGES = bot_config["template_messages"]["user"]["waiting_answer"]
    USER_CORRECTED_ANSWER_MESSAGES = bot_config["template_messages"]["user"]["corrected_answer"]

    USER_VERIFIED_EMOJI = app_config["channel"]["reaction"]["user"]["verified"]
    USER_REJECTED_EMOJI = app_config["channel"]["reaction"]["user"]["rejected"]
    USER_PENDING_EMOJI = app_config["channel"]["reaction"]["user"]["pending"]

    EXPERT_RESOLVED_EMOJI = app_config["channel"]["reaction"]["expert"]["resolved"]
    EXPERT_PENDING_EMOJI = app_config["channel"]["reaction"]["expert"]["pending"]
    EXPERT_WAITING_EMOJI = app_config["channel"]["reaction"]["expert"]["waiting"]

    _regular_user_type = bot_config["regular"]["user_type"]
    button_titles = bot_config["template_messages"]["expert"]["verification"]["button_titles"]
    yes = button_titles[0]
    no = button_titles[1]

    def __get_user_language(
        self,
        user_info_dict: dict
    ):
        user = User.model_validate(user_info_dict)
        return user.user_language

    def __strip_patient_context(self, message: str) -> str:
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
                print(f"🔧 DEBUG: Stripped patient context from expert message")
                print(f"🔧 DEBUG: Patient context found - Name: '{lines[0]}', Details: '{second_line}'")
                print("🔧 DEBUG: Stripped content:", stripped)
                return stripped
        
        return message

    def __parse_message(self, message: str) -> dict:
        # Strip patient context first
        clean_message = self.__strip_patient_context(message)
        
        pattern = r"\*Question\*:\s*(.*?)\n\*Bot_Answer\*:\s*(.*)"
        match = re.search(pattern, clean_message)
        if match:
            return {
                "Question": match.group(1).strip(),
                "Bot_Answer": match.group(2).strip()
            }
        return {}
        
    def __parse_message_alternative(self, message: str) -> dict:
        """
        Alternative parser for the new verification message format.
        Handles format like:
        <QUESTION>
        <ANSWER>
        Is the answer correct?
        """
        # Strip patient context first
        clean_message = self.__strip_patient_context(message)
        
        lines = clean_message.strip().split('\n')
        if len(lines) >= 2:
            # Find "Is the answer correct?" line
            footer_index = -1
            for i, line in enumerate(lines):
                if "Is the answer correct?" in line.strip():
                    footer_index = i
                    break
            
            if footer_index > 1:
                # Everything before footer is question + answer
                question = lines[0].strip()
                # Answer is everything between question and footer
                answer_lines = lines[1:footer_index]
                answer = '\n'.join(answer_lines).strip()
                
                return {
                    "Question": question,
                    "Bot_Answer": answer
                }
        
        # If alternative parsing fails, return empty dict
        return {}

    def __parse_message_patient_info(self, message: str) -> dict:
        """
        Parser for verification messages that include patient information.
        Handles format like:
        *Patient Info*: Name, Age: X, Gender: Y, DOB: Z
        
        *Question:* ...
        *Answer:* ...
        
        Is the answer correct?
        """
        try:
            # Split by lines and find the key sections
            lines = message.strip().split('\n')
            
            question = ""
            answer_lines = []
            in_answer_section = False
            
            for line in lines:
                line = line.strip()
                
                # Skip empty lines and patient info
                if not line or line.startswith("*Patient Info*:"):
                    continue
                    
                # Find question line
                if line.startswith("*Question:*"):
                    question = line.replace("*Question:*", "").strip()
                    continue
                
                # Find answer start
                if line.startswith("*Answer:*"):
                    answer_lines.append(line.replace("*Answer:*", "").strip())
                    in_answer_section = True
                    continue
                
                # Stop at footer
                if "Is the answer correct?" in line:
                    break
                    
                # Collect answer lines
                if in_answer_section:
                    answer_lines.append(line)
            
            # Join answer lines
            answer = '\n'.join(answer_lines).strip()
            
            if question and answer:
                return {
                    "Question": question,
                    "Bot_Answer": answer
                }
                
        except Exception as e:
            print(f"❌ Error parsing message with patient info: {e}")
        
        return {}
    
    def __parse_translated_text(self, text: str, user_language: str) -> dict:
        """
        Parse translated text for Hindi and Kannada to extract question and answer parts.
        Handles format like:
        प्रश्न: <question>
        उत्तर: <answer>
        
        Or:
        ಪ್ರಶ್ನೆ: <question>
        ಉತ್ತರ: <answer>
        """
        if user_language == "hi":
            # Hindi parsing
            lines = text.strip().split('\n')
            question = ""
            answer_lines = []
            in_answer_section = False
            
            for line in lines:
                line = line.strip()
                if line.startswith("प्रश्न:"):
                    question = line.replace("प्रश्न:", "").strip()
                elif line.startswith("उत्तर:"):
                    answer_lines.append(line.replace("उत्तर:", "").strip())
                    in_answer_section = True
                elif in_answer_section:
                    answer_lines.append(line)
            
            answer = '\n'.join(answer_lines).strip()
            if question and answer:
                return {"Question": question, "Answer": answer}
                
        elif user_language == "kn":
            # Kannada parsing
            lines = text.strip().split('\n')
            question = ""
            answer_lines = []
            in_answer_section = False
            
            for line in lines:
                line = line.strip()
                if line.startswith("ಪ್ರಶ್ನೆ:"):
                    question = line.replace("ಪ್ರಶ್ನೆ:", "").strip()
                elif line.startswith("ಉತ್ತರ:"):
                    answer_lines.append(line.replace("ಉತ್ತರ:", "").strip())
                    in_answer_section = True
                elif in_answer_section:
                    answer_lines.append(line)
            
            answer = '\n'.join(answer_lines).strip()
            if question and answer:
                return {"Question": question, "Answer": answer}
        
        # Fallback: if parsing fails, use "see below" and clean the text
        print("Using fallback")
        if user_language == "hi":
            # Hindi fallback
            cleaned_text = text.replace('\n', '. ').strip()
            return {"Question": "नीचे देखें", "Answer": cleaned_text}
        elif user_language == "kn":
            # Kannada fallback
            cleaned_text = text.replace('\n', '. ').strip()
            return {"Question": "ಕೆಳಗೆ ನೋಡಿ", "Answer": cleaned_text}
        
        # For English or other languages, return empty dict
        return {}

    def __get_user_prompt(
        self,
        question,
        answer,
        correction_text
    ):
        template_user_prompt = bot_config["llm_response"]["correction_prompts"]["user_prompt"]

        # Replace placeholders with actual values
        user_prompt = template_user_prompt.replace("<QUESTION>", question).replace("<ANSWER>", answer).replace("<CORRECTION>", correction_text)

        return user_prompt
        
    def __augment(
        self,
        user_prompt
    ):
        system_prompt = bot_config["llm_response"]["correction_prompts"]["system_prompt"]
        augmented_prompts = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return augmented_prompts
    
    def __create_user_reply_context(
        self,
        byoeb_message: ByoebMessageContext,
        cross_conv_message: ByoebMessageContext,
        emoji = None,
        status = None
    ) -> ReplyContext:
        reply_id = cross_conv_message.message_context.message_id
        reply_type = cross_conv_message.message_context.message_type
        reply_additional_info = {
            constants.UPDATE_ID: cross_conv_message.message_context.message_id,
            constants.EMOJI: emoji,
            constants.VERIFICATION_STATUS: status,
            constants.MODIFIED_TIMESTAMP: str(int(datetime.now().timestamp()))
        }
        print(f"🔧 __create_user_reply_context DEBUG: status={status}, cross_conv_message has reply_context={cross_conv_message.reply_context is not None}")
        if cross_conv_message.reply_context:
            print(f"🔧 __create_user_reply_context DEBUG: cross_conv_message.reply_context.reply_id={cross_conv_message.reply_context.reply_id}")
            print(f"🔧 __create_user_reply_context DEBUG: additional_info exists={cross_conv_message.reply_context.additional_info is not None}")
            if cross_conv_message.reply_context.additional_info:
                verification_status = cross_conv_message.reply_context.additional_info.get(constants.VERIFICATION_STATUS)
                print(f"🔧 __create_user_reply_context DEBUG: verification_status='{verification_status}' (should be '{constants.WAITING}')")
                print(f"🔧 __create_user_reply_context DEBUG: verification_status comparison: {verification_status == constants.WAITING}")
            else:
                print(f"🔧 __create_user_reply_context DEBUG: additional_info is None!")
        
        print(f"🔧 __create_user_reply_context DEBUG: Checking verified condition:")
        print(f"  - status == constants.VERIFIED: {status == constants.VERIFIED} (status='{status}', VERIFIED='{constants.VERIFIED}')")
        print(f"  - reply_context is not None: {cross_conv_message.reply_context is not None}")
        print(f"  - additional_info is not None: {cross_conv_message.reply_context.additional_info is not None if cross_conv_message.reply_context else False}")
        if cross_conv_message.reply_context and cross_conv_message.reply_context.additional_info:
            verification_check = cross_conv_message.reply_context.additional_info.get(constants.VERIFICATION_STATUS) == constants.WAITING
            print(f"  - verification_status == WAITING: {verification_check}")
        
        if (status == constants.VERIFIED
            and cross_conv_message.reply_context is not None
            and cross_conv_message.reply_context.reply_id is not None
            # For verified messages, use the reply_id if it looks like a QikChat message ID (not UUID)
            and not cross_conv_message.reply_context.reply_id.startswith(('uuid:', 'urn:', '{'))
            and len(cross_conv_message.reply_context.reply_id) > 10
        ):
            # For verified answers, reply to the original user question (using the QikChat message ID)
            reply_id = cross_conv_message.reply_context.reply_id
            print(f"🔧 __create_user_reply_context DEBUG: Using verified flow, reply_id set to: {reply_id}")
            reply_type = None
            reply_additional_info = {
                constants.UPDATE_ID: cross_conv_message.message_context.message_id,
                constants.VERIFICATION_STATUS: status,
                constants.MODIFIED_TIMESTAMP: str(int(datetime.now().timestamp()))
            }

        print(f"🔧 __create_user_reply_context DEBUG: Final reply_id being returned: {reply_id}")
        return ReplyContext(
            reply_id=reply_id,
            reply_type=reply_type,
            additional_info=reply_additional_info
        )
    
    def __get_read_reciept_message(
        self,
        message: ByoebMessageContext,
    ) -> ByoebMessageContext:
        read_reciept_message = ByoebMessageContext(
            channel_type=message.channel_type,
            message_category=MessageCategory.READ_RECEIPT.value,
            message_context=MessageContext(
                message_id=message.message_context.message_id,
            )
        )
        return read_reciept_message
    
    async def __create_user_message(
        self,
        text_message: str,
        byoeb_message: ByoebMessageContext,
        emoji = None,
        status = None,
        related_questions = None,
        english_text = None,
    ):
        from byoeb.chat_app.configuration.dependency_setup import speech_translator
        from byoeb.chat_app.configuration.dependency_setup import text_translator
        user_info_dict = byoeb_message.cross_conversation_context.get(constants.USER)
        user = User.model_validate(user_info_dict)
        user.user_type = self._regular_user_type
        
        # Check if user is active for verified answers (template vs regular message decision)
        should_use_template = False #TODO
        if status == constants.VERIFIED:
            from byoeb.chat_app.configuration.dependency_setup import user_db_service
            from byoeb.services.chat.message_handlers.user_flow_handlers.send import ByoebUserSendResponse
            
            user_id = user.user_id
            # Check if user is active (hasn't been inactive for 24 hours)
            send_handler = ByoebUserSendResponse(user_db_service, None)  # message_db_service not needed for activity check
            is_active_user = await send_handler.is_active_user(user_id)
            # is_active_user = False #TODO
            print(f"🔧 User {user_id} is_active_user: {is_active_user}")
            
            if not is_active_user:
                should_use_template = True
                print("📋 User is inactive for 24 hours, will send template message")
            else:
                print("🔘 User is active, will send regular text message", should_use_template)
        reply_to_user_messages_context = byoeb_message.cross_conversation_context.get(constants.MESSAGES_CONTEXT)
        
        # print(f"🔧 DEBUG: reply_to_user_messages_context type: {type(reply_to_user_messages_context)}")
        # print(f"🔧 DEBUG: reply_to_user_messages_context value: {reply_to_user_messages_context}")
        
        # Check if reply_to_user_messages_context is None or empty
        if not reply_to_user_messages_context:
            print(f"❌ DEBUG: reply_to_user_messages_context is None or empty, returning empty list")
            return []
            
        reply_to_user_message_context = None
        message_reaction_additional_info = {}
        media_additiona_info = {}
        message_en_text = None
        
        # print(f"🔧 DEBUG: Creating user message with status: {status}")
        # print(f"🔧 DEBUG: Verification status from reply context: {byoeb_message.reply_context.additional_info.get(constants.VERIFICATION_STATUS) if byoeb_message.reply_context and byoeb_message.reply_context.additional_info else 'None'}")
        
        # Generate audio for all verified answers (both corrections and approvals)
        if status == constants.VERIFIED:
            message_en_text = english_text if english_text is not None else text_message
            
            # Check if this is an expert correction case
            is_correction = (byoeb_message.reply_context 
                           and byoeb_message.reply_context.additional_info
                           and byoeb_message.reply_context.additional_info.get(constants.VERIFICATION_STATUS) == constants.PENDING)
            
            if is_correction:
                print("🔧 DEBUG: Expert correction case - preparing corrected message")
                # For expert corrections, translate the formatted response to user's language
                translated_text = await text_translator.atranslate_text(
                    input_text=text_message,
                    source_language="en",
                    target_language=user.user_language
                )
                
                # For expert corrections, send the actual corrected answer directly
                text_message = translated_text
            else:
                print("🔧 DEBUG: Expert approval case - preparing verified message")
                # For expert approvals, translate the formatted response to user's language
                translated_text = await text_translator.atranslate_text(
                    input_text=text_message if message_en_text else text_message,
                    source_language="en",
                    target_language=user.user_language
                )
                
                # For expert approvals, send the actual translated answer directly
                text_message = translated_text

            
            print(f"🔧 DEBUG: Final message text: '{text_message[:100]}...'")
            
            # Generate TTS audio using User Delegation SAS URLs
            try:
                from byoeb.chat_app.configuration.dependency_setup import tts_service
                audio_url = await tts_service.generate_audio_url(
                    text=text_message,
                    language=user.user_language,
                )
                if audio_url:
                    media_additiona_info = {
                        "audio_url": audio_url,  # Store SAS URL for QikChat
                        constants.MIME_TYPE: "audio/wav"
                    }
                    print(f"🔧 DEBUG: Audio message generated successfully with SAS URL")
                else:
                    media_additiona_info = {}
                    print(f"⚠️ DEBUG: TTS service returned no audio URL")
            except Exception as e:
                print(f"❌ DEBUG: Error generating audio message: {e}")
                # Continue without audio if TTS fails
                media_additiona_info = {}
                
            message_reaction_additional_info = {
                constants.EMOJI: emoji,
                constants.VERIFICATION_STATUS: status
            }
        new_user_messages = []
        print(f"🔧 DEBUG: About to iterate over {len(reply_to_user_messages_context)} message contexts")
        
        # For verified answers, only send one response message to the most recent user message
        if status == constants.VERIFIED:
            print("🔧 DEBUG: Status is VERIFIED - sending single response to most recent message only")
            # Get the most recent message (usually the last one in the list)
            message_contexts_to_process = [reply_to_user_messages_context[-1]]
        else:
            # For other statuses, process all messages as before
            message_contexts_to_process = reply_to_user_messages_context
            
        for i, message_context_dict in enumerate(message_contexts_to_process):
            print(f"🔧 DEBUG: Processing message context {i+1}/{len(message_contexts_to_process)}")
            try:
                reply_to_user_message_context = ByoebMessageContext.model_validate(message_context_dict)
                reply_context = self.__create_user_reply_context(
                    byoeb_message,
                    reply_to_user_message_context,
                    emoji,
                    status
                )
                # print(f"✅ DEBUG: Successfully processed message context {i+1}")
            except Exception as e:
                print(f"❌ DEBUG: Error processing message context {i+1}: {e}")
                import traceback
                traceback.print_exc()
                continue
            message_context = None
            print(f"🔧 DEBUG: Original message type: {reply_to_user_message_context.message_context.message_type}")
            
            if (reply_to_user_message_context.message_context.message_type == MessageTypes.REGULAR_AUDIO.value):
                print("🔧 DEBUG: Creating REGULAR_AUDIO message context")
                message_context = MessageContext(
                    message_id=str(uuid.uuid4()),  # Will be replaced with QikChat ID after sending
                    message_type=MessageTypes.REGULAR_AUDIO.value,
                    additional_info={
                        **media_additiona_info,
                        **message_reaction_additional_info
                    }
                )
            elif (reply_to_user_message_context.message_context.message_type == MessageTypes.INTERACTIVE_LIST.value or
                  reply_to_user_message_context.message_context.message_type == "interactive_list_reply"):
                print("🔧 DEBUG: Creating INTERACTIVE_LIST/INTERACTIVE_LIST_REPLY message context")
                
                # For verified answers (status == constants.VERIFIED), always send as regular text without interactive elements
                if status == constants.VERIFIED:
                    if should_use_template:
                        print("🔧 DEBUG: Status is VERIFIED - creating template message for inactive user")
                        # Extract original question from reply context for template
                        original_question = "Your question"  # Default fallback
                        if (byoeb_message.reply_context and 
                            byoeb_message.reply_context.reply_english_text):
                            parsed_verification = self.__parse_message_patient_info(byoeb_message.reply_context.reply_english_text)
                            print("COMING HERE 1", byoeb_message.reply_context.reply_english_text)
                            print("done")
                            if not parsed_verification.get("Question"):
                                parsed_verification = self.__parse_message_alternative(byoeb_message.reply_context.reply_english_text)
                            original_question = parsed_verification.get("Question", "Your question")
                            corrected_answer = parsed_verification.get("Bot_Answer", "")
                        
                        user_language = user.user_language
                        if user_language == "en":
                            user_language = user_language + "_US"

                        print("Here, text_message", text_message)
                        print("done now")
                        
                        # Parse translated text for Hindi/Kannada template parameters
                        template_question = original_question
                        template_answer = corrected_answer
                        if user.user_language in ["hi", "kn"]:
                            parsed_translated = self.__parse_translated_text(text_message, user.user_language)
                            if parsed_translated.get("Question") and parsed_translated.get("Answer"):
                                template_question = parsed_translated["Question"]
                                template_answer = parsed_translated["Answer"]
                                print(f"🔧 DEBUG: Using translated template params - Q: '{template_question}', A: '{template_answer}'")
                        
                        message_context = MessageContext(
                            message_id=str(uuid.uuid4()),  # Generate unique message ID
                            message_type=MessageTypes.TEMPLATE_BUTTON.value,  # Use TEMPLATE_BUTTON for templates
                            message_english_text=message_en_text,
                            message_source_text=text_message,
                            additional_info={
                                constants.TEMPLATE_NAME: "bot_temp",
                                constants.TEMPLATE_LANGUAGE: user_language,
                                constants.TEMPLATE_PARAMETERS: [template_question, template_answer]
                            }
                        )
                    else:
                        print("🔧 DEBUG: Status is VERIFIED - creating regular text message without questions")
                        message_context = MessageContext(
                            message_id=str(uuid.uuid4()),  # Generate unique message ID
                            message_type=MessageTypes.REGULAR_TEXT.value,
                            message_english_text=message_en_text,
                            message_source_text=text_message,
                            additional_info={
                                **message_reaction_additional_info,
                                **media_additiona_info
                            }
                        )
                # If related_questions is explicitly passed as empty list, don't include any questions (for verified answers)
                elif related_questions is not None and len(related_questions) == 0:
                    print("🔧 DEBUG: related_questions is empty list - creating regular text message without questions")
                    message_context = MessageContext(
                        message_id=str(uuid.uuid4()),  # Generate unique message ID
                        message_type=MessageTypes.REGULAR_TEXT.value,
                        message_english_text=message_en_text,
                        message_source_text=text_message,
                        additional_info={
                            **message_reaction_additional_info
                        }
                    )
                else:
                    # For all other cases, include follow-up questions
                    description = bot_config["template_messages"]["user"]["follow_up_questions_description"][user.user_language]
                    
                    # Use the passed related_questions parameter if provided, otherwise fall back to existing data
                    if related_questions is not None:
                        questions_to_use = related_questions
                    else:
                        questions_to_use = reply_to_user_message_context.message_context.additional_info.get(constants.RELATED_QUESTIONS)
                    
                    # Only include row_texts and description if questions_to_use is not None and not empty
                    additional_info_dict = {
                        **message_reaction_additional_info,
                    }
                    if questions_to_use is not None and len(questions_to_use) > 0:
                        additional_info_dict[constants.DESCRIPTION] = description
                        additional_info_dict[constants.ROW_TEXTS] = questions_to_use
                        additional_info_dict["has_follow_up_questions"] = True
                        
                    message_context = MessageContext(
                        message_id=str(uuid.uuid4()),  # Generate unique message ID
                        message_type=MessageTypes.REGULAR_TEXT.value,
                        message_english_text=message_en_text,
                        message_source_text=text_message,
                        additional_info=additional_info_dict
                )
            else:
                print(f"🔧 DEBUG: Creating default REGULAR_TEXT message context for type: {reply_to_user_message_context.message_context.message_type}")
                # Default case for any other message type (including regular_text)
                
                # For verified answers, always send as regular text without interactive elements
                if status == constants.VERIFIED:
                    if should_use_template:
                        print("🔧 DEBUG: Status is VERIFIED - creating template message for inactive user")
                        # Extract original question from reply context for template
                        original_question = "Your question"  # Default fallback
                        if (byoeb_message.reply_context and 
                            byoeb_message.reply_context.reply_english_text):
                            parsed_verification = self.__parse_message(byoeb_message.reply_context.reply_english_text)
                            if not parsed_verification.get("Question"):
                                parsed_verification = self.__parse_message_alternative(byoeb_message.reply_context.reply_english_text)
                            original_question = parsed_verification.get("Question", "Your question")
                        
                        user_language = user.user_language
                        if user_language == "en":
                            user_language = user_language + "_US"
                        print("COMING HERE 2")
                        
                        # Parse translated text for Hindi/Kannada template parameters
                        template_question = original_question
                        template_answer = text_message
                        if user.user_language in ["hi", "kn"]:
                            parsed_translated = self.__parse_translated_text(text_message, user.user_language)
                            if parsed_translated.get("Question") and parsed_translated.get("Answer"):
                                template_question = parsed_translated["Question"]
                                template_answer = parsed_translated["Answer"]
                                print(f"🔧 DEBUG: Using translated template params - Q: '{template_question}', A: '{template_answer}'")
                        
                        message_context = MessageContext(
                            message_id=str(uuid.uuid4()),  # Generate unique message ID
                            message_type=MessageTypes.TEMPLATE_BUTTON.value,  # Start as regular, will be changed to TEMPLATE_BUTTON later
                            message_english_text=message_en_text,
                            message_source_text=text_message,
                            additional_info={
                                constants.TEMPLATE_NAME: "bot_temp",
                                constants.TEMPLATE_LANGUAGE: user_language,
                                constants.TEMPLATE_PARAMETERS: [template_question, template_answer]
                            }
                        )
                    else:
                        print("🔧 DEBUG: Status is VERIFIED - creating regular text message without questions")
                        message_context = MessageContext(
                            message_id=str(uuid.uuid4()),  # Generate unique message ID
                            message_type=MessageTypes.REGULAR_TEXT.value,
                            message_english_text=message_en_text,
                            message_source_text=text_message,
                            additional_info={
                                **message_reaction_additional_info,
                                **media_additiona_info
                            }
                        )
                # If we have related_questions, create an interactive list, otherwise regular text
                elif related_questions and len(related_questions) > 0:
                    print("🔧 DEBUG: Adding follow-up questions to regular text message")
                    description = bot_config["template_messages"]["user"]["follow_up_questions_description"][user.user_language]
                    message_context = MessageContext(
                        message_id=str(uuid.uuid4()),  # Generate unique message ID
                        message_type=MessageTypes.INTERACTIVE_LIST.value,
                        message_english_text=message_en_text,
                        message_source_text=text_message,
                        additional_info={
                            **message_reaction_additional_info,
                            **media_additiona_info,
                            constants.DESCRIPTION: description,
                            constants.ROW_TEXTS: related_questions,
                            "has_follow_up_questions": True
                        }
                    )
                else:
                    message_context = MessageContext(
                        message_id=str(uuid.uuid4()),  # Generate unique message ID
                        message_type=MessageTypes.REGULAR_TEXT.value,
                        message_english_text=message_en_text,
                        message_source_text=text_message,
                        additional_info={
                            **message_reaction_additional_info,
                            **media_additiona_info
                        }
                    )
            
            print(f"🔧 DEBUG: Created message_context: {message_context is not None}")
            if message_context:
                print(f"🔧 DEBUG: Message context type: {message_context.message_type}")
                print(f"🔧 DEBUG: Message source text length: {len(message_context.message_source_text) if message_context.message_source_text else 0}")
            
            # Ensure we have a valid message_context before proceeding
            if message_context is None:
                print(f"❌ DEBUG: message_context is None! Cannot create user message.")
                continue
            # print("Message context: ", json.dumps(message_context.model_dump()))
            
            try:
                new_user_message = ByoebMessageContext(
                    channel_type=byoeb_message.channel_type,
                    message_category=MessageCategory.BOT_TO_USER_RESPONSE.value,
                    user=user,
                    message_context=message_context,
                    reply_context=reply_context,
                    cross_conversation_context=byoeb_message.cross_conversation_context
                )
                new_user_messages.append(new_user_message)
                # print(f"✅ DEBUG: Successfully created user message {i+1}")
            except Exception as e:
                print(f"❌ DEBUG: Error creating user message {i+1}: {e}")
                import traceback
                traceback.print_exc()
                continue
                
        print(f"🔧 DEBUG: Created {len(new_user_messages)} user messages")
        return new_user_messages
    
    def __create_expert_message(
        self,
        text_message: str,
        byoeb_message: ByoebMessageContext,
        emoji = None,
        status = None,
    ):
        correction_info = {}

        if (status == constants.VERIFIED
            and byoeb_message.message_context.message_source_text != self.yes
        ):
            correction_source = byoeb_message.message_context.message_source_text
            correction_english = byoeb_message.message_context.message_english_text
            correction_info = {
                constants.CORRECTION_SOURCE: correction_source,
                constants.CORRECTION_EN: correction_english
            }
        new_expert_message = ByoebMessageContext(
            channel_type=byoeb_message.channel_type,
            message_category=MessageCategory.BOT_TO_EXPERT.value,
            user=User(
                user_id=byoeb_message.user.user_id if byoeb_message.user else None,
                user_type=byoeb_message.user.user_type if byoeb_message.user else None,
                user_language=byoeb_message.user.user_language if byoeb_message.user else None,
                phone_number_id=byoeb_message.user.phone_number_id if byoeb_message.user else None
            ),
            message_context=MessageContext(
                message_id=str(uuid.uuid4()),  # Generate unique message ID
                message_type=MessageTypes.REGULAR_TEXT.value,
                message_source_text=text_message,
                message_english_text=text_message,
            ),
            reply_context=ReplyContext(
                reply_id=byoeb_message.reply_context.reply_id if byoeb_message.reply_context else None,
                additional_info={
                    constants.EMOJI: emoji,
                    constants.VERIFICATION_STATUS: status,
                    **correction_info,
                    constants.MODIFIED_TIMESTAMP: str(int(datetime.now().timestamp()))
                }
            ),
            cross_conversation_context=byoeb_message.cross_conversation_context,
            incoming_timestamp=byoeb_message.incoming_timestamp,
        )
        if new_expert_message.reply_context and new_expert_message.reply_context.reply_id is None:
            new_expert_message.reply_context = None
        return [new_expert_message]
    
    def __get_cross_conv_verification_status(
        self,
        message: ByoebMessageContext
    ):
        # Check if cross_conversation_context exists
        if not message.cross_conversation_context:
            return None

        # Retrieve cross_messages_context with necessary checks
        cross_messages_context = message.cross_conversation_context.get(constants.MESSAGES_CONTEXT)
        if not cross_messages_context:
            return None

        # Validate and extract the first message context
        cross_message_context = ByoebMessageContext.model_validate(cross_messages_context[0])

        if not cross_message_context.message_context:
            return None
        if not cross_message_context.message_context.additional_info:
            return None
        
        return cross_message_context.message_context.additional_info.get(constants.VERIFICATION_STATUS)
        
        
    async def handle(
        self,
        messages: List[ByoebMessageContext]
    ) -> Dict[str, Any]:
        message = messages[0]
        print(f"\n=== EXPERT GENERATE RESPONSE DEBUG ===")
        print(f"📧 Processing expert message from: {message.user.phone_number_id if message.user else 'Unknown'}")
        # Use both text fields for debugging
        message_text = message.message_context.message_english_text or message.message_context.message_source_text
        print(f"💬 Message text: '{message_text}'")
        print(f"📝 Message type: {message.message_context.message_type}")
        

        
        read_reciept_message = self.__get_read_reciept_message(message)
        from byoeb.chat_app.configuration.dependency_setup import llm_client
        reply_context = message.reply_context
        
        print(f"🔗 Reply context exists: {reply_context is not None}")
        if reply_context:
            print(f"🔗 Reply ID: {reply_context.reply_id}")
            print(f"🔗 Reply message category: {getattr(reply_context, 'message_category', 'Not set')}")
            print(f"🔗 Reply additional_info keys: {list(reply_context.additional_info.keys()) if reply_context.additional_info else 'None'}")
            if reply_context.additional_info:
                print(f"🔗 Verification status: {reply_context.additional_info.get(constants.VERIFICATION_STATUS, 'Not set')}")
        
        cross_message_verification_status = self.__get_cross_conv_verification_status(message)
        # print(f"🔀 Cross conversation verification status: {cross_message_verification_status}")
        # print(f"🔀 Cross conversation context exists: {message.cross_conversation_context is not None}")
        
        byoeb_expert_messages = []
        byoeb_user_messages = []
        byoeb_messages = []

        if reply_context is None or reply_context.reply_id is None:
            print("❌ Branch: No reply context - sending default message")
            print(f"❌ This indicates the database lookup failed for expert reply")
            print(f"❌ Expert message will get default response instead of ask_for_correction")
            byoeb_expert_messages = self.__create_expert_message(self.EXPERT_DEFAULT_MESSAGE, message)

        elif cross_message_verification_status is None:
            print("❌ Branch: No cross message verification status - sending default message")
            print(f"❌ This indicates the reply context exists but lacks proper message category/status")
            byoeb_expert_messages = self.__create_expert_message(self.EXPERT_DEFAULT_MESSAGE, message)
        
        elif cross_message_verification_status == constants.VERIFIED:
            print("❌ Branch: Already verified - sending already verified message")
            byoeb_expert_messages = self.__create_expert_message(self.EXPERT_ALREADY_VERIFIED_MESSAGE, message)

        elif (reply_context.message_category == MessageCategory.BOT_TO_EXPERT_VERIFICATION.value
            and reply_context.additional_info[constants.VERIFICATION_STATUS] == constants.PENDING
            and (message.message_context.message_english_text or message.message_context.message_source_text) not in self.button_titles):
            print("🔄 Branch: Expert provided correction after clicking NO - generating corrected answer")
            # Expert provided correction - generate corrected answer and send to user, thank expert
            correction = message.message_context.message_english_text
            verification_message = reply_context.reply_english_text
            print(f"🔧 Original verification message: '{verification_message}'")
            print(f"🔧 Correction text: '{correction}'")
            
            print(f"🔧 DEBUG: Original verification text for correction (after NO): '{verification_message}'")
            parsed_message = self.__parse_message_patient_info(verification_message)
            print(f"🔧 DEBUG: Parsed verification message for correction (after NO): {parsed_message}")
            
            if "Question" not in parsed_message or "Bot_Answer" not in parsed_message:
                print(f"❌ ERROR: Question or Bot_Answer not found in parsed message (after NO). Available keys: {list(parsed_message.keys())}")
                print(f"🔧 DEBUG: Attempting fallback parsing for correction (after NO)...")
                # Try original parsing methods as fallback
                parsed_message = self.__parse_message(verification_message)
                if "Question" not in parsed_message or "Bot_Answer" not in parsed_message:
                    parsed_message = self.__parse_message_alternative(verification_message)
                print(f"🔧 DEBUG: Fallback parsed message for correction (after NO): {parsed_message}")
                
            question = parsed_message.get("Question", "")
            bot_answer = parsed_message.get("Bot_Answer", "")
            
            if not question or not bot_answer:
                print(f"❌ ERROR: Could not extract question or bot answer from verification message for correction (after NO)")
                # Try to extract from additional_info template parameters as fallback
                template_params = reply_context.additional_info.get("template_parameters", [])
                print(f"🔧 DEBUG: Template parameters for correction (after NO): {template_params}")
                if len(template_params) >= 2:
                    # template_params should be [verification_question, verification_bot_answer]
                    question = template_params[0] if not question else question
                    bot_answer = template_params[1] if not bot_answer else bot_answer
                    print(f"🔧 DEBUG: Extracted from template_parameters (after NO) - question: '{question}', bot_answer: '{bot_answer}'")
                
            print(f"🔧 DEBUG: Final extracted for correction (after NO) - question: '{question}', bot_answer: '{bot_answer}'")
            
            user_prompt = self.__get_user_prompt(
                question,
                bot_answer,
                correction
            )
            # Debug: Print exact text being passed to LLM for correction
            print(f"🔧 DEBUG: EXACT TEXT BEING CORRECTED BY LLM (after NO):")
            print(f"     Question: '{question}'")
            print(f"     Original Bot Answer: '{bot_answer}'")
            print(f"     Expert Correction: '{correction}'")
            print(f"     Final User Prompt to LLM: '{user_prompt}'")
            
            augmented_prompts = self.__augment(user_prompt)
            llm_response, response_text = await llm_client.agenerate_response(augmented_prompts)
            print(f"🔧 LLM corrected response: '{response_text}'")

            user_lang_here = message.cross_conversation_context.get(constants.USER, {}).get('user_language', 'en')
            
            # Debug: Show what's in reply_context.additional_info
            print(f"🔍 DEBUG [Expert NO - checking additional_info]:")
            if reply_context and reply_context.additional_info:
                print(f"     reply_context.additional_info keys: {list(reply_context.additional_info.keys())}")
                print(f"     has is_audio_query: {'is_audio_query' in reply_context.additional_info}")
                if 'is_audio_query' in reply_context.additional_info:
                    print(f"     is_audio_query value: {reply_context.additional_info['is_audio_query']}")
            else:
                print(f"     reply_context.additional_info is None or empty")
            
            # Check if original user query was audio from the stored flag in reply context
            is_audio_query = reply_context.additional_info.get("is_audio_query", False) if reply_context and reply_context.additional_info else False
            print(f"🎤 DEBUG [Expert NO correction]: Original user query was audio: {is_audio_query}")
            
            # Check if user is active (needed to decide if Question prefix is required)
            from byoeb.chat_app.configuration.dependency_setup import user_db_service
            from byoeb.services.chat.message_handlers.user_flow_handlers.send import ByoebUserSendResponse
            user_no = message.cross_conversation_context.get(constants.USER, {})
            user_id_for_active_check_no = user_no.get("user_id")
            send_handler_no = ByoebUserSendResponse(user_db_service, None)
            is_active_user_no = await send_handler_no.is_active_user(user_id_for_active_check_no)
            print(f"🎤 DEBUG [Expert NO correction]: User is_active_user: {is_active_user_no}")
            
            # Format the corrected answer with Question/Answer format
            # Include Question prefix for: 1) audio queries, OR 2) inactive users (who get template messages)
            # Keep English version for database storage
            if is_audio_query or not is_active_user_no:
                formatted_response_en = f"Question: {question}\nAnswer: {response_text}"
                print(f"🎤 DEBUG [Expert NO correction]: Including Question prefix (audio={is_audio_query}, inactive={not is_active_user_no})")
            else:
                formatted_response_en = response_text
            
            # Format response based on the user language for display
            formatted_response = formatted_response_en  # Default to English
            # if user_lang_here == "hi":
            #     formatted_response = f"प्रश्न: {question}\nउत्तर: {response_text}"
            # elif user_lang_here == "kn":
            #     formatted_response = f"ಪ್ರಶ್ನೆ: {question}\nಉತ್ತರ: {response_text}"

            # Send thank you message to expert
            byoeb_expert_messages = self.__create_expert_message(
                self.EXPERT_THANK_YOU_MESSAGE,
                message,
                None,  # Remove emoji reactions as requested
                constants.VERIFIED
            )
            
            # Send corrected answer to user
            byoeb_user_messages = await self.__create_user_message(
                formatted_response,
                message,
                None,  # Remove emoji reactions as requested
                constants.VERIFIED,
                [],  # Empty list to suppress related questions in final verified answer
                formatted_response_en  # Pass English version for database storage
            )

            print("This is the byoeb user message", byoeb_user_messages)
            print("done here")

        elif (reply_context.message_category == MessageCategory.BOT_TO_EXPERT_VERIFICATION.value
            and reply_context.additional_info[constants.VERIFICATION_STATUS] == constants.PENDING
            and (message.message_context.message_english_text or message.message_context.message_source_text) == self.yes):
            print("✅ Branch: Expert clicked YES - sending approved answer to user and thank you to expert")
            
            # Parse the verification message to get the original answer
            # print(f"🔧 DEBUG: Original verification text: '{reply_context.reply_english_text}'")
            parsed_message = self.__parse_message_patient_info(reply_context.reply_english_text)
            # print(f"🔧 DEBUG: Parsed verification message: {parsed_message}")
            
            if "Bot_Answer" not in parsed_message:
                print(f"❌ ERROR: Bot_Answer not found in parsed message. Available keys: {list(parsed_message.keys())}")
                print(f"🔧 DEBUG: Attempting fallback parsing...")
                # Try original parsing methods as fallback
                parsed_message = self.__parse_message(reply_context.reply_english_text)
                if "Bot_Answer" not in parsed_message:
                    parsed_message = self.__parse_message_alternative(reply_context.reply_english_text)
                print(f"🔧 DEBUG: Fallback parsed message: {parsed_message}")
                
            question = parsed_message.get("Question", "")
            bot_answer = parsed_message.get("Bot_Answer", "")
            
            if not bot_answer or not question:
                print(f"❌ ERROR: Could not extract question or bot answer from verification message")
                # Try to extract from additional_info template parameters as fallback
                template_params = reply_context.additional_info.get("template_parameters", [])
                # print(f"🔧 DEBUG: Template parameters: {template_params}")
                if len(template_params) >= 2:
                    # template_params should be [verification_question, verification_bot_answer]
                    question = template_params[0] if not question else question  # First parameter is the question
                    bot_answer = template_params[1] if not bot_answer else bot_answer  # Second parameter is the bot answer
                    print(f"🔧 DEBUG: Extracted from template_parameters - question: '{question}', bot_answer: '{bot_answer}'")
                
            print(f"🔧 DEBUG: Final extracted question: '{question}' bot_answer: '{bot_answer}'")
            print(f"🔧 DEBUG: Expert thank you message: '{self.EXPERT_THANK_YOU_MESSAGE}'")
            
            # Get related questions from expert verification message if available
            related_questions = reply_context.additional_info.get(constants.RELATED_QUESTIONS, {})
            
            # Send thank you message to expert
            byoeb_expert_messages = self.__create_expert_message(
                self.EXPERT_THANK_YOU_MESSAGE,
                message,
                None,  # Remove emoji reactions as requested
                constants.VERIFIED
            )
            
            print(f"🔧 DEBUG: Created expert message with text: '{self.EXPERT_THANK_YOU_MESSAGE}'")

            user_lang_here = message.cross_conversation_context.get(constants.USER, {}).get('user_language', 'en')
            print(f"Translating bot answer to user's language: {user_lang_here}")

            # Debug: Show what's in reply_context.additional_info
            print(f"🔍 DEBUG [Expert YES - checking additional_info]:")
            if reply_context and reply_context.additional_info:
                print(f"     reply_context.additional_info keys: {list(reply_context.additional_info.keys())}")
                print(f"     has is_audio_query: {'is_audio_query' in reply_context.additional_info}")
                if 'is_audio_query' in reply_context.additional_info:
                    print(f"     is_audio_query value: {reply_context.additional_info['is_audio_query']}")
            else:
                print(f"     reply_context.additional_info is None or empty")
            
            # Check if original user query was audio from the stored flag in reply context
            is_audio_query = reply_context.additional_info.get("is_audio_query", False) if reply_context and reply_context.additional_info else False
            print(f"🎤 DEBUG [Expert YES approval]: Original user query was audio: {is_audio_query}")

            # Check if user is active (needed to decide if Question prefix is required)
            from byoeb.chat_app.configuration.dependency_setup import user_db_service
            from byoeb.services.chat.message_handlers.user_flow_handlers.send import ByoebUserSendResponse
            user = message.cross_conversation_context.get(constants.USER, {})
            user_id_for_active_check = user.get("user_id")
            send_handler_early = ByoebUserSendResponse(user_db_service, None)
            is_active_user_early = await send_handler_early.is_active_user(user_id_for_active_check)
            print(f"🎤 DEBUG [Expert YES approval]: User is_active_user: {is_active_user_early}")

            # Format bot answer with Question/Answer format
            # Include Question prefix for: 1) audio queries, OR 2) inactive users (who get template messages)
            # Keep English version for database storage
            if is_audio_query or not is_active_user_early:
                formatted_bot_answer_en = f"Question: {question}\nAnswer: {bot_answer}"
                print(f"🎤 DEBUG [Expert YES approval]: Including Question prefix (audio={is_audio_query}, inactive={not is_active_user_early})")
            else:
                formatted_bot_answer_en = bot_answer
            
            # Format bot answer based on user language for display
            formatted_bot_answer = formatted_bot_answer_en  # Default to English
            # if user_lang_here == "hi":
            #     formatted_bot_answer = f"प्रश्न: {question}\nउत्तर: {bot_answer}"
            # elif user_lang_here == "kn":
            #     formatted_bot_answer = f"ಪ್ರಶ್ನೆ: {question}\nಉತ್ತರ: {bot_answer}"
            
            # Translate bot answer to user's language before sending
            from byoeb.chat_app.configuration.dependency_setup import text_translator
            print("here now, ", formatted_bot_answer)
            translated_bot_answer = await text_translator.atranslate_text(
                input_text=formatted_bot_answer,
                source_language="en",
                target_language=message.cross_conversation_context.get(constants.USER, {}).get("user_language", "en")
            )
            # TODO see here what is the output of translation

            # Generate TTS audio for the translated text (FIX: Add missing audio generation)
            media_additional_info = {}
            user = message.cross_conversation_context.get(constants.USER, {})
            user_language = user.get("user_language", "en")
            
            try:
                from byoeb.chat_app.configuration.dependency_setup import tts_service
                audio_url = await tts_service.generate_audio_url(
                    text=translated_bot_answer,
                    language=user_language,
                )
                if audio_url:
                    media_additional_info = {
                        "audio_url": audio_url,  # Store SAS URL for QikChat
                        constants.MIME_TYPE: "audio/wav"
                    }
                    print(f"🔧 DEBUG: Audio message generated successfully for YES flow with SAS URL")
                else:
                    media_additional_info = {}
                    print(f"⚠️ DEBUG: TTS service returned no audio URL for YES flow")
            except Exception as e:
                print(f"❌ DEBUG: Error generating audio message for YES flow: {e}")
                # Continue without audio if TTS fails
                media_additional_info = {}
            
            # NEW FLOW: Send approved answer to user (using already translated text)
            # Check if user is active before deciding message type
            from byoeb.chat_app.configuration.dependency_setup import user_db_service
            from byoeb.services.chat.message_handlers.user_flow_handlers.send import ByoebUserSendResponse
            
            user_id = user.get("user_id")
            user_language = user.get("user_language", "en")
            
            # Check if user is active (hasn't been inactive for 24 hours)
            send_handler = ByoebUserSendResponse(user_db_service, None)  # message_db_service not needed for activity check
            is_active_user = await send_handler.is_active_user(user_id)
            # is_active_user = False #TODO
            print(f"🔧 User {user_id} is_active_user: {is_active_user}")
            
            # We need to create the user message manually to avoid double translation
            user_obj = User(
                user_id=user.get("user_id"),
                user_type=user.get("user_type"),
                user_language=user.get("user_language", "en"),
                phone_number_id=user.get("phone_number_id")
            )
            print("COMING HERE 3")
            # Create message context (always start as regular text)
            if user_language == "en":
                user_language = user_language + "_US"
            
            # Parse translated text for Hindi/Kannada template parameters
            template_question = question
            template_answer = bot_answer
            if user_obj.user_language in ["hi", "kn"]:
                parsed_translated = self.__parse_translated_text(translated_bot_answer, user_obj.user_language)
                if parsed_translated.get("Question") and parsed_translated.get("Answer"):
                    template_question = parsed_translated["Question"]
                    template_answer = parsed_translated["Answer"]
                    print(f"🔧 DEBUG: Using translated template params (case 3) - Q: '{template_question}', A: '{template_answer}'")
            
            message_context = MessageContext(
                message_id=str(uuid.uuid4()),
                message_type=MessageTypes.TEMPLATE_BUTTON.value,
                message_english_text=formatted_bot_answer_en,  # English version for database
                message_source_text=translated_bot_answer,  # Already translated text
                additional_info=media_additional_info if is_active_user else {
                    constants.TEMPLATE_NAME: "bot_temp",
                    constants.TEMPLATE_LANGUAGE: user_language,
                    constants.TEMPLATE_PARAMETERS: [template_question, template_answer]
                }
            )
            
            # Fix: Use the same approach as __create_user_message() - take the last message and create reply context
            reply_to_user_messages_context = message.cross_conversation_context.get(constants.MESSAGES_CONTEXT)
            if reply_to_user_messages_context:
                # Get the most recent message (like __create_user_message does for VERIFIED status)
                reply_to_user_message_context = ByoebMessageContext.model_validate(reply_to_user_messages_context[-1])
                print(f"🔧 DEBUG: Using last message in conversation context: {reply_to_user_message_context.message_context.message_id}")
                print(f"🔧 DEBUG: Last message category: '{reply_to_user_message_context.message_category}'")
                
                # Create proper reply context that tags the original user question (same as __create_user_message)
                reply_context = self.__create_user_reply_context(
                    message,
                    reply_to_user_message_context,
                    None,  # emoji
                    constants.VERIFIED
                )
                print(f"🔧 DEBUG: Created reply_context with reply_id: {reply_context.reply_id}")
            else:
                # Fallback to basic reply context if no conversation context
                reply_context = ReplyContext(
                    reply_id=message.reply_context.reply_id if message.reply_context else None,
                    additional_info={
                        constants.VERIFICATION_STATUS: constants.VERIFIED,
                        constants.RELATED_QUESTIONS: []
                    }
                )

            new_user_message = ByoebMessageContext(
                channel_type=message.channel_type,
                message_category=MessageCategory.BOT_TO_USER_RESPONSE.value,
                user=user_obj,
                message_context=message_context,
                reply_context=reply_context,  # Now uses the properly created reply context
                incoming_timestamp=message.incoming_timestamp,
            )
            
            # Handle inactive user template message - just prepare the message, send.py will handle sending
            if not is_active_user:
                print("📋 User is inactive for 24 hours, message prepared with template format")
                # Message is already prepared with TEMPLATE_BUTTON type and template params
                # send.py will handle the actual sending
                byoeb_user_messages = [new_user_message]
            else:
                print("🔘 User is active, will send regular message through normal flow")
                byoeb_user_messages = [new_user_message]
            
            print(f"🔧 DEBUG: Created user message with bot_answer: '{bot_answer}'")

        elif (reply_context.message_category == MessageCategory.BOT_TO_EXPERT_VERIFICATION.value
            and reply_context.additional_info[constants.VERIFICATION_STATUS] == constants.PENDING
            and (message.message_context.message_english_text or message.message_context.message_source_text) == self.no):
            print("❌ Branch: Expert clicked NO - asking for correction, notifying user")
            
            print(f"🔧 DEBUG: About to create expert correction message")
            print(f"🔧 DEBUG: EXPERT_ASK_FOR_CORRECTION = {self.EXPERT_ASK_FOR_CORRECTION}")
            # print(f"🔧 DEBUG: message type = {type(message)}")
            # print(f"🔧 DEBUG: cross_conversation_context = {message.cross_conversation_context}")
            
            # Expert rejected the answer - ask expert for correction
            try:
                byoeb_expert_messages = self.__create_expert_message(
                    self.EXPERT_ASK_FOR_CORRECTION,
                    message,
                    None,  # Remove emoji reactions as requested
                    constants.WAITING)
                print(f"✅ DEBUG: Expert message created successfully: {type(byoeb_expert_messages)}")
            except Exception as e:
                print(f"❌ DEBUG: Error creating expert message: {e}")
                import traceback
                traceback.print_exc()
                raise e

        elif (reply_context.message_category == MessageCategory.BOT_TO_EXPERT_VERIFICATION.value
            and reply_context.additional_info[constants.VERIFICATION_STATUS] == constants.WAITING
        ):
            print("🔄 Branch: Expert provided correction - generating corrected answer")
            # Expert provided correction - generate corrected answer and send to user, thank expert
            correction = message.message_context.message_english_text
            verification_message = reply_context.reply_english_text
            print(f"🔧 Original verification message: '{verification_message}'")
            print(f"🔧 Correction text: '{correction}'")
            
            print(f"🔧 DEBUG: Original verification text for correction: '{verification_message}'")
            parsed_message = self.__parse_message_patient_info(verification_message)
            print(f"🔧 DEBUG: Parsed verification message for correction: {parsed_message}")
            
            if "Question" not in parsed_message or "Bot_Answer" not in parsed_message:
                print(f"❌ ERROR: Question or Bot_Answer not found in parsed message. Available keys: {list(parsed_message.keys())}")
                print(f"🔧 DEBUG: Attempting fallback parsing for correction...")
                # Try original parsing methods as fallback
                parsed_message = self.__parse_message(verification_message)
                if "Question" not in parsed_message or "Bot_Answer" not in parsed_message:
                    parsed_message = self.__parse_message_alternative(verification_message)
                print(f"🔧 DEBUG: Fallback parsed message for correction: {parsed_message}")
                
            question = parsed_message.get("Question", "")
            bot_answer = parsed_message.get("Bot_Answer", "")
            
            if not question or not bot_answer:
                print(f"❌ ERROR: Could not extract question or bot answer from verification message for correction")
                # Try to extract from additional_info template parameters as fallback
                template_params = reply_context.additional_info.get("template_parameters", [])
                print(f"🔧 DEBUG: Template parameters for correction: {template_params}")
                if len(template_params) >= 2:
                    # template_params should be [verification_question, verification_bot_answer]
                    question = template_params[0] if not question else question
                    bot_answer = template_params[1] if not bot_answer else bot_answer
                    print(f"🔧 DEBUG: Extracted from template_parameters - question: '{question}', bot_answer: '{bot_answer}'")
                
            print(f"🔧 DEBUG: Final extracted for correction - question: '{question}', bot_answer: '{bot_answer}'")
            
            user_prompt = self.__get_user_prompt(
                question,
                bot_answer,
                correction
            )
            # Debug: Print exact text being passed to LLM for correction
            print(f"🔧 DEBUG: EXACT TEXT BEING CORRECTED BY LLM:")
            print(f"     Question: '{question}'")
            print(f"     Original Bot Answer: '{bot_answer}'")
            print(f"     Expert Correction: '{correction}'")
            print(f"     Final User Prompt to LLM: '{user_prompt}'")
            
            augmented_prompts = self.__augment(user_prompt)
            llm_response, response_text = await llm_client.agenerate_response(augmented_prompts)
            print(f"🔧 LLM corrected response: '{response_text}'")
            
            user_lang_here = message.cross_conversation_context.get(constants.USER, {}).get('user_language', 'en')

            # Debug: Show what's in reply_context.additional_info
            print(f"🔍 DEBUG [Expert custom - checking additional_info]:")
            if reply_context and reply_context.additional_info:
                print(f"     reply_context.additional_info keys: {list(reply_context.additional_info.keys())}")
                print(f"     has is_audio_query: {'is_audio_query' in reply_context.additional_info}")
                if 'is_audio_query' in reply_context.additional_info:
                    print(f"     is_audio_query value: {reply_context.additional_info['is_audio_query']}")
            else:
                print(f"     reply_context.additional_info is None or empty")
            
            # Check if original user query was audio from the stored flag in reply context
            is_audio_query = reply_context.additional_info.get("is_audio_query", False) if reply_context and reply_context.additional_info else False
            print(f"🎤 DEBUG [Expert custom correction]: Original user query was audio: {is_audio_query}")

            # Format the corrected answer with Question/Answer format
            # Keep English version for database storage
            if is_audio_query:
                formatted_response_en = f"Question: {question}\nAnswer: {response_text}"
            else:
                formatted_response_en = response_text
            
            # Format response based on the user language for display
            formatted_response = formatted_response_en  # Default to English
            # if user_lang_here == "hi":
            #     formatted_response = f"प्रश्न: {question}\nउत्तर: {response_text}"
            # elif user_lang_here == "kn":
            #     formatted_response = f"ಪ್ರಶ್ನೆ: {question}\nಉತ್ತರ: {response_text}"
            
            # Send thank you message to expert
            byoeb_expert_messages = self.__create_expert_message(
                self.EXPERT_THANK_YOU_MESSAGE,
                message,
                None,  # Remove emoji reactions as requested
                constants.VERIFIED
            )
            
            # Send corrected answer to user
            byoeb_user_messages = await self.__create_user_message(
                formatted_response,
                message,
                None,  # Remove emoji reactions as requested
                constants.VERIFIED,
                [],  # Empty list to suppress related questions in final verified answer
                formatted_response_en  # Pass English version for database storage
            )
        else:
            # print("❓ Branch: No matching condition - sending default message")
            # print(f"❓ Reply message category: {getattr(reply_context, 'message_category', 'None') if reply_context else 'No reply context'}")
            # print(f"❓ Verification status: {reply_context.additional_info.get(constants.VERIFICATION_STATUS) if reply_context and reply_context.additional_info else 'None'}")
            # Use both text fields for debugging
            message_text = message.message_context.message_english_text or message.message_context.message_source_text
            # print(f"❓ Message text: '{message_text}'")
            # print(f"❓ Message type: {message.message_context.message_type}")
            # print(f"❓ Button titles: {self.button_titles}")
            byoeb_expert_messages = self.__create_expert_message(self.EXPERT_DEFAULT_MESSAGE, message)
            
        # print(f"🔧 DEBUG: About to combine messages")
        # print(f"🔧 DEBUG: byoeb_user_messages type: {type(byoeb_user_messages)}, content: {byoeb_user_messages}")
        # print(f"🔧 DEBUG: byoeb_expert_messages type: {type(byoeb_expert_messages)}, content: {byoeb_expert_messages}")
        # print(f"🔧 DEBUG: read_reciept_message type: {type(read_reciept_message)}, content: {read_reciept_message}")
        
        try:
            # Include the original expert message so it gets stored as EXPERT_TO_BOT
            original_expert_message = messages[0]  # The original expert input message
            # Ensure the category is properly set as string, not tuple
            original_expert_message.message_category = MessageCategory.EXPERT_TO_BOT.value
            print(f"🔧 Including original expert message for storage: ID={original_expert_message.message_context.message_id}")
            print(f"🔧 Original expert message category: {getattr(original_expert_message, 'message_category', 'Not set')}")
            
            byoeb_messages = byoeb_user_messages + byoeb_expert_messages + [read_reciept_message, original_expert_message]
            # print(f"✅ DEBUG: Messages combined successfully")
        except Exception as e:
            print(f"❌ DEBUG: Error combining messages: {e}")
            print(f"❌ DEBUG: byoeb_user_messages is None: {byoeb_user_messages is None}")
            print(f"❌ DEBUG: byoeb_expert_messages is None: {byoeb_expert_messages is None}")
            import traceback
            traceback.print_exc()
            raise e
            
        print(f"📤 Generated messages: {len(byoeb_user_messages) if byoeb_user_messages else 0} user, {len(byoeb_expert_messages) if byoeb_expert_messages else 0} expert")
        print("=== END EXPERT GENERATE RESPONSE DEBUG ===\n")
        if self._successor:
            return await self._successor.handle(byoeb_messages)