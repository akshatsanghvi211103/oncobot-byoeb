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

async def get_qikchat_audio_request_from_byoeb_message(
    byoeb_message: ByoebMessageContext
) -> Dict[str, Any]:
    """
    Convert BYOeB message to Qikchat audio message format.
    
    Key Differences from WhatsApp:
    1. Uses 'to_contact' field
    2. Different audio structure - supports both URLs and IDs
    3. Uploads audio data first if needed to get a URL/ID
    """
    phone_number = byoeb_message.user.phone_number_id
    additional_info = byoeb_message.message_context.additional_info
    
    # Check if we have an audio URL (for SAS-enabled audio)
    if "audio_url" in additional_info:
        audio_url = additional_info["audio_url"]
        print(f"🎵 Using audio URL: {audio_url[:50]}..." if audio_url else "🎵 Empty audio URL")
        qikchat_message = {
            "to_contact": phone_number,
            "type": "audio",
            "audio": {
                "link": audio_url  # Use SAS URL for direct access
            }
        }
    elif "data" in additional_info:
        # For TTS-generated audio data, we need to upload it first
        audio_data = additional_info["data"]
        mime_type = additional_info.get("mime_type", "audio/wav")
        
        # Import the client to upload media
        from byoeb.chat_app.configuration.dependency_setup import channel_client_factory
        
        try:
            client = await channel_client_factory.get("qikchat")
            
            # Upload the audio data
            upload_response = await client.upload_media(
                media_data=audio_data,
                mime_type=mime_type,
                filename="audio_message.wav"
            )
            
            # Extract media ID or URL from upload response
            media_id = upload_response.get("media_id") or upload_response.get("id")
            media_url = upload_response.get("url") or upload_response.get("link")
            
            if media_url:
                # Use URL if available
                qikchat_message = {
                    "to_contact": phone_number,
                    "type": "audio",
                    "audio": {
                        "link": media_url
                    }
                }
            elif media_id:
                # Use media ID if URL not available
                qikchat_message = {
                    "to_contact": phone_number,
                    "type": "audio",
                    "audio": {
                        "id": media_id
                    }
                }
            else:
                # Upload failed - return None to skip audio message
                print(f"⚠️ Media upload failed: No media_id or media_url in response")
                return None
                
        except Exception as e:
            print(f"❌ Error uploading audio media: {e}")
            # Upload failed - return None to skip audio message
            print(f"⚠️ Skipping audio message due to upload failure")
            return None
    else:
        # No audio data available - shouldn't happen
        raise ValueError("No audio data or URL provided for audio message")
    
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
    if "row_texts" in additional_info and additional_info["row_texts"] is not None:
        row_texts = additional_info["row_texts"]
        rows = []
        for i, row_text in enumerate(row_texts):
            rows.append({
                "id": f"option_{i}",
                "title": f"Q{i+1}",  # Short title like "Q1", "Q2", etc. (max 20 chars)
                "description": row_text if len(row_text) <= 72 else row_text[:69] + "..."  # Full question in description
            })
        
        sections.append({
            "title": "",  # Remove section title to eliminate header
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
    
    # Get description for button text - truncate to 20 chars max
    button_text = additional_info.get("description", "Select an option")
    if len(button_text) > 20:
        button_text = button_text[:17] + "..."  # Truncate and add ellipsis
    
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
    template_parameters = additional_info.get("template_parameters", [])
    
    # Debug output
    # print(f"🔧 Template language type: {type(template_language)}, value: {template_language}")
    # print(f"🔧 Template parameters: {template_parameters}")
    # print(f"🔧 Additional info: {additional_info}")
    
    # Ensure template_language is a string
    if isinstance(template_language, dict):
        template_language = template_language.get("code", "en")
    elif not isinstance(template_language, str):
        template_language = str(template_language)
    
    # Build components array for template parameters
    components = []
    if template_parameters and len(template_parameters) > 0:
        # Create body component with parameters
        parameters = []
        for param in template_parameters:
            parameters.append({
                "type": "text",
                "text": param
            })
        
        components.append({
            "type": "body",
            "parameters": parameters
        })
    
    qikchat_message = {
        "to_contact": phone_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": template_language,  # QikChat expects a string, not an object
            "components": components  # Include parameters in components
        }
    }
    
    # print(f"🔧 Final template language in payload: {qikchat_message['template']['language']}")
    # print(f"🔧 Final template components: {qikchat_message['template']['components']}")
    return qikchat_message
