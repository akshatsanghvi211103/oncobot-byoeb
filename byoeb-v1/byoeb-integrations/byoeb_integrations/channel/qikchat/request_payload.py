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
    2. Different audio structure - supports both URLs and IDs
    3. May need media upload first
    """
    phone_number = byoeb_message.user.phone_number_id
    additional_info = byoeb_message.message_context.additional_info
    
    # Check if we have an audio URL (for TTS-generated audio)
    if "audio_url" in additional_info:
        audio_url = additional_info["audio_url"]
        qikchat_message = {
            "to_contact": phone_number,
            "type": "audio",
            "audio": {
                "link": audio_url  # Use link for direct URL
            }
        }
    else:
        # Fallback to original implementation for uploaded audio
        audio_data = additional_info["data"]
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
    elif "button_titles" in additional_info:
        # Handle button_titles format (used by expert verification messages)
        for title in additional_info["button_titles"]:
            buttons.append({
                "type": "reply",
                "reply": {
                    "id": str(uuid.uuid4()),
                    "title": title
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
    # Look for row_texts (like WhatsApp implementation) instead of sections
    if "row_texts" in additional_info:
        row_texts = additional_info["row_texts"]
        rows = []
        for i, row_text in enumerate(row_texts):
            rows.append({
                "id": f"option_{i}",
                "title": row_text[:24],  # Limit title length for Qikchat
                "description": row_text if len(row_text) <= 72 else row_text[:69] + "..."  # Limit description
            })
        
        sections.append({
            "title": "Options",
            "rows": rows
        })
    elif "sections" in additional_info:
        # Fallback to original sections format
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
    
    # Get description for button text
    button_text = additional_info.get("description", "Select an option")
    
    qikchat_message = {
        "to_contact": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {
                "text": byoeb_message.message_context.message_source_text
            },
            "action": {
                "button": button_text,
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
    
    # Debug output
    print(f"🔧 Template language type: {type(template_language)}, value: {template_language}")
    print(f"🔧 Additional info: {additional_info}")
    
    # Ensure template_language is a string
    if isinstance(template_language, dict):
        template_language = template_language.get("code", "en")
    elif not isinstance(template_language, str):
        template_language = str(template_language)
    
    qikchat_message = {
        "to_contact": phone_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": template_language,  # QikChat expects a string, not an object
            "components": []  # Empty components for basic templates
        }
    }
    
    print(f"🔧 Final template language in payload: {qikchat_message['template']['language']}")
    return qikchat_message
