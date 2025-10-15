import byoeb.services.chat.constants as constants
from typing import List
from byoeb.models.message_category import MessageCategory
from byoeb_core.models.byoeb.message_context import ByoebMessageContext
from byoeb.chat_app.configuration.config import bot_config

def has_audio_additional_info(
    byoeb_message: ByoebMessageContext
):
    # Check for traditional audio data format
    has_traditional_audio = (
        byoeb_message.message_context.additional_info is not None and
        constants.DATA in byoeb_message.message_context.additional_info and
        constants.MIME_TYPE in byoeb_message.message_context.additional_info and
        "audio" in byoeb_message.message_context.additional_info.get(constants.MIME_TYPE)
    )
    
    # Check for TTS-generated audio URL format
    has_tts_audio = (
        byoeb_message.message_context.additional_info is not None and
        "audio_url" in byoeb_message.message_context.additional_info
    )
    
    return has_traditional_audio or has_tts_audio

def has_interactive_list_additional_info(
    byoeb_message: ByoebMessageContext
):
    has_list = (
        byoeb_message.message_context.additional_info is not None and
        constants.DESCRIPTION in byoeb_message.message_context.additional_info and
        constants.ROW_TEXTS in byoeb_message.message_context.additional_info and
        byoeb_message.message_context.additional_info[constants.ROW_TEXTS] is not None
    )
    if byoeb_message.message_context.additional_info:
        description_exists = 'description' in byoeb_message.message_context.additional_info
        row_texts_exists = 'row_texts' in byoeb_message.message_context.additional_info
        row_texts_not_none = (row_texts_exists and 
                             byoeb_message.message_context.additional_info['row_texts'] is not None)
        print(f"Checking interactive list - has description: {description_exists}, has row_texts: {row_texts_exists}, row_texts not None: {row_texts_not_none}, result: {has_list}")
    return has_list

def has_interactive_button_additional_info(
    byoeb_message: ByoebMessageContext
):
    return (
        byoeb_message.message_context.additional_info is not None and
        "button_titles" in byoeb_message.message_context.additional_info
    )

def has_template_additional_info(
    byoeb_message: ByoebMessageContext
):
    return (    
        byoeb_message.message_context.additional_info is not None and
        constants.TEMPLATE_NAME in byoeb_message.message_context.additional_info and
        constants.TEMPLATE_LANGUAGE in byoeb_message.message_context.additional_info and
        constants.TEMPLATE_PARAMETERS in byoeb_message.message_context.additional_info
    )

def has_text(
    byoeb_message: ByoebMessageContext
):
    return (
        byoeb_message.message_context.message_source_text is not None
    )

def get_last_active_duration_seconds(timestamp):
    from datetime import datetime
    
    # Handle both string and integer timestamps
    if isinstance(timestamp, str):
        timestamp_int = int(timestamp)
    elif isinstance(timestamp, int):
        timestamp_int = timestamp
    else:
        raise ValueError(f"Timestamp must be string or int, got {type(timestamp)}")
    
    # Convert Unix timestamp to a datetime object  
    last_active_time = datetime.fromtimestamp(timestamp_int)
    
    # Calculate the duration since last active
    return (datetime.now() - last_active_time).total_seconds()

def get_expert_byoeb_messages(byoeb_messages: List[ByoebMessageContext]):
    from byoeb.models.message_category import MessageCategory
    expert_user_types = bot_config["expert"]
    expert_messages = [
        byoeb_message for byoeb_message in byoeb_messages
        if (byoeb_message.user is not None and byoeb_message.user.user_type in expert_user_types.values()) 
           or byoeb_message.message_category == MessageCategory.BOT_TO_EXPERT_VERIFICATION.value
    ]
    return expert_messages

def get_user_byoeb_messages(byoeb_messages: List[ByoebMessageContext]):
    regular_user_type = bot_config["regular"]["user_type"]
    user_messages = [
        byoeb_message for byoeb_message in byoeb_messages 
        if byoeb_message.user is not None and byoeb_message.user.user_type == regular_user_type
    ]
    return user_messages

def get_read_receipt_byoeb_messages(byoeb_messages: List[ByoebMessageContext]):
    read_receipt_messages = [
        byoeb_message for byoeb_message in byoeb_messages
        if byoeb_message.message_category == MessageCategory.READ_RECEIPT.value
    ]
    return read_receipt_messages
    