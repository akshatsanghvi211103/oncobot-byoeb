import uuid
from typing import Dict, Any
from byoeb_core.models.byoeb.message_context import ByoebMessageContext

def get_qikchat_text_request_from_byoeb_message(
    byoeb_message: ByoebMessageContext
) -> Dict[str, Any]:
    """
    Convert BYOeB message to Qikchat text message format.
    
    Key Differences from WhatsApp:
    1. Uses 'to_contact' field instead of 'to'
    2. Text is nested under 'text.body' structure
    3. No 'messaging_product' field required
    4. Uses 'from' field for sender identification
    """
    message_text = byoeb_message.message_context.message_source_text
    phone_number = byoeb_message.user.phone_number_id
    
    # Qikchat message structure (based on successful API test)
    qikchat_message = {
        "to_contact": phone_number,  # Correct field name for Qikchat
        "type": "text",              # Message type
        "text": {
            "body": message_text     # Nested text structure
        }
    }
    
    # Add reply context if available
    if byoeb_message.reply_context is not None:
        qikchat_message["context"] = {
            "message_id": byoeb_message.reply_context.reply_id
        }
    
    return qikchat_message

def get_qikchat_audio_request_from_byoeb_message(
    byoeb_message: ByoebMessageContext
) -> Dict[str, Any]:
    """
    Convert BYOeB message to Qikchat audio message format.
    
    Key Differences from WhatsApp:
    1. Uses 'to_contact' field
    2. Different audio structure
    3. May need media upload first
    """
    audio_data = byoeb_message.message_context.additional_info["data"]
    phone_number = byoeb_message.user.phone_number_id
    
    qikchat_message = {
        "to_contact": phone_number,
        "type": "audio",
        "audio": {
            "id": audio_data,  # Assumes audio_data is a media ID
            "mime_type": "audio/wav"
        }
    }
    
    # Add reply context if available
    if byoeb_message.reply_context is not None:
        qikchat_message["context"] = {
            "message_id": byoeb_message.reply_context.reply_id
        }
    
    return qikchat_message

def get_qikchat_interactive_button_request_from_byoeb_message(
    byoeb_message: ByoebMessageContext
) -> Dict[str, Any]:
    """
    Convert BYOeB interactive button message to Qikchat format.
    
    Key Differences from WhatsApp:
    1. Uses 'to_contact' field
    2. Similar interactive message structure to WhatsApp
    3. Buttons have slightly different format
    """
    phone_number = byoeb_message.user.phone_number_id
    additional_info = byoeb_message.message_context.additional_info
    
    buttons = []
    if "buttons" in additional_info:
        for button in additional_info["buttons"]:
            buttons.append({
                "type": "reply",
                "reply": {
                    "id": button.get("id", str(uuid.uuid4())),
                    "title": button.get("title", "Button")
                }
            })
    
    qikchat_message = {
        "to_contact": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": byoeb_message.message_context.message_source_text
            },
            "action": {
                "buttons": buttons
            }
        }
    }
    
    return qikchat_message

def get_qikchat_interactive_list_request_from_byoeb_message(
    byoeb_message: ByoebMessageContext
) -> Dict[str, Any]:
    """
    Convert BYOeB interactive list message to Qikchat format.
    """
    phone_number = byoeb_message.user.phone_number_id
    additional_info = byoeb_message.message_context.additional_info
    
    sections = []
    if "sections" in additional_info:
        for section in additional_info["sections"]:
            rows = []
            for row in section.get("rows", []):
                rows.append({
                    "id": row.get("id", str(uuid.uuid4())),
                    "title": row.get("title", "Option"),
                    "description": row.get("description", "")
                })
            
            sections.append({
                "title": section.get("title", "Options"),
                "rows": rows
            })
    
    qikchat_message = {
        "to_contact": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {
                "text": byoeb_message.message_context.message_source_text
            },
            "action": {
                "button": "Select an option",
                "sections": sections
            }
        }
    }
    
    return qikchat_message

def get_qikchat_reaction_request(
    phone_number: str,
    message_id: str,
    reaction: str
) -> Dict[str, Any]:
    """
    Create Qikchat reaction request.
    
    Key Differences from WhatsApp:
    1. Uses 'to_contact' field
    2. Simpler reaction structure
    """
    return {
        "to_contact": phone_number,
        "type": "reaction",
        "reaction": {
            "message_id": message_id,
            "emoji": reaction
        }
    }

def get_qikchat_template_request_from_byoeb_message(
    byoeb_message: ByoebMessageContext
) -> Dict[str, Any]:
    """
    Create Qikchat template message request.
    
    Template messages are used for notifications and re-engagement.
    """
    phone_number = byoeb_message.user.phone_number_id
    additional_info = byoeb_message.message_context.additional_info
    
    # Default template for oncology bot
    template_name = additional_info.get("template_name", "hello_world")
    template_language = additional_info.get("template_language", "en")
    
    qikchat_message = {
        "to_contact": phone_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": template_language
            },
            "components": []  # Empty components for basic templates
        }
    }
    
    return qikchat_message
