import byoeb.services.chat.constants as constants
import byoeb.services.chat.utils as utils
from typing import List, Dict, Any
from byoeb_core.models.byoeb.message_context import ByoebMessageContext, MessageTypes
from byoeb.services.channel.base import BaseChannelService, MessageReaction
from byoeb.services.databases.mongo_db import UserMongoDBService, MessageMongoDBService
from byoeb.services.chat.message_handlers.base import Handler
from byoeb.services.channel.base import MessageReaction

class ByoebExpertSendResponse(Handler):
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
    
    def __modify_user_messages_context(
        self,
        user_messages_context: List[ByoebMessageContext]
    ):
        print(f"🔧 __modify_user_messages_context: Processing {len(user_messages_context)} messages")
        
        has_audio = False
        audio_message = None

        for user_message in user_messages_context:
            if (user_message.message_context.message_type == MessageTypes.REGULAR_AUDIO.value
                and utils.has_audio_additional_info(user_message)):
                has_audio = True
                audio_message = user_message
                break

        if not has_audio:
            print(f"🔧 No audio messages found, fixing reply contexts for user messages")
            # Instead of completely removing reply_context, try to find the original user question message ID
            for user_message in user_messages_context:
                if user_message.reply_context:
                    original_reply_id = user_message.reply_context.reply_id
                    print(f"🔧 Original reply_id: {original_reply_id}")
                    
                    # First check if the current reply_id already looks like a valid QikChat message ID
                    if original_reply_id and not original_reply_id.startswith(('uuid:', 'urn:', '{')) and len(original_reply_id) > 10:
                        print(f"🔧 Reply_id already looks like valid QikChat message ID, keeping it: {original_reply_id}")
                        # Keep the additional_info but remove emoji to avoid reactions
                        if user_message.reply_context.additional_info:
                            user_message.reply_context.additional_info.pop(constants.EMOJI, None)
                        continue
                    
                    # Try to find the original user question from cross conversation context
                    if (hasattr(user_message, 'cross_conversation_context') and 
                        user_message.cross_conversation_context and 
                        'messages_context' in user_message.cross_conversation_context):
                        
                        messages_context = user_message.cross_conversation_context['messages_context']
                        if messages_context and len(messages_context) > 0:
                            # The first message should be the original user question
                            original_message = messages_context[0]
                            if isinstance(original_message, dict):
                                # Look for the actual Qikchat message ID from the original user question
                                if 'reply_context' in original_message and original_message['reply_context']:
                                    original_question_id = original_message['reply_context'].get('reply_id')
                                    if original_question_id and not original_question_id.startswith(('uuid:', 'urn:', '{')) and len(original_question_id) > 10:
                                        print(f"🔧 Found original user question ID: {original_question_id}")
                                        user_message.reply_context.reply_id = original_question_id
                                        # Keep the additional_info but remove emoji to avoid reactions
                                        if user_message.reply_context.additional_info:
                                            user_message.reply_context.additional_info.pop(constants.EMOJI, None)
                                        continue
                    
                    print(f"🔧 Could not find valid original user question ID, removing reply_context")
                    user_message.reply_context = None
            return user_messages_context

        print(f"🔧 Audio message found, reordering with audio first")
        new_contexts = [audio_message] 
        for user_message in user_messages_context:
            if user_message != audio_message:
                new_context = user_message.__deepcopy__()
                # Keep reply_context for all messages to ensure proper tagging
                print(f"🔧 Keeping reply_context for text/interactive message: {new_context.reply_context.reply_id if new_context.reply_context else 'None'}")
                new_contexts.append(new_context)

        return new_contexts
    
    def __prepare_db_queries(
        self,
        byoeb_user_messages: List[ByoebMessageContext],
        byoeb_expert_messages: List[ByoebMessageContext],
    ):
        print(f"🗄️ __prepare_db_queries: Preparing queries for {len(byoeb_user_messages) if byoeb_user_messages else 0} user messages and {len(byoeb_expert_messages) if byoeb_expert_messages else 0} expert messages")
        
        # Prepare all messages that need to be stored in database
        all_messages_to_store = []
        
        # Add user messages (verified answers) if they exist
        if byoeb_user_messages:
            print(f"🗄️ AUDIO_DEBUG: Checking {len(byoeb_user_messages)} user messages for audio processing")
            for i, msg in enumerate(byoeb_user_messages):
                has_audio = (hasattr(msg.message_context, 'additional_info') and 
                           msg.message_context.additional_info and 
                           'audio_url' in msg.message_context.additional_info)
                print(f"🗄️ AUDIO_DEBUG: User message {i+1}: ID={msg.message_context.message_id}, has_audio={has_audio}")
            
            all_messages_to_store.extend(byoeb_user_messages)
            print(f"🗄️ Added {len(byoeb_user_messages)} user response messages for storage")
        
        # Add expert messages (expert's responses: YES/NO/correction and bot responses to expert)
        if byoeb_expert_messages:
            all_messages_to_store.extend(byoeb_expert_messages)
            print(f"🗄️ Added {len(byoeb_expert_messages)} expert messages for storage")
        
        # Create database storage queries for all messages
        message_create_queries = []
        message_update_queries = []
        
        if all_messages_to_store:
            try:
                # DEBUG: Show what messages we're storing for expert flow
                print(f"\n=== EXPERT HANDLER MESSAGE STORAGE DEBUG ===")
                print(f"📊 Total messages to store: {len(all_messages_to_store)}")
                for i, msg in enumerate(all_messages_to_store):
                    msg_text = msg.message_context.message_english_text or msg.message_context.message_source_text
                    has_audio = (hasattr(msg.message_context, 'additional_info') and 
                               msg.message_context.additional_info and 
                               'audio_url' in msg.message_context.additional_info)
                    qikchat_audio_id = (msg.message_context.additional_info.get('qikchat_audio_id') 
                                      if hasattr(msg.message_context, 'additional_info') and msg.message_context.additional_info 
                                      else None)
                    
                    print(f"  {i+1}. ID: {msg.message_context.message_id}")
                    print(f"     Category: {getattr(msg, 'message_category', 'NO_CATEGORY')}")
                    print(f"     Type: {msg.message_context.message_type}")
                    print(f"     Has Audio: {has_audio}")
                    if qikchat_audio_id:
                        print(f"     QikChat Audio ID: {qikchat_audio_id}")
                    print(f"     Text: '{(msg_text or '')[:50]}...'")
                print("=== END EXPERT HANDLER DEBUG ===\n")
                
                # CREATE queries for new messages (same pattern as user flow handlers)
                message_create_queries = self._message_db_service.message_create_queries(all_messages_to_store)
                print(f"🗄️ Generated {len(message_create_queries)} CREATE queries")
                
                # UPDATE queries for existing messages (existing logic)
                if byoeb_user_messages and byoeb_expert_messages:
                    # Use the first expert message for the update queries (the bot response to expert)
                    primary_expert_message = byoeb_expert_messages[0]
                    print(f"🗄️ Calling correction_update_query")
                    correction_queries = self._message_db_service.correction_update_query(byoeb_user_messages, primary_expert_message)
                    print(f"🗄️ Calling verification_status_update_query")
                    verification_queries = self._message_db_service.verification_status_update_query(byoeb_user_messages, primary_expert_message)
                    message_update_queries = correction_queries + verification_queries
                    print(f"🗄️ Generated {len(message_update_queries)} UPDATE queries")
                
                print(f"🗄️ Database queries prepared successfully")
            except Exception as e:
                print(f"❌ Error preparing database queries: {e}")
                import traceback
                traceback.print_exc()
                message_create_queries = []
                message_update_queries = []
        
        # Use the first expert message for user activity update (any expert message will do)
        user_update_queries = []
        if byoeb_expert_messages:
            user_update_queries = [self._user_db_service.user_activity_update_query(byoeb_expert_messages[0].user)]
        return {
            constants.MESSAGE_DB_QUERIES: {
                constants.CREATE: message_create_queries,
                constants.UPDATE: message_update_queries
            },
            constants.USER_DB_QUERIES: {
                constants.UPDATE: user_update_queries
            }
        }
        
    async def __handle_user(
        self,
        channel_service: BaseChannelService,
        user_messages_context: List[ByoebMessageContext]
    ):
        print(f"📤 __handle_user: Processing {len(user_messages_context)} user messages")
        
        # Create message reactions only if reply_context exists and has emoji
        message_reactions = []
        for user_message in user_messages_context:
            if (user_message.reply_context and 
                user_message.reply_context.additional_info and 
                user_message.reply_context.additional_info.get(constants.EMOJI) is not None):
                try:
                    reaction = MessageReaction(
                        reaction=user_message.reply_context.additional_info.get(constants.EMOJI),
                        message_id=user_message.reply_context.reply_id,
                        phone_number_id=user_message.user.phone_number_id
                    )
                    message_reactions.append(reaction)
                except Exception as e:
                    print(f"❌ Error creating MessageReaction: {e}")
                    continue
        if message_reactions:  # Proceed only if there are valid reactions
            print(f"📤 Sending {len(message_reactions)} message reactions first")
            reaction_requests = channel_service.prepare_reaction_requests(message_reactions)
            await channel_service.send_requests(reaction_requests)
        
        responses = []
        message_ids = []
        modified_user_messages_context = self.__modify_user_messages_context(user_messages_context)
        print(f"📤 After modification: {len(modified_user_messages_context)} messages to send")
        
        for i, user_message in enumerate(modified_user_messages_context):
            print(f"📤 Preparing request for message {i+1}/{len(modified_user_messages_context)}")
            print(f"📤 Message type: {user_message.message_context.message_type}")
            print(f"📤 Message source text length: {len(user_message.message_context.message_source_text) if user_message.message_context.message_source_text else 0}")
            print(f"📤 Has reply_context: {user_message.reply_context is not None}")
            if user_message.reply_context:
                print(f"📤 Reply ID: {user_message.reply_context.reply_id}")
            
            try:
                requests = await channel_service.prepare_requests(user_message)
                print(f"📤 Successfully prepared {len(requests)} requests for message {i+1}")
                response, message_id = await channel_service.send_requests(requests)
                print(f"📤 Successfully sent message {i+1}, got response: {len(response) if response else 0} items, message_id: {message_id}")
                responses.extend(response)
                message_ids.extend(message_id)
            except Exception as e:
                print(f"❌ Error processing message {i+1}: {e}")
                import traceback
                traceback.print_exc()

        # CRITICAL FIX: Update message IDs with QikChat IDs after sending
        print(f"🔧 FINAL_ANSWER_ID_FIX: Updating {len(modified_user_messages_context)} message IDs with QikChat IDs")
        print(f"🔧 FINAL_ANSWER_ID_FIX: Available QikChat IDs: {message_ids}")
        
        for i, user_message in enumerate(modified_user_messages_context):
            original_id = user_message.message_context.message_id
            has_audio = (hasattr(user_message.message_context, 'additional_info') and 
                        user_message.message_context.additional_info and 
                        'audio_url' in user_message.message_context.additional_info)
            
            print(f"🔧 FINAL_ANSWER_ID_FIX: Processing message {i+1}")
            print(f"   - Original ID: {original_id}")
            print(f"   - Has audio: {has_audio}")
            print(f"   - Message type: {user_message.message_context.message_type}")
            
            if has_audio and len(message_ids) >= 2:
                # This message generated 2 QikChat IDs (text + audio)
                text_id = message_ids[0]  # First ID is for text request
                audio_id = message_ids[1]  # Second ID is for audio request
                
                print(f"🔧 FINAL_ANSWER_ID_FIX: Text+Audio message detected")
                print(f"   - Text QikChat ID: {text_id}")
                print(f"   - Audio QikChat ID: {audio_id}")
                
                # Update the main message with text ID (this will create the text database entry)
                user_message.message_context.message_id = text_id
                
                # Store the audio ID in additional_info so it can be used for the audio database entry
                if 'qikchat_audio_id' not in user_message.message_context.additional_info:
                    user_message.message_context.additional_info['qikchat_audio_id'] = audio_id
                    print(f"🔧 FINAL_ANSWER_ID_FIX: Stored audio ID in additional_info: {audio_id}")
                
                print(f"🔧 FINAL_ANSWER_ID_FIX: Message {i+1} ID updated: {original_id} -> {text_id} (text), audio ID: {audio_id}")
            elif len(message_ids) > i:
                # Single message, use the corresponding QikChat ID
                qikchat_id = message_ids[i]
                user_message.message_context.message_id = qikchat_id
                print(f"🔧 FINAL_ANSWER_ID_FIX: Message {i+1} ID updated: {original_id} -> {qikchat_id}")

        # Only add final emoji reactions if we have messages with additional_info that contains emoji
        emoji = None
        if (user_messages_context and 
            user_messages_context[0].message_context.additional_info):
            emoji = user_messages_context[0].message_context.additional_info.get(constants.EMOJI)
            
        if emoji is None:
            print(f"📤 No emoji found, skipping final reaction")
            return responses
            
        print(f"📤 Adding final emoji reactions for {len(message_ids)} messages")
        message_reactions = [
            MessageReaction(
                reaction=emoji,
                message_id=message_id,
                phone_number_id=user_messages_context[0].user.phone_number_id
            )
            for message_id in message_ids if message_id is not None
        ]
        reaction_requests = channel_service.prepare_reaction_requests(message_reactions)
        await channel_service.send_requests(reaction_requests)
        return responses

    async def __handle_expert(
        self,
        channel_service: BaseChannelService,
        expert_message_context: ByoebMessageContext
    ):
        # Store original expert message ID before it gets updated by sending
        original_expert_id = expert_message_context.message_context.message_id
        
        expert_requests = await channel_service.prepare_requests(expert_message_context)
        responses, message_ids = await channel_service.send_requests(expert_requests)

        # EXPERT_ID_FIX: Extract QikChat message ID from response and update expert message
        if message_ids and len(message_ids) > 0 and message_ids[0] is not None:
            qikchat_expert_id = message_ids[0]
            print(f"🔧 EXPERT_ID_FIX: Updating expert message ID: {original_expert_id} -> {qikchat_expert_id}")
            
            # Update the message context with the QikChat ID
            expert_message_context.message_context.message_id = qikchat_expert_id
            new_expert_id = qikchat_expert_id
        else:
            print(f"⚠️ EXPERT_ID_FIX: No QikChat message ID received, keeping original: {original_expert_id}")
            new_expert_id = original_expert_id

        # Update message ID in database if it changed after sending to Qikchat
        if original_expert_id != new_expert_id:
            print(f"🔄 Updating expert message ID in database: {original_expert_id} -> {new_expert_id}")
            await self._message_db_service.update_message_id(original_expert_id, new_expert_id)

        # Check if reply_id is present and add reaction
        if (expert_message_context.reply_context
            and expert_message_context.reply_context.reply_id
            and expert_message_context.reply_context.additional_info
            and expert_message_context.reply_context.additional_info.get(constants.EMOJI)
        ):
            try:
                expert_reaction = MessageReaction(
                    reaction=expert_message_context.reply_context.additional_info.get(constants.EMOJI),
                    message_id=expert_message_context.reply_context.reply_id,
                    phone_number_id=expert_message_context.user.phone_number_id
                )
                expert_reaction_requests = channel_service.prepare_reaction_requests([expert_reaction])
                await channel_service.send_requests(expert_reaction_requests)
            except Exception as e:
                print(f"❌ Error creating expert MessageReaction: {e}")

        return responses
        
    async def handle(
        self,
        messages: List[ByoebMessageContext]
    ) -> Dict[str, Any]:
        print(f"\n=== EXPERT SEND RESPONSE DEBUG ===")
        print(f"📨 Processing {len(messages)} messages in send handler")
        for i, msg in enumerate(messages):
            user_type = msg.user.user_type if msg.user else "None"
            message_category = msg.message_category
            print(f"📨 Message {i+1}: user_type='{user_type}', category='{message_category}'")
        
        db_queries = {}
        read_receipt_messages = utils.get_read_receipt_byoeb_messages(messages)
        byoeb_user_messages = utils.get_user_byoeb_messages(messages)
        byoeb_expert_messages = utils.get_expert_byoeb_messages(messages)
        
        print(f"📨 After filtering: {len(read_receipt_messages)} read receipts, {len(byoeb_user_messages) if byoeb_user_messages else 0} user messages, {len(byoeb_expert_messages) if byoeb_expert_messages else 0} expert messages")
        
        # Special handling for expert-generated user messages
        # If we have no user messages but have messages with BOT_TO_USER_RESPONSE category, include them
        if (byoeb_user_messages is None or len(byoeb_user_messages) == 0):
            from byoeb.models.message_category import MessageCategory
            user_response_messages = [
                msg for msg in messages 
                if msg.message_category == MessageCategory.BOT_TO_USER_RESPONSE.value
            ]
            if user_response_messages:
                print(f"📨 Found {len(user_response_messages)} BOT_TO_USER_RESPONSE messages to send as user messages")
                byoeb_user_messages = user_response_messages
        
        byoeb_expert_message = byoeb_expert_messages[0]
        channel_service = self.get_channel_service(byoeb_expert_message.channel_type)
        await channel_service.amark_read(read_receipt_messages)
        expert_responses = await self.__handle_expert(channel_service, byoeb_expert_message)
        if byoeb_user_messages is not None and len(byoeb_user_messages) != 0:
            print(f"📨 Sending {len(byoeb_user_messages)} user messages")
            user_responses = await self.__handle_user(channel_service, byoeb_user_messages)
        else:
            print(f"📨 No user messages to send")
        db_queries = self.__prepare_db_queries(byoeb_user_messages, byoeb_expert_messages)
        print("=== END EXPERT SEND RESPONSE DEBUG ===\n")
        return db_queries