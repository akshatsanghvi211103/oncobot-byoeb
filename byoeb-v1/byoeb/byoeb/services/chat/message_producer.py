import logging
import json
import time
from byoeb_core.models.byoeb.message_status import ByoebMessageStatus
from byoeb_core.models.byoeb.message_context import ByoebMessageContext
from byoeb_core.message_queue.base import BaseQueue

class MessageProducerService:
    def __init__(
        self,
        config,
        queue_client: BaseQueue,
    ):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._config = config
        self.__queue_client = queue_client

    def __convert_whatsapp_to_byoeb_message(
        self,
        message
    ) -> ByoebMessageContext:
        import byoeb_integrations.channel.whatsapp.validate_message as wa_validator
        import byoeb_integrations.channel.whatsapp.convert_message as wa_converter
        _, message_type = wa_validator.validate_whatsapp_message(message)
        byoeb_message = wa_converter.convert_whatsapp_to_byoeb_message(message, message_type)
        return byoeb_message
    
    def __convert_qikchat_to_byoeb_message(
        self,
        message
    ) -> ByoebMessageContext:
        import byoeb_integrations.channel.qikchat.validate_message as qikchat_validator
        import byoeb_integrations.channel.qikchat.convert_message as qikchat_converter
        
        # print(f"QIKCHAT CONVERTER: Input message keys: {list(message.keys()) if isinstance(message, dict) else 'Not a dict'}")
        
        # Debug: Log the original webhook payload
        # print(f"DEBUG PRODUCER: Original webhook message: {message}")
        
        # Extract the actual message data from the Qikchat webhook structure
        # Qikchat sends: {"event": "whatsapp:message", "payload": {"message": {...}}}
        if "event" in message and "payload" in message:
            payload = message["payload"]
            # print(f"DEBUG PRODUCER: Payload keys: {list(payload.keys())}")
            # print(f"DEBUG PRODUCER: Full payload: {payload}")
            
            if "message" in payload:
                actual_message = payload["message"]
                # print(f"DEBUG PRODUCER: Extracted message from payload: {actual_message}")
                
                # Add contact info from payload to the message for conversion
                if "id" in payload:
                    actual_message["id"] = payload["id"] 
                
                # Fix: Use contacts field to get the actual sender (your number)
                # The message.from field contains bot number, but contacts.to contains sender number
                if "contacts" in payload:
                    contacts = payload["contacts"]
                    # print(f"DEBUG PRODUCER: Found contacts: {contacts}")
                    if isinstance(contacts, list) and len(contacts) > 0:
                        # The contacts.to field contains the actual sender's number
                        contact = contacts[0]
                        sender_number = contact.get("to")  # This is the actual sender
                        if sender_number:
                            # print(f"DEBUG PRODUCER: Overriding from '{actual_message.get('from')}' with sender '{sender_number}'")
                            actual_message["from"] = sender_number
                        else:
                            print(f"DEBUG PRODUCER: No 'to' field found in contact: {contact}")
                    elif isinstance(contacts, str):
                        actual_message["from"] = contacts
                        # print(f"DEBUG PRODUCER: Set from to: {actual_message['from']}")
                else:
                    # print(f"DEBUG PRODUCER: Using existing 'from' field: {actual_message.get('from')}")
                    print("DEBUG PRODUCER: No contacts field found")
                
                # Add timestamp if available
                if "timestamp" not in actual_message and "timestamp" in payload:
                    actual_message["timestamp"] = payload["timestamp"]
                
                # print(f"DEBUG PRODUCER: Final message before conversion: {actual_message}")
                
                byoeb_message = qikchat_converter.convert_qikchat_message_to_byoeb(actual_message)
                # print(f"QIKCHAT CONVERTER: Conversion result: {byoeb_message}")
                return byoeb_message
        
        # print("QIKCHAT CONVERTER: Could not extract message from webhook payload")
        return None
    
    def is_older_than_n_minutes(
        self,
        n,
        unix_timestamp
    ) -> bool:
        seconds = n*60
        current_time = int(time.time())   
        if current_time - unix_timestamp > seconds:
            return True
        return False
        

    async def apublish_message(
        self,
        message,
        channel
    ):
        # print(f"MESSAGE PRODUCER SERVICE: Publishing message for channel: {channel}")
        byoeb_message: ByoebMessageContext = None
        n = 5
        if channel == "whatsapp":
            # print("MESSAGE PRODUCER SERVICE: Converting WhatsApp message")
            byoeb_message = self.__convert_whatsapp_to_byoeb_message(message)
        elif channel == "qikchat":
            # print("MESSAGE PRODUCER SERVICE: Converting Qikchat message")
            byoeb_message = self.__convert_qikchat_to_byoeb_message(message)
        else:
            print(f"MESSAGE PRODUCER SERVICE: Unsupported channel: {channel}")
            
        # print(f"MESSAGE PRODUCER SERVICE: Conversion result - byoeb_message: {byoeb_message}")
        
        if byoeb_message is None or byoeb_message is False:
            # print("MESSAGE PRODUCER SERVICE: Invalid message - conversion failed")
            return None, "Invalid message"
        
        # Debug: Log the full byoeb_message before sending to queue (commented out to reduce noise)
        # print(f"DEBUG: Full byoeb_message before queue: {byoeb_message}")
        # print(f"DEBUG: byoeb_message user: {byoeb_message.user}")
        # print(f"DEBUG: byoeb_message JSON: {byoeb_message.model_dump_json()}")
        
        try:
            # Skip timestamp check if incoming_timestamp is None (for real-time messages)
            if byoeb_message.incoming_timestamp is not None and self.is_older_than_n_minutes(
                n,
                byoeb_message.incoming_timestamp,
            ):
                return f"Skipped. Older than {n} minutes", None
            result = await self.__queue_client.asend_message(
                byoeb_message.model_dump_json(),
                time_to_live=self._config["message_queue"]["azure"]["time_to_live"])
            self._logger.info(f"Message sent: {result}")
            print(f"Published successfully {result.id}")
            return f"Published successfully {result.id}", None
        except Exception as e:
            return None, e