import asyncio
import logging
import uuid
import byoeb.services.chat.constants as constants
import byoeb.services.chat.utils as utils
import byoeb_integrations.channel.qikchat.request_payload as qik_req_payload
from byoeb.services.channel.base import BaseChannelService, MessageReaction
from byoeb_core.models.byoeb.message_context import (
    User,
    ByoebMessageContext,
    MessageContext,
    ReplyContext,
    MediaContext,
    MessageTypes
)
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime


class QikchatService(BaseChannelService):
    """
    Qikchat service implementation for BYOeB.
    
    Key Differences from WhatsApp Service:
    1. Different client type identifier
    2. Different request payload functions
    3. Simpler response handling (no complex WhatsApp response objects)
    4. Different authentication and configuration
    """
    __client_type = "qikchat"  # Different from "whatsapp"

    def __init__(self):
        """Initialize QikchatService with logger."""
        self.logger = logging.getLogger(self.__class__.__name__)

    def prepare_reaction_requests(
        self,
        message_reactions: List[MessageReaction]
    ) -> List[Dict[str, Any]]:
        """
        Prepare reaction requests for Qikchat.
        
        Key Differences from WhatsApp:
        1. Different reaction request format
        2. Simpler reaction structure
        """
        reactions = []
        for message_reaction in message_reactions:
            message_id = message_reaction.message_id
            phone_number = message_reaction.phone_number_id
            reaction = message_reaction.reaction
            
            reaction_request = qik_req_payload.get_qikchat_reaction_request(
                phone_number,
                message_id,
                reaction
            )
            reactions.append(reaction_request)
        return reactions
    
    def prepare_requests(
        self,
        byoeb_message: ByoebMessageContext
    ) -> List[Dict[str, Any]]:
        """
        Prepare message requests for Qikchat.
        
        Key Differences from WhatsApp:
        1. Uses Qikchat-specific request payload functions
        2. Simpler request structure
        3. Different function names (qikchat vs whatsapp prefixes)
        """
        qik_requests = []
        
        # Handle interactive button messages
        if utils.has_interactive_button_additional_info(byoeb_message):
            qik_interactive_button_message = qik_req_payload.get_qikchat_interactive_button_request_from_byoeb_message(byoeb_message)
            qik_requests.append(qik_interactive_button_message)
            
        # Handle interactive list messages
        elif utils.has_interactive_list_additional_info(byoeb_message):
            # print(f"🔗 Detected interactive list message with additional_info: {byoeb_message.message_context.additional_info}")
            qik_interactive_list_message = qik_req_payload.get_qikchat_interactive_list_request_from_byoeb_message(byoeb_message)
            # print(f"📋 Generated qikchat interactive list request: {qik_interactive_list_message}")
            qik_requests.append(qik_interactive_list_message)
            
        # Handle text messages
        elif utils.has_text(byoeb_message):
            qik_text_message = qik_req_payload.get_qikchat_text_request_from_byoeb_message(byoeb_message)
            qik_requests.append(qik_text_message)
        
        # Handle audio messages
        if utils.has_audio_additional_info(byoeb_message):
            qik_audio_message = qik_req_payload.get_qikchat_audio_request_from_byoeb_message(byoeb_message)
            qik_requests.append(qik_audio_message)
            
        # Handle template messages
        if utils.has_template_additional_info(byoeb_message):
            qik_template_message = qik_req_payload.get_qikchat_template_request_from_byoeb_message(byoeb_message)
            qik_requests.append(qik_template_message)
        
        return qik_requests
    
    async def amark_read(
        self,
        messages: List[ByoebMessageContext]
    ) -> List[Dict[str, Any]]:
        """
        Mark messages as read in Qikchat.
        
        Key Differences from WhatsApp:
        1. Different client interface
        2. Simpler response format (Dict instead of WhatsAppResponse)
        3. Different mark_as_read method parameters
        """
        from byoeb.chat_app.configuration.dependency_setup import channel_client_factory
        client = await channel_client_factory.get(self.__client_type)
        
        tasks = []
        for message in messages:
            if message.message_context.message_id is None:
                continue
            # Check if user exists before accessing phone_number_id
            if message.user is None:
                continue
            # Qikchat may need phone number for mark_as_read
            tasks.append(
                client.mark_as_read(
                    message.message_context.message_id,
                    message.user.phone_number_id
                )
            )
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [result for result in results if not isinstance(result, Exception)]
    
    async def send_requests(
        self,
        requests: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Send message requests via Qikchat.
        
        Key Differences from WhatsApp:
        1. Different client interface (send_message vs send_batch_messages)
        2. Simpler response format
        3. Different message ID extraction
        4. No message type parameter needed
        """
        from byoeb.chat_app.configuration.dependency_setup import channel_client_factory
        client = await channel_client_factory.get(self.__client_type)
        
        tasks = []
        for request in requests:
            # Qikchat uses single send_message method for all types
            tasks.append(client.send_message(request))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Extract successful responses and message IDs
        responses = []
        message_ids = []
        
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Failed to send message: {result}")
                responses.append({"error": str(result)})
                message_ids.append(None)
            else:
                responses.append(result)
                # Extract message ID from Qikchat response
                message_id = result.get("message_id") or result.get("id")
                message_ids.append(message_id)
        
        return responses, message_ids
    
    def create_conv(
        self,
        byoeb_user_message: ByoebMessageContext,
        responses: List[Dict[str, Any]]
    ) -> List[ByoebMessageContext]:
        """
        Create conversation context from bot responses.
        
        Key Differences from WhatsApp:
        1. Different response structure (Dict vs WhatsAppResponse)
        2. Different message ID extraction
        3. Simpler response parsing
        """
        bot_to_user_messages = []
        
        for response in responses:
            if "error" in response:
                continue
                
            # Extract message details from Qikchat response
            message_id = response.get("message_id") or response.get("id")
            if message_id is None:
                message_id = str(uuid.uuid4())  # Generate unique message ID if not provided
            timestamp = response.get("timestamp") or str(datetime.now().timestamp())
            
            # Convert timestamp to integer if it's a string
            if isinstance(timestamp, str):
                try:
                    # Convert string timestamp to integer (remove decimal part)
                    timestamp_int = int(float(timestamp))
                except (ValueError, TypeError):
                    # Fallback to current timestamp if conversion fails
                    timestamp_int = int(datetime.now().timestamp())
            else:
                timestamp_int = int(timestamp)
            
            # Create bot user context
            bot_user = User(
                phone_number_id=byoeb_user_message.user.phone_number_id,
                name="Oncology Bot",  # Bot name
                user_id="bot"
            )
            
            # Create message context for bot response
            bot_message_context = MessageContext(
                message_id=message_id,
                message_source_text=byoeb_user_message.message_context.message_source_text,
                message_type=MessageTypes.REGULAR_TEXT.value,  # Fixed: Use valid MessageType
                timestamp=str(timestamp_int)  # Convert to string for MessageContext
            )
            
            # Create BYOeB message context
            bot_message = ByoebMessageContext(
                channel_type=byoeb_user_message.channel_type,  # Required field
                message_category=byoeb_user_message.message_category,  # Required field  
                user=bot_user,
                message_context=bot_message_context,
                reply_context=ReplyContext(reply_id=byoeb_user_message.message_context.message_id),
                incoming_timestamp=byoeb_user_message.incoming_timestamp,
                outgoing_timestamp=timestamp_int  # Use integer timestamp
            )
            
            bot_to_user_messages.append(bot_message)
        
        return bot_to_user_messages
    
    def create_cross_conv(
        self,
        byoeb_user_message: ByoebMessageContext,
        byoeb_expert_message: ByoebMessageContext,
        user_responses: List[Dict[str, Any]],
        expert_responses: List[Dict[str, Any]]
    ) -> List[ByoebMessageContext]:
        """
        Create cross conversation context from responses.
        
        Key Differences from WhatsApp:
        1. Dict responses instead of WhatsAppResponse objects
        2. Different message ID extraction
        3. Simpler response structure
        """
        user_messages_context = []
        for user_response in user_responses:
            if "error" in user_response:
                continue
                
            # Determine message type based on response content
            message_type = MessageTypes.INTERACTIVE_LIST.value
            if user_response.get("media_message") is not None:
                message_type = MessageTypes.REGULAR_AUDIO.value
                
            # Extract message ID from response
            message_id = user_response.get("message_id") or user_response.get("id")
            if message_id is None:
                message_id = str(uuid.uuid4())  # Generate unique message ID if not provided
            
            message_context = MessageContext(
                message_id=message_id,
                message_type=message_type,
                additional_info=byoeb_user_message.message_context.additional_info
            )
            reply_context = ReplyContext(
                reply_id=byoeb_user_message.reply_context.reply_id if byoeb_user_message.reply_context else None,
            )
            user_message_context = ByoebMessageContext(
                channel_type=byoeb_user_message.channel_type,
                message_context=message_context,
                reply_context=reply_context
            )
            user_messages_context.append(user_message_context)
        
        # Process expert responses and update expert message with returned message ID
        print(f"🔧 CREATE_CROSS_CONV: Processing {len(expert_responses)} expert responses")
        for i, expert_response in enumerate(expert_responses):
            print(f"🔧 CREATE_CROSS_CONV: Expert response {i+1}: {expert_response}")
            
            if "error" in expert_response:
                print(f"❌ CREATE_CROSS_CONV: Expert response {i+1} contains error, skipping")
                continue
                
            # Extract message ID from expert response
            expert_message_id = expert_response.get("message_id") or expert_response.get("id")
            print(f"🔧 CREATE_CROSS_CONV: Top-level message ID: {expert_message_id}")
            
            # If not found at top level, check in data array (Qikchat format)
            if expert_message_id is None and "data" in expert_response:
                data_array = expert_response.get("data", [])
                print(f"🔧 CREATE_CROSS_CONV: Checking data array with {len(data_array)} items")
                if data_array and len(data_array) > 0:
                    first_data_item = data_array[0]
                    expert_message_id = first_data_item.get("id") or first_data_item.get("message_id")
                    print(f"🔧 CREATE_CROSS_CONV: Found message ID in data[0]: {expert_message_id}")
                    
            print(f"🔧 CREATE_CROSS_CONV: Final extracted expert message ID: {expert_message_id}")
            
            if expert_message_id is not None:
                # Store the original UUID for database update
                original_message_id = byoeb_expert_message.message_context.message_id
                print(f"🔧 CREATE_CROSS_CONV: Original expert message ID: {original_message_id}")
                
                # Update the expert message with the actual Qikchat message ID
                byoeb_expert_message.message_context.message_id = expert_message_id
                print(f"🔧 CREATE_CROSS_CONV: Updated expert message ID: {original_message_id} -> {expert_message_id}")
                print(f"🔧 CREATE_CROSS_CONV: Expert message will be stored with Qikchat ID: {expert_message_id}")
            else:
                print(f"⚠️ CREATE_CROSS_CONV: No message ID found in expert response, will keep original UUID")
            
        # Create cross conversation context
        cross_conversation_context = {
            constants.USER: User(
                user_id=byoeb_user_message.user.user_id if byoeb_user_message.user else None,
                user_type=byoeb_user_message.user.user_type if byoeb_user_message.user else None,
                user_language=byoeb_user_message.user.user_language if byoeb_user_message.user else None,
                test_user=byoeb_user_message.user.test_user if byoeb_user_message.user else None,
                phone_number_id=byoeb_user_message.user.phone_number_id if byoeb_user_message.user else None,
            ),
            constants.MESSAGES_CONTEXT: user_messages_context
        }
        
        # Update expert message with cross conversation context
        byoeb_expert_message.cross_conversation_context = cross_conversation_context
        
        # Return both user messages and updated expert message for database storage
        result_messages = user_messages_context + [byoeb_expert_message]
        
        print(f"🔧 CREATE_CROSS_CONV: Returning {len(result_messages)} messages for database storage")
        for i, msg in enumerate(result_messages):
            msg_id = msg.message_context.message_id
            msg_type = msg.message_context.message_type
            msg_text = msg.message_context.message_english_text
            print(f"   Message {i+1}: ID={msg_id}, Type={msg_type}, Text='{(msg_text or '')[:50]}...'")
        
        return result_messages
    
    async def download_media(
        self,
        media_id: str,
        mime_type: str
    ) -> Optional[bytes]:
        """
        Download media from Qikchat.
        
        Key Differences from WhatsApp:
        1. Different client method name and parameters
        2. Simpler error handling
        """
        try:
            from byoeb.chat_app.configuration.dependency_setup import channel_client_factory
            client = await channel_client_factory.get(self.__client_type)
            
            media_data = await client.get_media(media_id)
            return media_data
            
        except Exception as e:
            self.logger.error(f"Failed to download media {media_id}: {str(e)}")
            return None
    
    async def upload_media(
        self,
        media_data: bytes,
        mime_type: str,
        filename: str
    ) -> Optional[str]:
        """
        Upload media to Qikchat.
        
        Key Differences from WhatsApp:
        1. Different upload method and response format
        2. Direct media ID return
        """
        try:
            from byoeb.chat_app.configuration.dependency_setup import channel_client_factory
            client = await channel_client_factory.get(self.__client_type)
            
            upload_response = await client.upload_media(media_data, mime_type, filename)
            return upload_response.get("media_id")
            
        except Exception as e:
            self.logger.error(f"Failed to upload media: {str(e)}")
            return None
