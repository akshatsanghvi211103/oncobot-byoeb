import asyncio
import byoeb.services.chat.constants as constants
import byoeb.utils.utils as b_utils
from datetime import datetime
from byoeb.chat_app.configuration.config import app_config
from byoeb.services.chat import utils
from byoeb.services.chat import mocks
from typing import Any, Dict, List
from byoeb_core.models.byoeb.message_context import ByoebMessageContext, MessageTypes
from byoeb.services.channel.base import BaseChannelService, MessageReaction
from byoeb.services.databases.mongo_db import UserMongoDBService, MessageMongoDBService
from byoeb.services.chat.message_handlers.base import Handler
from byoeb.services.channel.base import MessageReaction

class ByoebUserSendResponse(Handler):
    __max_last_active_duration_seconds: int = app_config["app"]["max_last_active_duration_seconds"]

    def __init__(
        self,
        user_db_service: UserMongoDBService,
        message_db_service: MessageMongoDBService,
    ):
        self._user_db_service = user_db_service
        self._message_db_service = message_db_service

    def get_channel_service(
        self,
        channel_type
    ) -> BaseChannelService:
        if channel_type == "whatsapp":
            from byoeb.services.channel.whatsapp import WhatsAppService
            return WhatsAppService()
        elif channel_type == "qikchat":
            from byoeb.services.channel.qikchat import QikchatService
            return QikchatService()
        return None

    def __prepare_db_queries(
        self,
        convs: List[ByoebMessageContext],
        byoeb_user_message: ByoebMessageContext,
    ):
        message_db_queries = {
            constants.CREATE: self._message_db_service.message_create_queries(convs)
        }
        qa = {
            constants.QUESTION: byoeb_user_message.reply_context.reply_english_text if byoeb_user_message.reply_context else None,
            constants.ANSWER: byoeb_user_message.message_context.message_english_text
        }
        print(f"Saving conversation history: Q: {qa[constants.QUESTION]} | A: {qa[constants.ANSWER][:100]}...")
        
        # Always use CREATE for new users, UPDATE for existing users
        # print(f"[DEBUG] _is_new_user on byoeb_user_message: {getattr(byoeb_user_message, '_is_new_user', None)}")
        is_new_user = getattr(byoeb_user_message, '_is_new_user', False)
        if is_new_user:
            user_db_queries = {
                constants.CREATE: [self._user_db_service.user_create_query(byoeb_user_message.user, qa)]
            }
            print(f"[LOGIC] Using CREATE query for new user {byoeb_user_message.user.phone_number_id}")
        else:
            user_db_queries = {
                constants.UPDATE: [self._user_db_service.user_activity_update_query(byoeb_user_message.user, qa)]
            }
            # print(f"[LOGIC] Using UPDATE query for existing user {byoeb_user_message.user.phone_number_id}")
        # print(f"[DEBUG] Prepared user_db_queries: {user_db_queries}")
        return {
            constants.MESSAGE_DB_QUERIES: message_db_queries,
            constants.USER_DB_QUERIES: user_db_queries
        }

    async def is_active_user(self, user_id: str, expert: bool = False):
        # if expert:
        #     return False
        try:
            result = await self._user_db_service.get_user_activity_timestamp(user_id)
            if result is None:
                # User doesn't exist in database yet - treat as inactive
                print(f"User {user_id} not found in database - treating as inactive")
                return False
                
            user_timestamp, cached = result
            last_active_duration_seconds = utils.get_last_active_duration_seconds(user_timestamp)
            print("Last active duration", last_active_duration_seconds)
            print("Cached", cached)
            if last_active_duration_seconds >= self.__max_last_active_duration_seconds and cached:
                print("Invalidating cache")
                await self._user_db_service.invalidate_user_cache(user_id)
                result = await self._user_db_service.get_user_activity_timestamp(user_id)
                if result is None:
                    print(f"User {user_id} still not found after cache invalidation - treating as inactive")
                    return False
                user_timestamp, cached = result
                print("Cached", cached)
                last_active_duration_seconds = utils.get_last_active_duration_seconds(user_timestamp)
                print("Last active duration", last_active_duration_seconds)
            if last_active_duration_seconds >= self.__max_last_active_duration_seconds:
                return False
            return True
        except Exception as e:
            print(f"Error checking user activity for {user_id}: {e}")
            # Default to inactive if there's an error
            return False
    
    async def __handle_expert(
        self,
        channel_service: BaseChannelService,
        expert_message_context: ByoebMessageContext
    ):
        print(f"🔧 Handling expert message for: {expert_message_context.user.phone_number_id}")
        print(f"🔧 Expert user_id: {expert_message_context.user.user_id}")
        
        is_active_user = await self.is_active_user(expert_message_context.user.user_id, expert=True)
        print(f"🔧 Expert is_active_user: {is_active_user}")
        
        # Set message type BEFORE prepare_requests so it generates the right format
        if not is_active_user:
            print("📋 Preparing template message for inactive expert")
            expert_message_context.message_context.message_type = MessageTypes.TEMPLATE_BUTTON.value
        else:
            print("🔘 Preparing interactive button for active expert")
        
        expert_requests = await channel_service.prepare_requests(expert_message_context)
        print(f"🔧 Expert prepare_requests returned {len(expert_requests)} messages")
        
        # Send all expert requests (may include continuation messages if split)
        responses, message_ids = await channel_service.send_requests(expert_requests)
        print("responses", responses)
        pending_emoji = expert_message_context.message_context.additional_info.get(constants.EMOJI)
        
        # Only create reactions if emoji is not None
        if pending_emoji is not None:
            message_reactions = [
                MessageReaction(
                    reaction=pending_emoji,
                    message_id=message_id,
                    phone_number_id=expert_message_context.user.phone_number_id
                )
                for message_id in message_ids if message_id is not None
            ]
            reaction_requests = channel_service.prepare_reaction_requests(message_reactions)
        else:
            print("📌 Skipping emoji reaction (emoji is None)")
            reaction_requests = []
        await channel_service.send_requests(reaction_requests)
        return responses

    async def __handle_user(
        self,
        channel_service: BaseChannelService,
        user_message_context: ByoebMessageContext
    ):
        # responses = [
        #     mocks.get_mock_whatsapp_response(user_message_context.user.phone_number_id)
        # ]
        # return responses
        message_ids = []
        print(f"🔍 HANDLE_USER: Processing {user_message_context.message_context.message_type}")
        user_requests = await channel_service.prepare_requests(user_message_context)
        print(f"🔍 HANDLE_USER: Prepared {len(user_requests)} requests")
        
        if user_message_context.message_context.message_type == MessageTypes.REGULAR_AUDIO.value:
            print(f"🎵 Sending audio message...")
            
            # Check if we have follow-up questions
            has_follow_up = user_message_context.message_context.additional_info.get("has_follow_up_questions", False)
            follow_up_questions = user_message_context.message_context.additional_info.get(constants.ROW_TEXTS, [])
            
            if has_follow_up and follow_up_questions:
                print(f"🎵📋 Audio message with {len(follow_up_questions)} follow-up questions")
                
                # Send audio message first
                user_message_copy = user_message_context.__deepcopy__()
                user_message_copy.reply_context = None
                audio_requests = await channel_service.prepare_requests(user_message_copy)
                response_audio, message_id_audio = await channel_service.send_requests(audio_requests)
                
                # Create and send interactive list for follow-up questions (TEXT ONLY)
                follow_up_context = user_message_context.__deepcopy__()
                follow_up_context.message_context.message_type = MessageTypes.INTERACTIVE_LIST.value
                follow_up_context.message_context.message_source_text = "Follow-up questions:"
                follow_up_context.message_context.message_english_text = "Follow-up questions:"
                # Keep reply_context for proper tagging of follow-up questions
                
                # CRITICAL: Remove audio URL from follow-up questions - they should be TEXT ONLY
                if hasattr(follow_up_context.message_context, 'additional_info'):
                    follow_up_context.message_context.additional_info.pop('tts_audio_url', None)
                    follow_up_context.message_context.additional_info.pop('has_audio_additional_info', None)
                
                follow_up_requests = await channel_service.prepare_requests(follow_up_context)
                response_followup, message_id_followup = await channel_service.send_requests(follow_up_requests)
                
                responses = response_audio + response_followup
                message_ids = message_id_audio + message_id_followup
                
            else:
                print(f"🎵 Audio message only (no follow-up questions)")
                # Since we now skip empty text requests, we only have audio request
                print(f"🎵 Found {len(user_requests)} audio requests to send")
                if len(user_requests) > 0:
                    response_audio, message_id_audio = await channel_service.send_requests(user_requests)
                    responses = response_audio
                    message_ids = message_id_audio
                else:
                    print(f"⚠️ No audio requests to send")
                    responses = []
                    message_ids = []
                
        else:
            # print(f"💬 Sending text/interactive message...")
            responses, message_ids = await channel_service.send_requests(user_requests)
            # print("user responses", responses)
        pending_emoji = user_message_context.message_context.additional_info.get(constants.EMOJI)
        message_reactions = [
            MessageReaction(
                reaction=pending_emoji,
                message_id=message_id,
                phone_number_id=user_message_context.user.phone_number_id
            )
            for message_id in message_ids if message_id is not None and pending_emoji is not None
        ]
        reaction_requests = channel_service.prepare_reaction_requests(message_reactions)
        await channel_service.send_requests(reaction_requests)
        return responses
    
    async def __handle_message_send_workflow(
        self,
        messages: List[ByoebMessageContext]
    ):
        from byoeb.models.message_category import MessageCategory
        
        verification_status = constants.VERIFICATION_STATUS
        read_receipt_messages = utils.get_read_receipt_byoeb_messages(messages)
        
        # CLASSIFICATION_FIX: Separate incoming vs outgoing messages
        incoming_user_messages = []  # Original user messages (to store in DB only)
        outgoing_user_messages = []  # Bot responses to user (to send and store)
        
        for msg in messages:
            if hasattr(msg, 'message_category'):
                if msg.message_category == MessageCategory.USER_TO_BOT.value:
                    incoming_user_messages.append(msg)
                    print(f"📥 INCOMING: {msg.message_context.message_type}, ID={msg.message_context.message_id}")
                elif msg.message_category == MessageCategory.BOT_TO_USER_RESPONSE.value:
                    outgoing_user_messages.append(msg)
                    print(f"📤 OUTGOING: {msg.message_context.message_type}, ID={msg.message_context.message_id}")
        
        # Use traditional utils for expert messages (unchanged)
        byoeb_expert_messages = utils.get_expert_byoeb_messages(messages)
        
        # For backward compatibility, use outgoing messages as "byoeb_user_messages" 
        byoeb_user_messages = outgoing_user_messages
        
        # Debug: Show message breakdown
        print(f"🔍 MESSAGE BREAKDOWN: Total={len(messages)}, Incoming={len(incoming_user_messages)}, Outgoing={len(byoeb_user_messages)}, Expert={len(byoeb_expert_messages)}, ReadReceipt={len(read_receipt_messages)}")
        for i, user_msg in enumerate(byoeb_user_messages):
            print(f"🔍 User message {i+1}: Type={user_msg.message_context.message_type}, ID={user_msg.message_context.message_id}")
        
        if len(byoeb_user_messages) == 0:
            raise Exception("No user messages found")
            
        byoeb_user_message = byoeb_user_messages[0]
        
        # Expert workflow enabled - will send verification messages to expert verifier
        channel_service = self.get_channel_service(byoeb_user_message.channel_type)
        print(f"🔧 DEBUG: Using channel_type='{byoeb_user_message.channel_type}' -> service={type(channel_service).__name__}")
        await channel_service.amark_read(read_receipt_messages)
        
        # Enable actual message sending (was in testing mode)
        print(f"💬 Sending response: {byoeb_user_message.message_context.message_english_text[:100]}...")
        print(f"🏷️ Query type: {byoeb_user_message.message_context.additional_info.get('query_type', 'medical')}")
        
        # Handle expert workflow if expert messages exist
        if len(byoeb_expert_messages) > 0:
            byoeb_expert_message = byoeb_expert_messages[0]
            print(f"👨‍⚕️ Found expert verification message for {byoeb_expert_message.user.phone_number_id}")
            
            if byoeb_user_message.channel_type != byoeb_expert_message.channel_type:
                raise Exception("Channel type mismatch")
                
            # Process each user message individually to maintain order and context
            user_responses = []
            for i, user_msg in enumerate(byoeb_user_messages):
                print(f"📤 Processing user message {i+1}/{len(byoeb_user_messages)}: {user_msg.message_context.message_type}")
                response = await self.__handle_user(channel_service, user_msg)
                if isinstance(response, list):
                    user_responses.extend(response)
                else:
                    user_responses.append(response)
                    
            expert_responses = await self.__handle_expert(channel_service, byoeb_expert_message)
            print(f"✅ Sent {len(byoeb_user_messages)} user messages and expert verifier message!")
            
        else:
            # Handle user-only workflow (most common case)
            print(f"📝 No expert messages found - handling {len(byoeb_user_messages)} user messages")
            
            # Process each user message individually to maintain order and context
            user_responses = []
            for i, user_msg in enumerate(byoeb_user_messages):
                print(f"📤 Processing user message {i+1}/{len(byoeb_user_messages)}: {user_msg.message_context.message_type}")
                response = await self.__handle_user(channel_service, user_msg)
                if isinstance(response, list):
                    user_responses.extend(response)
                else:
                    user_responses.append(response)
                    
            expert_responses = []
            # Create a mock expert message for the create_conv logic
            byoeb_expert_message = byoeb_user_message.__deepcopy__()
            byoeb_expert_message.message_context.additional_info = {verification_status: constants.VERIFIED}

        # print(f"🔧 DEBUG: user_responses type={type(user_responses)}, first_item_type={type(user_responses[0]) if user_responses else 'N/A'}")
        # if user_responses:
        #     print(f"🔧 DEBUG: first_response_content={user_responses[0]}")
        print(f"✅ Response sent successfully!")

        byoeb_user_verification_status = byoeb_expert_message.message_context.additional_info.get(verification_status)
        related_questions = byoeb_user_message.message_context.additional_info.get(constants.ROW_TEXTS)
        
        # CLASSIFICATION_PRESERVE: Don't overwrite existing additional_info, just update specific fields
        if not hasattr(byoeb_user_message.message_context, 'additional_info') or byoeb_user_message.message_context.additional_info is None:
            byoeb_user_message.message_context.additional_info = {}
        
        # Preserve existing additional_info and only update specific fields
        byoeb_user_message.message_context.additional_info.update({
            verification_status: byoeb_user_verification_status,
            constants.RELATED_QUESTIONS: related_questions
        })
        

        # print(f"🔧 DEBUG: About to call create_conv with user_responses type={type(user_responses)}")
        bot_to_user_convs = channel_service.create_conv(
            byoeb_user_message,
            user_responses,
            original_messages=byoeb_user_messages
        )
        # print(f"🔧 DEBUG: create_conv returned {len(bot_to_user_convs)} items, first_type={type(bot_to_user_convs[0]) if bot_to_user_convs else 'N/A'}")
        
        # Only create cross conv if we have expert responses
        if expert_responses:
            # Store original expert message ID before it gets updated
            original_expert_id = byoeb_expert_message.message_context.message_id
            print(f"🔧 EXPERT MESSAGE ID DEBUG:")
            print(f"   Original expert ID: {original_expert_id}")
            print(f"   Expert responses count: {len(expert_responses)}")
            if expert_responses:
                print(f"   First expert response: {expert_responses[0]}")
            
            byoeb_expert_verification_status = byoeb_expert_message.message_context.additional_info.get(verification_status)
            # AUDIO_PREFIX_FIX: Don't overwrite additional_info - preserve is_audio_query and other fields
            if byoeb_expert_message.message_context.additional_info is None:
                byoeb_expert_message.message_context.additional_info = {}
            byoeb_expert_message.message_context.additional_info[verification_status] = byoeb_expert_verification_status
            bot_to_expert_cross_convs = channel_service.create_cross_conv(
                byoeb_user_message,
                byoeb_expert_message,
                user_responses,
                expert_responses
            )
            
            # Note: Expert message ID is updated by create_cross_conv and will be stored with correct ID
            new_expert_id = byoeb_expert_message.message_context.message_id
            print(f"   Expert ID after create_cross_conv: {new_expert_id}")
            print(f"   ID changed: {original_expert_id != new_expert_id}")
            print(f"   ℹ️ Expert message will be stored in database with correct QikChat ID: {new_expert_id}")
            
            return bot_to_user_convs + bot_to_expert_cross_convs, byoeb_user_message
        else:
            return bot_to_user_convs, byoeb_user_message
    
    async def handle(
        self,
        messages: List[ByoebMessageContext]
    ) -> Dict[str, Any]:
        if messages is None or len(messages) == 0:
            return {}
        try:
            start_time = datetime.now().timestamp()
            convs, byoeb_user_message = await self.__handle_message_send_workflow(messages)
            
            # Create separate message objects for database storage
            from byoeb.models.message_category import MessageCategory
            
            # Create USER_TO_BOT message with original user question text
            if byoeb_user_message.reply_context and byoeb_user_message.reply_context.reply_english_text:
                # CLASSIFICATION_FIX: Try to find the original incoming user message with classification
                original_user_message = None
                for msg in messages:
                    if (hasattr(msg, 'message_category') and 
                        msg.message_category == MessageCategory.USER_TO_BOT.value and
                        msg.message_context.message_id == byoeb_user_message.reply_context.reply_id):
                        original_user_message = msg
                        print(f"🔍 CLASSIFICATION_FIX: Found original user message with ID {msg.message_context.message_id}")
                        break
                
                if original_user_message:
                    # Use the original message that has the classification
                    user_question_message = original_user_message.__deepcopy__()
                    print(f"🔍 CLASSIFICATION_FIX: Using original user message with preserved classification")
                else:
                    # Fallback: Create a copy for the user question
                    user_question_message = byoeb_user_message.__deepcopy__()
                    print(f"🔍 CLASSIFICATION_FIX: Original message not found, using fallback copy")
                
                user_question_message.message_category = MessageCategory.USER_TO_BOT.value
                
                # Set the message text to the original user question
                user_question_message.message_context.message_english_text = byoeb_user_message.reply_context.reply_english_text
                user_question_message.message_context.message_source_text = byoeb_user_message.reply_context.reply_source_text or byoeb_user_message.reply_context.reply_english_text
                
                # Use the actual QikChat message ID from reply context instead of generating new one
                # This preserves the original user question message ID for proper threading
                if byoeb_user_message.reply_context.reply_id:
                    user_question_message.message_context.message_id = byoeb_user_message.reply_context.reply_id
                    print(f"📎 Using original message ID from reply context: {byoeb_user_message.reply_context.reply_id}")
                else:
                    # Fallback to generated ID only if no reply_id available
                    import uuid
                    user_question_message.message_context.message_id = f"user_q_{uuid.uuid4().hex[:8]}"
                    print(f"⚠️ No reply_id found, using generated ID: {user_question_message.message_context.message_id}")
                
                # Set outgoing_timestamp for USER_TO_BOT message (uses incoming_timestamp or current time)
                if not hasattr(user_question_message, 'outgoing_timestamp') or user_question_message.outgoing_timestamp is None:
                    # For incoming user messages, use incoming_timestamp if available, otherwise current time
                    if hasattr(user_question_message, 'incoming_timestamp') and user_question_message.incoming_timestamp:
                        user_question_message.outgoing_timestamp = user_question_message.incoming_timestamp
                    else:
                        user_question_message.outgoing_timestamp = int(datetime.now().timestamp())
                
                print(f"🔧 Created USER_TO_BOT message:")
                print(f"   ID: {user_question_message.message_context.message_id}")
                print(f"   Text: '{user_question_message.message_context.message_english_text[:50]}...'")
                
                # Debug: Show final additional_info for user question message

                
                # Include both user question and bot response in conversation history
                all_convs = [user_question_message] + convs
            else:
                # Fallback: just include bot responses if no original question available
                print("⚠️ No original user question found in reply_context - storing bot responses only")
                all_convs = convs
            
            # DEBUG: Show what we're about to store
            print(f"\n=== USER HANDLER MESSAGE STORAGE DEBUG ===")
            print(f"📊 Total conversations to store: {len(all_convs)}")
            for i, conv in enumerate(all_convs):
                msg_text = conv.message_context.message_english_text or conv.message_context.message_source_text
                print(f"  {i+1}. ID: {conv.message_context.message_id}")
                print(f"     Category: {getattr(conv, 'message_category', 'NO_CATEGORY')}")
                print(f"     Type: {conv.message_context.message_type}")
                print(f"     Text: '{(msg_text or '')[:50]}...'")
            print("=== END USER HANDLER DEBUG ===\n")
            
            # Always prepare DB queries for conversation history, even in testing mode
            db_queries = self.__prepare_db_queries(all_convs, byoeb_user_message)
            
            end_time = datetime.now().timestamp()
            b_utils.log_to_text_file(f"Successfully send the message to the user and expert in {end_time - start_time} seconds")
            return db_queries
        except Exception as e:
            b_utils.log_to_text_file(f"Error in sending message to user and expert: {str(e)}")
            raise e