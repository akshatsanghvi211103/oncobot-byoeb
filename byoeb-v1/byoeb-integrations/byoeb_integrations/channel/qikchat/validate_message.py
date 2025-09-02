import json
import logging
from typing import Dict, Any, Union

logger = logging.getLogger(__name__)

def validate_qikchat_regular_message(original_message: Union[str, Dict[str, Any]]) -> bool:
    """
    Validate regular Qikchat message (text, audio, etc.).
    
    Key Differences from WhatsApp:
    1. Qikchat wraps messages in an 'event' structure
    2. Actual message data is nested inside
    3. Different field names and structure
    """
    # logger.info(f"Qikchat validator: Checking message: {original_message}")
    
    if isinstance(original_message, str):
        try:
            original_message = json.loads(original_message)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Qikchat message JSON: {str(e)}")
            return False
    
    try:
        # logger.info(f"Qikchat validator: Message type: {type(original_message)}")
        # logger.info(f"Qikchat validator: Message keys: {list(original_message.keys()) if isinstance(original_message, dict) else 'Not a dict'}")
        
        # Safety check for None or empty message
        if not original_message or not isinstance(original_message, dict):
            logger.warning(f"Qikchat validator: Invalid message format - not a dict or empty: {original_message}")
            return False
        
        # Check if this is a Qikchat webhook with event structure
        if "event" in original_message:
            # logger.info(f"Qikchat validator: Found 'event' field with value: {original_message['event']}")
            # Extract the actual message from the event wrapper
            if "payload" in original_message:
                payload = original_message["payload"]
                # logger.info(f"Qikchat validator: Using 'payload' field: {payload}")
                
                # Safety check for payload
                if not payload or not isinstance(payload, dict):
                    logger.warning(f"Qikchat validator: Invalid payload format: {payload}")
                    return False
                
                # Check if this is a status message (delivery/read status)
                # Status messages have 'status' field but no 'message' field
                if "status" in payload and "message" not in payload:
                    logger.info(f"Qikchat validator: Status message detected, ignoring")
                    return False
                
                # The actual message data is in payload.message
                if "message" in payload:
                    message_data = payload["message"]
                    # logger.info(f"Qikchat validator: Found message data in payload.message: {message_data}")
                else:
                    message_data = payload
                    # logger.info(f"Qikchat validator: Using payload directly: {message_data}")
            elif "data" in original_message:
                message_data = original_message["data"]
                # logger.info(f"Qikchat validator: Using 'data' field: {message_data}")
            else:
                # Sometimes the message might be directly in the event
                message_data = original_message
                # Look for nested message structure
                for key, value in original_message.items():
                    if isinstance(value, dict) and "type" in value:
                        message_data = value
                        # logger.info(f"Qikchat validator: Found nested message in '{key}': {message_data}")
                        break
        else:
            # logger.info("Qikchat validator: No 'event' field found, using original message")
            message_data = original_message
        
        # Safety check for message_data
        if not message_data or not isinstance(message_data, dict):
            logger.warning(f"Qikchat validator: Invalid message_data format: {message_data}")
            return False
            
        # logger.info(f"Qikchat validator: Final message_data: {message_data}")
        
        # Validate required Qikchat message fields
        required_fields = ["type"]  # Start with just type, others might be optional
        
        for field in required_fields:
            if field not in message_data:
                logger.error(f"Missing required field in Qikchat message: {field}")
                logger.error(f"Available fields: {list(message_data.keys()) if isinstance(message_data, dict) else 'Not a dict'}")
                return False
        
        message_type = message_data.get("type")
        
        # Validate supported message types
        if message_type == "text":
            if "text" not in message_data:
                logger.error("Text message missing 'text' field")
                return False
            return True
            
        elif message_type == "audio":
            if "audio" not in message_data:
                logger.error("Audio message missing 'audio' field")
                return False
            return True
            
        elif message_type == "image":
            if "image" not in message_data:
                logger.error("Image message missing 'image' field")
                return False
            return True
            
        elif message_type == "document":
            if "document" not in message_data:
                logger.error("Document message missing 'document' field")
                return False
            return True
            
        else:
            logger.warning(f"Unsupported Qikchat message type: {message_type}")
            return False
            
    except Exception as e:
        logger.error(f"Qikchat regular message validation error: {str(e)}")
        return False

def validate_qikchat_interactive_message(original_message: Union[str, Dict[str, Any]]) -> bool:
    """
    Validate Qikchat interactive message (buttons, lists).
    
    Key Differences from WhatsApp:
    1. Different interactive message structure
    2. Simpler button/list response format
    3. No template message concept like WhatsApp
    """
    if isinstance(original_message, str):
        try:
            original_message = json.loads(original_message)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Qikchat interactive message JSON: {str(e)}")
            return False
    
    try:
        # Handle qikchat event structure - extract payload if present
        message_data = original_message
        if "payload" in original_message and "event" in original_message:
            payload = original_message.get("payload", {})
            if "message" in payload:
                message_data = payload["message"]
        
        # Check if it's an interactive response
        message_type = message_data.get("type")
        
        if message_type != "interactive":
            return False
            
        interactive_data = message_data.get("interactive")
        if not interactive_data:
            logger.error("Interactive message missing 'interactive' field")
            return False
        
        interactive_type = interactive_data.get("type")
        
        if interactive_type == "button_reply":
            # Button response validation
            if "button_reply" not in interactive_data:
                logger.error("Button reply missing 'button_reply' field")
                return False
            return True
            
        elif interactive_type == "list_reply":
            # List response validation
            if "list_reply" not in interactive_data:
                logger.error("List reply missing 'list_reply' field")
                return False
            return True
            
        else:
            logger.warning(f"Unsupported interactive type: {interactive_type}")
            return False
            
    except Exception as e:
        logger.error(f"Qikchat interactive message validation error: {str(e)}")
        return False

def validate_qikchat_status_message(original_message: Union[str, Dict[str, Any]]) -> bool:
    """
    Validate Qikchat status/delivery receipt message.
    
    Key Differences from WhatsApp:
    1. Simpler status structure
    2. Different status field names
    """
    if isinstance(original_message, str):
        try:
            original_message = json.loads(original_message)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Qikchat status message JSON: {str(e)}")
            return False
    
    try:
        if original_message.get("type") != "status":
            return False
        
        # Validate required status fields
        if "status" not in original_message:
            logger.error("Status message missing 'status' field")
            return False
            
        if "message_id" not in original_message:
            logger.error("Status message missing 'message_id' field")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Qikchat status message validation error: {str(e)}")
        return False

def is_valid_qikchat_message(original_message: Union[str, Dict[str, Any]]) -> bool:
    """
    Main validation function for any Qikchat message.
    
    Returns True if the message is valid, False otherwise.
    """
    # Try each validation type
    if validate_qikchat_regular_message(original_message):
        return True
    
    if validate_qikchat_interactive_message(original_message):
        return True
        
    if validate_qikchat_status_message(original_message):
        return True
    
    logger.warning("Message failed all Qikchat validation checks")
    return False

def validate_qikchat_message(original_message: Union[str, Dict[str, Any]]):
    """
    Main validation function matching WhatsApp validator interface.
    
    Returns tuple: (is_valid, message_type)
    """
    # Early check for status messages to avoid validation errors
    if isinstance(original_message, dict):
        if "event" in original_message:
            event_type = original_message["event"]
            
            # Check for status events first - RETURN TRUE to acknowledge them
            if event_type == "whatsapp:message:status":
                logger.info(f"Qikchat validator: Status event acknowledged: {event_type}")
                return True, "status"  # Acknowledge status messages but don't process them
            
            # Check for regular message events
            if event_type == "whatsapp:message:in" and "payload" in original_message:
                payload = original_message["payload"]
                # Additional check: status messages might also have 'status' field but no 'message' field
                if isinstance(payload, dict) and "status" in payload and "message" not in payload:
                    logger.info(f"Qikchat validator: Status payload acknowledged")
                    return True, "status"  # Acknowledge status messages but don't process them
    
    if validate_qikchat_regular_message(original_message):
        return True, "regular"
    
    if validate_qikchat_interactive_message(original_message):
        return True, "interactive"
        
    if validate_qikchat_status_message(original_message):
        return True, "status"
    
    return False, None
