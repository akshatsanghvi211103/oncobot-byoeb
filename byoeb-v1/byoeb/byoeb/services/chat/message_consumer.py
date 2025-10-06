import logging
import asyncio
import json
import hashlib
import byoeb.utils.utils as b_utils
import byoeb.services.chat.constants as constants
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from byoeb.models.message_category import MessageCategory
from byoeb.factory import ChannelClientFactory
from byoeb.chat_app.configuration.config import bot_config
from byoeb_core.models.byoeb.user import User
from byoeb.services.databases.mongo_db import UserMongoDBService, MessageMongoDBService
from byoeb_core.models.byoeb.message_context import ByoebMessageContext, ReplyContext

class Conversation(BaseModel):
    user_message: Optional[ByoebMessageContext]
    bot_message: Optional[ByoebMessageContext]
    user: User

class MessageConsmerService:

    __timeout_seconds = 60
    def __init__(
        self,
        config,
        user_db_service: UserMongoDBService,
        message_db_service: MessageMongoDBService,
        channel_client_factory: ChannelClientFactory
    ):
        self._config = config
        self._logger = logging.getLogger(self.__class__.__name__)
        self._user_db_service = user_db_service
        self._message_db_service = message_db_service
        self._channel_client_factory = channel_client_factory
        self._regular_user_type = bot_config["regular"]["user_type"]
        self._expert_user_types = bot_config["expert"]

    # TODO: Hash can be used or better way to get user by phone number
    def __get_user(
        self,
        users: List[User],
        phone_number_id,

    ) -> tuple[User, bool]:  # Returns (user, is_new_user)
        print(f"[DEBUG] Looking for user with phone_number_id: '{phone_number_id}' in {len(users)} retrieved users")
        user_id = hashlib.md5(phone_number_id.encode()).hexdigest()
        print(f"[DEBUG] Generated user_id: '{user_id}' from phone_number_id: '{phone_number_id}'")
        user = next((user for user in users if user.phone_number_id == phone_number_id), None)
        if user is None:
            print(f"[DEBUG] User not found in database, creating new user with ID: {user_id} and phone_number_id: '{phone_number_id}'")
            user = User(
                user_id=user_id,
                phone_number_id=phone_number_id,
                user_type=self._regular_user_type,
                user_language="en"
            )
            return user, True  # User is newly created
        else:
            print(f"[DEBUG] Found existing user with user_id: '{user.user_id}', phone_number_id: '{user.phone_number_id}', conversations: {len(user.last_conversations)}")
            return user, False  # User exists in database
    
    def __is_expert_user_type(
        self,
        user_type: str
    ):
        if user_type in self._expert_user_types.values():
            return True
        return False
    
    def __get_bot_message(
        self,
        messages: List[ByoebMessageContext],
        reply_id
    ) -> ByoebMessageContext:
        return next(
            (
                message for message in messages
                if reply_id is not None
                and message.message_context.message_id == reply_id
            ),
            None
        )

    async def __create_conversations(
        self,
        messages: List[ByoebMessageContext]
    ) -> List[ByoebMessageContext]:
        phone_numbers = list(set([message.user.phone_number_id for message in messages]))
        user_ids = list(set([hashlib.md5(number.encode()).hexdigest() for number in phone_numbers]))
        byoeb_users = await self._user_db_service.get_users(user_ids)
        bot_message_ids = list(
            set(message.reply_context.reply_id for message in messages if message.reply_context is not None and message.reply_context.reply_id is not None)
        )
        # print(f"🔍 Bot message IDs being searched: {bot_message_ids}")
        bot_messages = await self._message_db_service.get_bot_messages(bot_message_ids)
        
        # Debug: Show available bot messages
        # print(f"🤖 Available bot messages count: {len(bot_messages)}")
        if len(bot_messages) == 0 and len(bot_message_ids) > 0:
            print(f"❌ No bot messages found in DB for IDs: {bot_message_ids}")
        for i, bot_msg in enumerate(bot_messages):
            print(f"🤖 Bot message {i}: ID={bot_msg.message_context.message_id}")
        
        conversations = []
        
        for message in messages:
            user, is_new_user = self.__get_user(byoeb_users,message.user.phone_number_id)
            # Safety check: Handle case where reply_context might be None
            reply_id = message.reply_context.reply_id if message.reply_context is not None else None
            bot_message = self.__get_bot_message(bot_messages, reply_id)
            
            # Debug: Log reply context extraction status
            if user is not None and self.__is_expert_user_type(user.user_type):
                print(f"� Expert message debug - reply_id: {reply_id}, bot_message found: {bot_message is not None}")
                if message.reply_context:
                    print(f"🔍 Reply context exists: reply_id={message.reply_context.reply_id}")
                else:
                    print(f"� No reply context in message")
            
            conversation = ByoebMessageContext.model_validate(message)
            if user is not None and user.user_type == self._regular_user_type:
                conversation.message_category = MessageCategory.USER_TO_BOT.value
            elif user is not None and self.__is_expert_user_type(user.user_type):
                conversation.message_category = MessageCategory.EXPERT_TO_BOT.value
            conversation.user = user
            # Add a temporary attribute to track if this is a new user
            setattr(conversation, '_is_new_user', is_new_user)
            if is_new_user:
                print(f"[DEBUG] _is_new_user set to True for user_id: {user.user_id}, phone_number_id: {user.phone_number_id}")
            if bot_message is None:
                conversations.append(conversation)
                continue
            # Ensure reply_context exists before updating it
            if conversation.reply_context is None:
                conversation.reply_context = ReplyContext()
            conversation.reply_context.message_category = bot_message.message_category
            conversation.reply_context.reply_id = bot_message.message_context.message_id
            conversation.reply_context.reply_type = bot_message.message_context.message_type
            conversation.reply_context.reply_source_text = bot_message.message_context.message_source_text
            conversation.reply_context.reply_english_text = bot_message.message_context.message_english_text
            conversation.reply_context.additional_info = bot_message.message_context.additional_info
            conversation.cross_conversation_id = bot_message.cross_conversation_id
            conversation.cross_conversation_context = bot_message.cross_conversation_context
            conversations.append(conversation)
        return conversations
        
    async def consume(
        self,
        messages: list
    ) -> List[ByoebMessageContext]:
        byoeb_messages = []
        successfully_processed_messages = []
        for message in messages:
            json_message = json.loads(message)
            byoeb_message = ByoebMessageContext.model_validate(json_message)
            byoeb_messages.append(byoeb_message)
        start_time = datetime.now().timestamp()
        conversations = await self.__create_conversations(byoeb_messages)
        end_time = datetime.now().timestamp()
        b_utils.log_to_text_file(f"Conversations created in: {end_time - start_time} seconds")
        task = []
        for conversation in conversations:
            if conversation.user is not None:
                conversation.user.activity_timestamp = int(datetime.now().timestamp())
                # b_utils.log_to_text_file("Processing message: " + json.dumps(conversation.model_dump()))
                if conversation.user.user_type == self._regular_user_type:
                    task.append(self.__process_byoebuser_conversation(conversation))
                elif self.__is_expert_user_type(conversation.user.user_type):
                    task.append(self.__process_byoebexpert_conversation(conversation))
        results = await asyncio.gather(*task)
        for queries, processed_message, err in results:
            if err is not None or queries is None:
                continue
            successfully_processed_messages.append(processed_message)
        start_time = datetime.now().timestamp()
        user_queries = self._user_db_service.aggregate_queries(results)
        message_queries = self._message_db_service.aggregate_queries(results)
        
        print(f"Executing database queries - User updates: {len(user_queries.get('update', []))}, Message creates: {len(message_queries.get('create', []))}")
        
        await asyncio.gather(
            self._user_db_service.execute_queries(user_queries),
            self._message_db_service.execute_queries(message_queries)
        )
        end_time = datetime.now().timestamp()
        print(f"Database operations completed in {end_time - start_time:.2f} seconds")
        b_utils.log_to_text_file(f"DB queries executed in: {end_time - start_time} seconds")
        return successfully_processed_messages

    async def __process_byoebuser_conversation(self, byoeb_message):
        from byoeb.chat_app.configuration.dependency_setup import byoeb_user_process
        byoeb_message_copy = byoeb_message.model_copy(deep=True)
        try:
            queries = await asyncio.wait_for(byoeb_user_process.handle([byoeb_message]), timeout=self.__timeout_seconds)
            return queries, byoeb_message_copy, None
        except asyncio.TimeoutError:
            error_message = f"Timeout error: Task took longer than {self.__timeout_seconds} seconds."
            self._logger.error(error_message)
            print(error_message)
            return None, byoeb_message_copy, "TimeoutError"
        except Exception as e:
            self._logger.error(f"Error processing user message: {e}")
            print("Error processing user message: ", e)
            import traceback
            traceback.print_exc()
            return None, byoeb_message_copy, e

    async def __process_byoebexpert_conversation(
        self,
        byoeb_message: ByoebMessageContext
    ):
        from byoeb.chat_app.configuration.dependency_setup import byoeb_expert_process
        
        print(f"\n=== EXPERT MESSAGE CONSUMER DEBUG ===")
        print(f"👨‍⚕️ Processing expert message from: {byoeb_message.user.phone_number_id if byoeb_message.user else 'Unknown'}")
        # Show both text fields for debugging
        message_text = byoeb_message.message_context.message_english_text or byoeb_message.message_context.message_source_text
        print(f"💬 Message text: '{message_text}'")
        print(f"📝 Message type: {byoeb_message.message_context.message_type}")
        # print(f"🏷️ Message category: {byoeb_message.message_category}")
        # print(f"🔗 Has reply context: {byoeb_message.reply_context is not None}")
        if byoeb_message.reply_context:
            print(f"🔗 Reply ID: {byoeb_message.reply_context.reply_id}")
            print(f"🔗 Reply additional info: {byoeb_message.reply_context.additional_info}")
        # print(f"🔀 Has cross conversation context: {byoeb_message.cross_conversation_context is not None}")
        print("=== END EXPERT MESSAGE CONSUMER DEBUG ===\n")
        
        # print("Process expert message ", json.dumps(byoeb_message.model_dump()))
        byoeb_message_copy = byoeb_message.model_copy(deep=True)
        self._logger.info(f"Process expert message: {byoeb_message}")
        try:
            queries = await asyncio.wait_for(byoeb_expert_process.handle([byoeb_message]), timeout=self.__timeout_seconds)
            return queries, byoeb_message_copy, None
        except asyncio.TimeoutError:
            error_message = f"Timeout error: Expert process task took longer than {self.__timeout_seconds} seconds."
            self._logger.error(error_message)
            print(error_message)
            return None, byoeb_message_copy, "TimeoutError"
        # except Exception as e:
        #     self._logger.error(f"Error processing expert message: {e}")
        #     print("Error processing expert message: ", e)
        #     return None, byoeb_message_copy, e