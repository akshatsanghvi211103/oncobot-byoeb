import re
import json
import uuid
import byoeb.services.chat.constants as constants
from typing import List, Dict, Any
from datetime import datetime
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
    USER_WAITING_ANSWER_MESSAGES = bot_config["template_messages"]["user"]["waiting_answer"]
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

    def __parse_message(self, message: str) -> dict:
        pattern = r"\*Question\*:\s*(.*?)\n\*Bot_Answer\*:\s*(.*)"
        match = re.search(pattern, message)
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
        lines = message.strip().split('\n')
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
        if (status == constants.VERIFIED
            and cross_conv_message.reply_context is not None
            and cross_conv_message.reply_context.additional_info is not None
            and cross_conv_message.reply_context.additional_info.get(constants.VERIFICATION_STATUS) == constants.WAITING
        ):
            # For verified answers, reply to the original user question (not the waiting message)
            reply_id = cross_conv_message.reply_context.reply_id
            reply_type = None
            reply_additional_info = {
                constants.UPDATE_ID: cross_conv_message.message_context.message_id,
                constants.VERIFICATION_STATUS: status,
                constants.MODIFIED_TIMESTAMP: str(int(datetime.now().timestamp()))
            }

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
    ):
        from byoeb.chat_app.configuration.dependency_setup import speech_translator
        from byoeb.chat_app.configuration.dependency_setup import text_translator
        user_info_dict = byoeb_message.cross_conversation_context.get(constants.USER)
        user = User.model_validate(user_info_dict)
        user.user_type = self._regular_user_type
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
            message_en_text = text_message
            
            # Check if this is an expert correction case
            is_correction = (byoeb_message.reply_context 
                           and byoeb_message.reply_context.additional_info
                           and byoeb_message.reply_context.additional_info.get(constants.VERIFICATION_STATUS) == constants.WAITING)
            
            if is_correction:
                print("🔧 DEBUG: Expert correction case - preparing corrected message")
                # For expert corrections, translate the corrected response to user's language
                translated_text = await text_translator.atranslate_text(
                    input_text=text_message,
                    source_language="en",
                    target_language=user.user_language
                )
                
                # For expert corrections, send the actual corrected answer directly
                text_message = translated_text
            else:
                print("🔧 DEBUG: Expert approval case - preparing verified message")
                # For expert approvals, use the verified answer template with the translated response
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
                    message_id=str(uuid.uuid4()),  # Generate unique message ID
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
            parsed_message = self.__parse_message(verification_message)
            print(f"🔧 DEBUG: Parsed verification message for correction (after NO): {parsed_message}")
            
            if "Question" not in parsed_message or "Bot_Answer" not in parsed_message:
                print(f"❌ ERROR: Question or Bot_Answer not found in parsed message (after NO). Available keys: {list(parsed_message.keys())}")
                print(f"🔧 DEBUG: Attempting alternative parsing for correction (after NO)...")
                # Alternative parsing for new format
                parsed_message = self.__parse_message_alternative(verification_message)
                print(f"🔧 DEBUG: Alternative parsed message for correction (after NO): {parsed_message}")
                
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
            # print(f"🔧 Generated user prompt for LLM: '{user_prompt[:200]}...'")
            
            augmented_prompts = self.__augment(user_prompt)
            llm_response, response_text = await llm_client.agenerate_response(augmented_prompts)
            print(f"🔧 LLM corrected response: '{response_text}'")
            
            # Send thank you message to expert
            byoeb_expert_messages = self.__create_expert_message(
                self.EXPERT_THANK_YOU_MESSAGE,
                message,
                None,  # Remove emoji reactions as requested
                constants.VERIFIED
            )
            
            # Send corrected answer to user
            byoeb_user_messages = await self.__create_user_message(
                response_text,
                message,
                None,  # Remove emoji reactions as requested
                constants.VERIFIED,
                []  # Empty list to suppress related questions in final verified answer
            )

        elif (reply_context.message_category == MessageCategory.BOT_TO_EXPERT_VERIFICATION.value
            and reply_context.additional_info[constants.VERIFICATION_STATUS] == constants.PENDING
            and (message.message_context.message_english_text or message.message_context.message_source_text) == self.yes):
            print("✅ Branch: Expert clicked YES - sending approved answer to user and thank you to expert")
            
            # Parse the verification message to get the original answer
            print(f"🔧 DEBUG: Original verification text: '{reply_context.reply_english_text}'")
            parsed_message = self.__parse_message(reply_context.reply_english_text)
            print(f"🔧 DEBUG: Parsed verification message: {parsed_message}")
            
            if "Bot_Answer" not in parsed_message:
                print(f"❌ ERROR: Bot_Answer not found in parsed message. Available keys: {list(parsed_message.keys())}")
                print(f"🔧 DEBUG: Attempting alternative parsing...")
                # Alternative parsing for new format
                parsed_message = self.__parse_message_alternative(reply_context.reply_english_text)
                print(f"🔧 DEBUG: Alternative parsed message: {parsed_message}")
                
            bot_answer = parsed_message.get("Bot_Answer", "")
            if not bot_answer:
                print(f"❌ ERROR: Could not extract bot answer from verification message")
                # Try to extract answer from additional_info template parameters as fallback
                template_params = reply_context.additional_info.get("template_parameters", [])
                # print(f"🔧 DEBUG: Template parameters: {template_params}")
                if len(template_params) >= 2:
                    # template_params should be [verification_question, verification_bot_answer]
                    bot_answer = template_params[1]  # Second parameter is the bot answer
                    print(f"🔧 DEBUG: Extracted bot answer from template_parameters: '{bot_answer}'")
                
            print(f"🔧 DEBUG: Final extracted bot_answer: '{bot_answer}'")
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

            print(f"Translating bot answer to user's language: {message.cross_conversation_context.get(constants.USER, {}).get('user_language', 'en')}")

            # Translate bot answer to user's language before sending
            from byoeb.chat_app.configuration.dependency_setup import text_translator

            translated_bot_answer = await text_translator.atranslate_text(
                input_text=bot_answer,
                source_language="en",
                target_language=message.cross_conversation_context.get(constants.USER, {}).get("user_language", "en")
            )

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
            # We need to create the user message manually to avoid double translation
            user_obj = User(
                user_id=user.get("user_id"),
                user_type=user.get("user_type"),
                user_language=user.get("user_language", "en"),
                phone_number_id=user.get("phone_number_id")
            )
            
            message_context = MessageContext(
                message_id=str(uuid.uuid4()),
                message_type=MessageTypes.REGULAR_TEXT.value,
                message_english_text=bot_answer,  # Original English text
                message_source_text=translated_bot_answer,  # Already translated text
                additional_info=media_additional_info  # FIX: Include audio info
            )
            
            new_user_message = ByoebMessageContext(
                channel_type=message.channel_type,
                message_category=MessageCategory.BOT_TO_USER_RESPONSE.value,
                user=user_obj,
                message_context=message_context,
                reply_context=ReplyContext(
                    reply_id=message.reply_context.reply_id if message.reply_context else None,
                    additional_info={
                        constants.VERIFICATION_STATUS: constants.VERIFIED,
                        constants.RELATED_QUESTIONS: []
                    }
                ),
                incoming_timestamp=message.incoming_timestamp,
            )
            
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
            parsed_message = self.__parse_message(verification_message)
            print(f"🔧 DEBUG: Parsed verification message for correction: {parsed_message}")
            
            if "Question" not in parsed_message or "Bot_Answer" not in parsed_message:
                print(f"❌ ERROR: Question or Bot_Answer not found in parsed message. Available keys: {list(parsed_message.keys())}")
                print(f"🔧 DEBUG: Attempting alternative parsing for correction...")
                # Alternative parsing for new format
                parsed_message = self.__parse_message_alternative(verification_message)
                print(f"🔧 DEBUG: Alternative parsed message for correction: {parsed_message}")
                
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
            # print(f"🔧 Generated user prompt for LLM: '{user_prompt[:200]}...'")
            
            augmented_prompts = self.__augment(user_prompt)
            llm_response, response_text = await llm_client.agenerate_response(augmented_prompts)
            print(f"🔧 LLM corrected response: '{response_text}'")
            
            # Send thank you message to expert
            byoeb_expert_messages = self.__create_expert_message(
                self.EXPERT_THANK_YOU_MESSAGE,
                message,
                None,  # Remove emoji reactions as requested
                constants.VERIFIED
            )
            
            # Send corrected answer to user
            byoeb_user_messages = await self.__create_user_message(
                response_text,
                message,
                None,  # Remove emoji reactions as requested
                constants.VERIFIED,
                []  # Empty list to suppress related questions in final verified answer
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
            byoeb_messages = byoeb_user_messages + byoeb_expert_messages + [read_reciept_message]
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