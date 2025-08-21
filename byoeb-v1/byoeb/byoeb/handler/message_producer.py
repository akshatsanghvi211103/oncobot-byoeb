import logging
import byoeb_integrations.channel.whatsapp.validate_message as wa_validator
import byoeb_integrations.channel.qikchat.validate_message as qikchat_validator
from typing import Any
from byoeb.factory import QueueProducerFactory
from byoeb.services.chat.message_producer import MessageProducerService
from byoeb_core.models.byoeb.response import ByoebResponseModel, ByoebStatusCodes

class QueueProducerHandler:
    def __init__(
        self,
        config,
        queue_producer_factory: QueueProducerFactory
    ):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._config = config
        self._queue_provider = config["app"]["queue_provider"]
        self.queue_producer_factory = queue_producer_factory

    async def __get_or_create_message_producer(
        self,
        message_type
    ) -> MessageProducerService:
        queue_client = await self.queue_producer_factory.get(self._queue_provider, message_type)
        return MessageProducerService(self._config, queue_client)

    async def __validate_channel_and_get_message_type(
        self,
        message
    ) -> Any:
        # For debugging: log the message structure
        self._logger.info(f"Validating message with keys: {list(message.keys()) if isinstance(message, dict) else 'Not a dict'}")
        
        # Try Qikchat validation first (since this is likely from /webhook/whk)
        is_qikchat, message_type = qikchat_validator.validate_qikchat_message(message)
        if is_qikchat:
            return "qikchat", message_type
        
        # Try WhatsApp validation second
        is_whatsapp, message_type = wa_validator.validate_whatsapp_message(message)
        if is_whatsapp:
            return "whatsapp", message_type
            
        return False, None
            
        
    async def handle(
        self,
        message
    ):
        # print(f"MESSAGE PRODUCER: Starting handle for message with keys: {list(message.keys()) if isinstance(message, dict) else 'Not a dict'}")
        
        channel, message_type = await self.__validate_channel_and_get_message_type(message)
        # print(f"MESSAGE PRODUCER: Validation result - channel: {channel}, message_type: {message_type}")
        
        if message_type == "status":
            # print("MESSAGE PRODUCER: Returning status update")
            return ByoebResponseModel(
                status_code=ByoebStatusCodes.OK,
                message="status update"
            )
        if not channel:
            # print("MESSAGE PRODUCER: Invalid channel - returning BAD_REQUEST")
            return ByoebResponseModel(
                status_code=ByoebStatusCodes.BAD_REQUEST,
                message="Invalid channel"
            )
        
        # print(f"MESSAGE PRODUCER: Valid channel '{channel}', message_type '{message_type}' - proceeding to create producer")
        message_producer_service = None
        try:
            message_producer_service = await self.__get_or_create_message_producer(message_type)
            # print("MESSAGE PRODUCER: Producer service created successfully")
        except Exception as e:
            # print(f"MESSAGE PRODUCER: Error creating producer: {str(e)}")
            return ByoebResponseModel(
                status_code=ByoebStatusCodes.INTERNAL_SERVER_ERROR,
                message= f"Invalid producer type: {str(e)}"
            )
        
        # print("MESSAGE PRODUCER: Publishing message...")
        response, err = await message_producer_service.apublish_message(message, channel)
        if err is not None:
            # print(f"MESSAGE PRODUCER: Publish error: {err}")
            return ByoebResponseModel(
                status_code=ByoebStatusCodes.INTERNAL_SERVER_ERROR,
                message=err
            )
        # print(f"MESSAGE PRODUCER: Publish successful: {response}")
        return ByoebResponseModel(
            status_code=ByoebStatusCodes.OK,
            message=response
        )
        