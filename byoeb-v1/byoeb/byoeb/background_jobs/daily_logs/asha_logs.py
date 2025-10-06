import time
import pandas as pd
from datetime import datetime
from byoeb.background_jobs.config import app_config
from byoeb.background_jobs.dependency_setup import user_db_service
from byoeb.factory import MongoDBFactory

SINGLETON = "singleton"
db_provider = app_config["app"]["db_provider"]
message_collection_name = app_config["databases"]["mongo_db"]["message_collection"]

async def get_user_infos(batch, user_info_dict):
    user_ids = set()
    for entry in batch:
        user = entry['message_data'].get("user", {})
        user_id = user.get("user_id")
        if user_id and user_id not in user_info_dict:
            user_ids.add(user_id)
    user_info_list = await user_db_service.get_users(list(user_ids))

    # Update the passed-in dictionary instead of overwriting it
    user_info_dict.update({user.user_id: user for user in user_info_list})

    return user_info_dict

    
def extract_fields(entry, user_info_dict):
    user = entry.get("user", {})
    user_id = user.get("user_id")
    user = user_info_dict[user_id]
    message_context = entry.get("message_context", {})
    message_additional_info = message_context.get("additional_info", {})
    reply_context = entry.get("reply_context", {})
    reply_additional_info = reply_context.get("additional_info", {})
    
    # Handle empty or missing user_location
    user_location = user.user_location

    incoming_ts = entry.get("incoming_timestamp")
    outgoing_ts = entry.get("outgoing_timestamp")
    onboarding_ts = user.created_timestamp
    
    

    # Convert timestamp to day format (dd-mm-yyyy)
    day = datetime.fromtimestamp(incoming_ts).strftime("%d-%m-%Y") if incoming_ts else None
    onboarding_date = datetime.fromtimestamp(onboarding_ts).strftime("%d-%m-%Y") if onboarding_ts else None

    status = message_additional_info.get("status")
    if not status:
        status = "resolved"

    return {
        "user_id": user.user_id,
        "phone_number_id": user.phone_number_id,
        "test_user": user.test_user,
        "user_language": user.user_language,
        "onboarding_date": onboarding_date,
        "district": user_location.get("district"),
        "block": user_location.get("block"),
        "sector": user_location.get("sector"),
        "sub_center": user_location.get("sub_center"),
        "message_type": reply_context.get("reply_type"),
        "message_category": entry.get("message_category"),
        "query_type": reply_additional_info.get("query_type"),
        "status": status,
        "query_source": reply_context.get("reply_source_text"),
        "query_en": reply_additional_info.get("query_en"),
        "rewritten_query": reply_context.get("reply_english_text"),
        "answer_english": message_context.get("message_english_text"),
        "answer_source": message_context.get("message_source_text"),
        "incoming_timestamp": incoming_ts,
        "outgoing_timestamp": outgoing_ts,
        "log_date": day
    }

async def fetch_and_process_user_messages(start_timestamp: str, end_timestamp: str, message_category: str, message_collection):
    query = query = {
        "timestamp": {
            "$gte": start_timestamp,
            "$lte": end_timestamp
        },
        "message_data.message_category": message_category
    }
    cursor = message_collection.find(query)
    user_info_dict = {}
    final_df = pd.DataFrame()
    while True:
        batch = await cursor.to_list(length=1000)
        if not batch:
            break
        # Process each batch
        user_info_dict = await get_user_infos(batch, user_info_dict)
        current_data = [extract_fields(entry['message_data'], user_info_dict) for entry in batch]
        # Convert to DataFrame and append to final_df
        temp_df = pd.DataFrame(current_data)
        final_df = pd.concat([final_df, temp_df], ignore_index=True)
    if final_df.empty:
        return final_df
    final_df.sort_values(by=["incoming_timestamp"], inplace=True, ascending=False, ignore_index=True)
    return final_df

async def fetch_daily_logs(start_timestamp: str, end_timestamp: str):
    mongo_db_factory = MongoDBFactory(
        config=app_config,
        scope=SINGLETON
    )
    mongo_db = await mongo_db_factory.get(db_provider)
    message_collection = mongo_db.get_collection(message_collection_name)
    answer_df = await fetch_and_process_user_messages(
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        message_category="bot_to_asha_response",
        message_collection=message_collection
    )
    audio_idk_df = await fetch_and_process_user_messages(
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        message_category="audio_idk",
        message_collection=message_collection
    )
    text_idk_df = await fetch_and_process_user_messages(
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        message_category="text_idk",
        message_collection=message_collection
    )
    ashas_df = pd.concat([answer_df, audio_idk_df, text_idk_df], ignore_index=True)
    if ashas_df.empty:
        return ashas_df
    ashas_df.sort_values(by=["incoming_timestamp"], inplace=True, ascending=False, ignore_index=True)
    return ashas_df