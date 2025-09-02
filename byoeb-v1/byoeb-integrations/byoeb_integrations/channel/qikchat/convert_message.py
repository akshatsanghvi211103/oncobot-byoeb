import json
import uuid
from typing import Dict, Any, Optional
from byoeb_core.models.byoeb.message_context import (
    ByoebMessageContext,
    MessageContext,
    ReplyContext,
    MediaContext,
    MessageTypes
)
from byoeb_core.models.byoeb.message_status import ByoebMessageStatus
from byoeb_core.models.byoeb.user import User

def convert_qikchat_regular_message(original_message: Dict[str, Any]) -> ByoebMessageContext:
    """
    Convert Qikchat regular message to BYOeB format.
    
    Key Differences from WhatsApp:
    1. Simpler message structure - direct fields instead of nested entry/changes
    2. Different field names (from vs from_, timestamp format)
    3. No complex nested validation models needed
    """
    if isinstance(original_message, str):
        original_message = json.loads(original_message)
    
    # Debug: Log the original message structure (commented out to reduce noise)
    # print(f"=== QIKCHAT CONVERT DEBUG: Original message keys: {list(original_message.keys())} ===")
    # print(f"=== QIKCHAT CONVERT DEBUG: Original message: {original_message} ===")
    
    # Extract basic message info - simpler than WhatsApp
    timestamp = original_message.get("timestamp")
    from_number = original_message.get("from")  # Direct field, not from_
    message_id = original_message.get("id") or str(uuid.uuid4())
    message_type = original_message.get("type")
    
    # print(f"DEBUG CONVERT: Extracted - timestamp: {timestamp}, from_number: {from_number}, message_id: {message_id}, message_type: {message_type}")
    
    byoeb_message_type = None
    message_text = None
    message_audio = None
    message_mime = None
    reply_to_message_id = None
    
    # Handle different message types
    if message_type == "text":
        text_data = original_message.get("text", {})
        if isinstance(text_data, dict):
            message_text = text_data.get("body", "")
        else:
            message_text = str(text_data)
        byoeb_message_type = MessageTypes.REGULAR_TEXT.value
        
    elif message_type == "audio":
        audio_data = original_message.get("audio", {})
        # For Qikchat, prefer URL over ID since API download endpoints don't exist
        message_audio = audio_data.get("url") or audio_data.get("id")
        message_mime = audio_data.get("mime_type", "audio/wav")
        byoeb_message_type = MessageTypes.REGULAR_AUDIO.value
        # print(f"=== AUDIO CONVERSION DEBUG ===")
        # print(f"Audio data: {audio_data}")
        # print(f"Message audio (url or id): {message_audio}")
        # print(f"Message mime: {message_mime}")
        # print(f"=== END AUDIO DEBUG ===")
        
    elif message_type == "image":
        image_data = original_message.get("image", {})
        message_audio = image_data.get("url") or image_data.get("id")
        message_mime = image_data.get("mime_type", "image/jpeg")
        byoeb_message_type = MessageTypes.REGULAR_IMAGE.value
        
    elif message_type == "document":
        doc_data = original_message.get("document", {})
        message_audio = doc_data.get("url") or doc_data.get("id")
        message_mime = doc_data.get("mime_type", "application/pdf")
        byoeb_message_type = MessageTypes.REGULAR_DOCUMENT.value
    
    # Handle reply context - simpler structure
    if "context" in original_message:
        reply_to_message_id = original_message["context"].get("message_id")
    
    # Create media context if needed
    message_info = None
    if message_audio is not None:
        message_info = MediaContext(
            media_id=message_audio,
            mime_type=message_mime
        )
        # print(f"=== MEDIA CONTEXT CREATED ===")
        # print(f"MediaContext: media_id={message_audio}, mime_type={message_mime}")
        # print(f"=== END MEDIA CONTEXT DEBUG ===")
    else:
        print(f"=== NO MEDIA CONTEXT CREATED - message_audio is None ===")
    
    # Create reply context if available
    reply_context = None
    if reply_to_message_id is not None:
        reply_context = ReplyContext(
            reply_id=reply_to_message_id
        )
    
    # Create user object
    user = User(
        phone_number_id=from_number,
        name="",  # Qikchat doesn't provide name in message
        user_id=from_number
    )
    
    # Create message context
    message_context = MessageContext(
        message_id=message_id,
        message_source_text=message_text or "",
        message_type=byoeb_message_type,
        media_info=message_info,
        timestamp=timestamp
    )
    
    # Create final BYOeB message context
    byoeb_message = ByoebMessageContext(
        channel_type="qikchat",
        user=user,
        message_context=message_context,
        reply_context=reply_context
    )
    
    return byoeb_message

def convert_qikchat_interactive_message(original_message: Dict[str, Any]) -> ByoebMessageContext:
    """
    Convert Qikchat interactive message (button/list response) to BYOeB format.
    
    Key Differences from WhatsApp:
    1. Different interactive response structure
    2. Simpler button/list reply format
    3. No template message conversion needed
    """
    if isinstance(original_message, str):
        original_message = json.loads(original_message)
    
    # Handle qikchat event structure - extract payload if present
    message_data = original_message
    if "payload" in original_message and "event" in original_message:
        payload = original_message.get("payload", {})
        if "message" in payload:
            message_data = payload["message"]
        # Also get contact info from payload
        contact_info = payload.get("contact", {})
        timestamp = original_message.get("timestamp")
        from_number = contact_info.get("wa_id") or contact_info.get("phone_number")
        message_id = message_data.get("id") or str(uuid.uuid4())
    else:
        # Fallback to original structure
        timestamp = original_message.get("timestamp")
        from_number = original_message.get("from")
        message_id = original_message.get("id") or str(uuid.uuid4())
    
    interactive_data = message_data.get("interactive", {})
    interactive_type = interactive_data.get("type")
    
    message_text = ""
    byoeb_message_type = None
    additional_info = {}
    
    if interactive_type == "button_reply":
        button_reply = interactive_data.get("button_reply", {})
        message_text = button_reply.get("title", "")
        button_id = button_reply.get("id", "")
        byoeb_message_type = MessageTypes.INTERACTIVE_BUTTON.value
        additional_info = {
            "button_id": button_id,
            "button_title": message_text
        }
        
    elif interactive_type == "list_reply":
        list_reply = interactive_data.get("list_reply", {})
        message_title = list_reply.get("title", "")
        message_description = list_reply.get("description", "")
        list_id = list_reply.get("id", "")
        
        # Use description if available (full text), otherwise fall back to title
        message_text = message_description if message_description else message_title
        
        byoeb_message_type = MessageTypes.INTERACTIVE_LIST.value
        additional_info = {
            "list_id": list_id,
            "list_title": message_title,
            "list_description": message_description
        }
    
    # Create user and message contexts
    user = User(
        phone_number_id=from_number,
        name="",
        user_id=from_number
    )
    
    message_context = MessageContext(
        message_id=message_id,
        message_source_text=message_text,
        message_type=byoeb_message_type,
        additional_info=additional_info,
        timestamp=timestamp
    )
    
    byoeb_message = ByoebMessageContext(
        channel_type="qikchat",
        user=user,
        message_context=message_context
    )
    
    return byoeb_message

def convert_qikchat_status_message(original_message: Dict[str, Any]) -> ByoebMessageStatus:
    """
    Convert Qikchat status/delivery receipt to BYOeB format.
    
    Key Differences from WhatsApp:
    1. Simpler status structure
    2. Different status field names
    3. Direct status mapping
    """
    if isinstance(original_message, str):
        original_message = json.loads(original_message)
    
    message_id = original_message.get("message_id")
    from_number = original_message.get("from")
    status = original_message.get("status")
    timestamp = original_message.get("timestamp")
    
    # Map Qikchat status to BYOeB status
    status_mapping = {
        "sent": "sent",
        "delivered": "delivered", 
        "read": "read",
        "failed": "failed"
    }
    
    byoeb_status = status_mapping.get(status, "unknown")
    
    return ByoebMessageStatus(
        message_id=message_id,
        phone_number_id=from_number,
        status=byoeb_status,
        timestamp=timestamp
    )

def convert_qikchat_message_to_byoeb(original_message: Dict[str, Any]) -> Optional[ByoebMessageContext]:
    """
    Main conversion function that determines message type and converts accordingly.
    
    Key Differences from WhatsApp:
    1. Single function handles all message types (simpler than WhatsApp's multiple functions)
    2. Direct type detection from message structure
    3. No complex validation model parsing needed
    """
    try:
        message_type = original_message.get("type")
        
        if message_type in ["text", "audio", "image", "document"]:
            return convert_qikchat_regular_message(original_message)
            
        elif message_type == "interactive":
            try:
                result = convert_qikchat_interactive_message(original_message)
                return result
            except Exception as e:
                print(f"❌ Error in convert_qikchat_interactive_message: {e}")
                import traceback
                traceback.print_exc()
                return None
            
        elif message_type == "status":
            # Status messages don't convert to ByoebMessageContext
            return None
            
        else:
            print(f"Unsupported Qikchat message type: {message_type}")
            return None
            
    except Exception as e:
        print(f"Error converting Qikchat message: {str(e)}")
        return None
