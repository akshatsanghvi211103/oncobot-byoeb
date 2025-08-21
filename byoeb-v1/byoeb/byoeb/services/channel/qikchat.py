import asyncio
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
            qik_interactive_list_message = qik_req_payload.get_qikchat_interactive_list_request_from_byoeb_message(byoeb_message)
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
            timestamp = response.get("timestamp") or str(datetime.now().timestamp())
            
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
                message_type=MessageTypes.BOT_RESPONSE.value,
                timestamp=timestamp
            )
            
            # Create BYOeB message context
            bot_message = ByoebMessageContext(
                user=bot_user,
                message_context=bot_message_context,
                reply_context=ReplyContext(reply_id=byoeb_user_message.message_context.message_id)
            )
            
            bot_to_user_messages.append(bot_message)
        
        return bot_to_user_messages
    
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
