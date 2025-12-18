import uuid
from typing import Dict, Any, List
from byoeb_core.models.byoeb.message_context import ByoebMessageContext
def _split_expert_verification_message(full_text: str, max_length: int = 1000) -> List[str]:
    """
    Split long expert verification messages into multiple parts.
    Strategy: Split between (Patient Info + Question) and (Answer)
    
    Message structure:
    *Patient Info*: ...
    
    *Question:* ...
    *Answer:* ...
    
    Is the answer correct?
    
    Returns:
        List of text chunks. Last chunk includes verification prompt.
    """
    if len(full_text) <= max_length:
        return [full_text]
    
    # Try to find the Answer section
    answer_marker = "*Answer:*"
    if answer_marker not in full_text:
        # Fallback: split at sentence boundaries
        chunks = []
        remaining = full_text
        while len(remaining) > max_length:
            # Find last sentence boundary before max_length
            split_point = max_length
            for delimiter in [". ", "? ", "! ", "\n\n"]:
                pos = remaining[:max_length].rfind(delimiter)
                if pos > max_length // 2:  # Only split if we're past halfway
                    split_point = pos + len(delimiter)
                    break
            
            chunks.append(remaining[:split_point].strip())
            remaining = remaining[split_point:].strip()
        
        if remaining:
            chunks.append(remaining)
        return chunks
    
    # Split at Answer section
    answer_start = full_text.index(answer_marker)
    context_part = full_text[:answer_start].strip()  # Patient Info + Question
    answer_part = full_text[answer_start:].strip()   # Answer + verification prompt
    
    # Ensure verification prompt is in answer_part
    verification_prompt = "\n\nIs the answer correct?"
    if verification_prompt not in answer_part:
        answer_part += verification_prompt
    
    print(f"  🔍 Split at Answer: context={len(context_part)} chars, answer={len(answer_part)} chars")
    
    # If both parts fit, return [context, answer]
    if len(context_part) <= max_length and len(answer_part) <= max_length:
        print(f"  ✅ Both parts fit in {max_length} char limit")
        return [context_part, answer_part]
    
    # If answer is too long, split it further
    chunks = [context_part]
    remaining_answer = answer_part
    
    while len(remaining_answer) > max_length:
        # Find good split point in answer
        split_point = max_length
        for delimiter in [". ", "? ", "! ", "\n\n"]:
            pos = remaining_answer[:max_length].rfind(delimiter)
            if pos > max_length // 2:
                split_point = pos + len(delimiter)
                break
        
        chunks.append(remaining_answer[:split_point].strip())
        remaining_answer = remaining_answer[split_point:].strip()
    
    if remaining_answer:
        chunks.append(remaining_answer)
    
    print(f"  📦 Split into {len(chunks)} chunks: {[len(c) for c in chunks]}")
    return chunks
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
) -> List[Dict[str, Any]]:
    """
    Convert BYOeB interactive button message to Qikchat format.
    If message is too long (>1000 chars), splits into multiple messages.
    
    Returns:
        List of request dicts. Last one has buttons, earlier ones are plain text.
        All but the last are marked with '_is_continuation': True for filtering.
    
    Key Differences from WhatsApp:
    1. Uses 'to_contact' field
    2. Similar interactive message structure to WhatsApp
    3. Buttons have slightly different format
    """
    phone_number = byoeb_message.user.phone_number_id
    additional_info = byoeb_message.message_context.additional_info
    full_text = byoeb_message.message_context.message_source_text
    
    # Check if message needs splitting
    print(f"🔍 Interactive button message length: {len(full_text)} chars")
    text_chunks = _split_expert_verification_message(full_text, max_length=1000)
    print(f"🔍 Split result: {len(text_chunks)} chunks")
    
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
    
    requests = []
    
    # If no splitting needed, return single message
    if len(text_chunks) == 1:
        qikchat_message = {
            "to_contact": phone_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": full_text
                },
                "action": {
                    "buttons": buttons
                }
            }
        }
        
        # Add reply context if available
        if byoeb_message.reply_context is not None:
            qikchat_message["context"] = {
                "message_id": byoeb_message.reply_context.reply_id
            }
        
        return [qikchat_message]
    
    # Multiple chunks: send continuation messages + final button message
    print(f"📏 Message too long ({len(full_text)} chars), splitting into {len(text_chunks)} parts")
    
    # Create continuation messages (plain text, no buttons)
    for i, chunk in enumerate(text_chunks[:-1]):
        continuation_message = {
            "to_contact": phone_number,
            "type": "text",
            "text": {
                "body": chunk
            },
            "_is_continuation": True  # Internal flag for filtering
        }
        requests.append(continuation_message)
        print(f"  📄 Part {i+1}/{len(text_chunks)}: {len(chunk)} chars (continuation)")
        print(f"     Preview: {chunk[:100]}...")
    
    # Create final message with buttons and last chunk
    print(f"  🔘 Part {len(text_chunks)}/{len(text_chunks)}: {len(text_chunks[-1])} chars (final with buttons)")
    print(f"     Preview: {text_chunks[-1][:100]}...")
    final_message = {
        "to_contact": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": text_chunks[-1]
            },
            "action": {
                "buttons": buttons
            }
        }
    }
    
    # Add reply context only to final message
    if byoeb_message.reply_context is not None:
        final_message["context"] = {
            "message_id": byoeb_message.reply_context.reply_id
        }
    
    requests.append(final_message)
    
    return requests

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
    
    # Add reply context if available (same as text messages)
    if byoeb_message.reply_context is not None:
        qikchat_message["context"] = {
            "message_id": byoeb_message.reply_context.reply_id
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
) -> List[Dict[str, Any]]:
    """
    Create Qikchat template message request.
    If message body is too long (>1000 chars), splits into multiple messages.
    
    Returns:
        List of request dicts. Last one is template, earlier ones are plain text.
        All but the last are marked with '_is_continuation': True for filtering.
    
    Template messages are used for notifications and re-engagement.
    """
    phone_number = byoeb_message.user.phone_number_id
    additional_info = byoeb_message.message_context.additional_info
    
    # Default template for oncology bot
    template_name = additional_info.get("template_name", "hello_world")
    template_language = additional_info.get("template_language", "en")
    template_parameters = additional_info.get("template_parameters", [])
    
    # Ensure template_language is a string
    if isinstance(template_language, dict):
        template_language = template_language.get("code", "en")
    elif not isinstance(template_language, str):
        template_language = str(template_language)
    
    # Check if this is an expert verification template that might be too long
    # Reconstruct the full message text from template parameters
    if template_name == "verification_with_butons" and len(template_parameters) >= 3:
        # Template structure: {{1}} = Patient Info, {{2}} = Question, {{3}} = Answer
        patient_info = template_parameters[0]
        question = template_parameters[1]
        answer = template_parameters[2]
        
        full_text = f"*Patient Info*: {patient_info}\n\n*Question:* {question}\n*Answer:* {answer}\n\nIs the answer correct?"
        
        # Check if we need to split
        if len(full_text) > 1000:
            print(f"📏 Template message too long ({len(full_text)} chars), splitting into 2 template messages")
            
            requests = []
            
            # First template message: Patient Info + Question (Answer field placeholder)
            # This ensures the context is sent first
            first_template = {
                "to_contact": phone_number,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": template_language,
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": patient_info},
                                {"type": "text", "text": question},
                                {"type": "text", "text": "<please check other message>"}  # Placeholder for answer
                            ]
                        }
                    ]
                },
                "_is_continuation": True  # Mark as continuation so it's not stored in DB
            }
            requests.append(first_template)
            print(f"  📋 Template 1: Patient Info + Question (Answer=placeholder) - continuation")
            
            # Second template message: Answer only (Patient Info + Question fields placeholder)
            # This is the primary message that gets stored in DB
            second_template = {
                "to_contact": phone_number,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": template_language,
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": "<please check other message>"},  # Placeholder for patient info
                                {"type": "text", "text": "<please check other message>"},  # Placeholder for question
                                {"type": "text", "text": answer}
                            ]
                        }
                    ]
                }
            }
            requests.append(second_template)
            print(f"  📋 Template 2: Answer only (Patient+Question=EMPTY) - primary with buttons")
            
            return requests
    
    # No splitting needed - return standard template message
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
            "language": template_language,
            "components": components
        }
    }
    
    return [qikchat_message]
