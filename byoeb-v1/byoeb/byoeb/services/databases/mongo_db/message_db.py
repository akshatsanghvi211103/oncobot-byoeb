import byoeb.services.chat.constants as constants
from datetime import datetime
from typing import List, Dict, Any
from byoeb.factory import MongoDBFactory
from byoeb.services.databases.mongo_db.base import BaseMongoDBService
from byoeb_core.models.byoeb.message_context import ByoebMessageContext
from byoeb_integrations.databases.mongo_db.azure.async_azure_cosmos_mongo_db import AsyncAzureCosmosMongoDBCollection

class MessageMongoDBService(BaseMongoDBService):
    """Service class for message-related MongoDB operations."""

    def __init__(self, config, mongo_db_factory: MongoDBFactory):
        super().__init__(config, mongo_db_factory)
        self.collection_name = self._config["databases"]["mongo_db"]["message_collection"]

    async def get_bot_messages(self, bot_message_ids: List[str]) -> List[ByoebMessageContext]:
        """Fetch multiple bot messages from the database."""
        print(f"🔍 GET_BOT_MESSAGES: Searching for {len(bot_message_ids)} message IDs")
        for i, msg_id in enumerate(bot_message_ids):
            print(f"   ID {i+1}: {msg_id}")
            
        message_collection_client = await self._get_collection_client(self.collection_name)
        
        print(f"🔍 GET_BOT_MESSAGES: Executing database query with filter: {{'_id': {{'$in': {bot_message_ids}}}}}")
        
        try:
            messages_obj = await message_collection_client.afetch_all({"_id": {"$in": bot_message_ids}})
            print(f"🔍 GET_BOT_MESSAGES: Database returned {len(messages_obj)} results")
            
            if len(messages_obj) == 0:
                print("❌ GET_BOT_MESSAGES: No messages found in database")
                print("🔍 Let's check what IDs actually exist in the database...")
                
                # Debug: Get recent messages to see what IDs are actually stored
                try:
                    recent_timestamp = str(int((datetime.now().timestamp() - 3600) * 1000))  # Last hour
                    all_recent = await message_collection_client.afetch_all({"timestamp": {"$gt": recent_timestamp}})
                    print(f"🔍 Recent messages in database (last hour): {len(all_recent)}")
                    
                    for i, msg in enumerate(all_recent[:5]):  # Show first 5
                        stored_id = msg.get("_id", "No ID")
                        message_data = msg.get("message_data", {})
                        message_context = message_data.get("message_context", {})
                        stored_text = message_context.get("message_english_text", "")
                        print(f"   Recent {i+1}: ID={stored_id}, Text='{stored_text[:50]}...'")
                        
                except Exception as e:
                    print(f"❌ Failed to get recent messages for debug: {e}")
            else:
                print("✅ GET_BOT_MESSAGES: Found matching messages")
                for i, msg_obj in enumerate(messages_obj):
                    stored_id = msg_obj.get("_id", "No ID")
                    print(f"   Found {i+1}: ID={stored_id}")
            
            result = [ByoebMessageContext(**msg_obj["message_data"]) for msg_obj in messages_obj]
            print(f"🔍 GET_BOT_MESSAGES: Returning {len(result)} ByoebMessageContext objects")
            return result
            
        except Exception as e:
            print(f"❌ GET_BOT_MESSAGES: Database query failed: {e}")
            raise

    async def get_latest_bot_messages_by_timestamp(self, timestamp: str):
        """Fetch bot messages with timestamps greater than the given timestamp."""
        message_collection_client = await self._get_collection_client(self.collection_name)
        messages_obj = await message_collection_client.afetch_all({"timestamp": {"$gt": timestamp}})
        return [ByoebMessageContext(**msg_obj["message_data"]) for msg_obj in messages_obj]

    def correction_update_query(
        self,
        byoeb_user_messages: List[ByoebMessageContext],
        byoeb_expert_message: ByoebMessageContext
    ):
        for byoeb_user_message in byoeb_user_messages:
            reply_context = byoeb_user_message.reply_context
            update_id = reply_context.additional_info.get(constants.UPDATE_ID)
            reply_context.reply_id = update_id
            byoeb_user_message.reply_context = reply_context
        update_data = {
            "$set":{
                "message_data.message_context.additional_info.correction_en_text": byoeb_expert_message.reply_context.additional_info.get(constants.CORRECTION_EN),
                "message_data.message_context.additional_info.correction_source_text": byoeb_expert_message.reply_context.additional_info.get(constants.CORRECTION_SOURCE),
            }
        }
        expert_update_queries = [({"_id": byoeb_expert_message.reply_context.reply_id}, update_data)]
        user_update_queries = []
        for byoeb_user_message in byoeb_user_messages:
            update_data = {
                "$set":{
                    "message_data.message_context.additional_info.corrected_en_text": byoeb_user_message.message_context.message_english_text,
                    "message_data.message_context.additional_info.corrected_source_text": byoeb_user_message.message_context.message_source_text
                }
            }
            user_update_queries.append(({"_id": byoeb_user_message.reply_context.reply_id}, update_data))
        return expert_update_queries + user_update_queries
    
    def verification_status_update_query(
        self,
        byoeb_user_messages: List[ByoebMessageContext],
        byoeb_expert_message: ByoebMessageContext
    ):
        for byoeb_user_message in byoeb_user_messages:
            reply_context = byoeb_user_message.reply_context
            update_id = reply_context.additional_info.get(constants.UPDATE_ID)
            reply_context.reply_id = update_id
            byoeb_user_message.reply_context = reply_context
        verification_status_param = constants.VERIFICATION_STATUS
        expert_verification_status = byoeb_expert_message.reply_context.additional_info.get(verification_status_param)
        expert_modified_timestamp = byoeb_expert_message.reply_context.additional_info.get(constants.MODIFIED_TIMESTAMP)
        user_verification_status = byoeb_user_messages[0].reply_context.additional_info.get(verification_status_param)
        user_modified_timestamp = byoeb_user_messages[0].reply_context.additional_info.get(constants.MODIFIED_TIMESTAMP)
        update_data = {
            "$set":{
                "message_data.message_context.additional_info.verification_status": expert_verification_status,
                "message_data.message_context.additional_info.modified_timestamp": expert_modified_timestamp,
                "message_data.cross_conversation_context.messages_context.$[].message_context.additional_info.verification_status": user_verification_status
            }
        }
        expert_update_queries = [({"_id": byoeb_expert_message.reply_context.reply_id}, update_data)]
        user_update_queries = []
        for byoeb_user_message in byoeb_user_messages:
            update_data = {
                "$set":{
                    "message_data.message_context.additional_info.verification_status": user_verification_status,
                    "message_data.message_context.additional_info.modified_timestamp": user_modified_timestamp
                }
            }
            user_update_queries.append(({"_id": byoeb_user_message.reply_context.reply_id}, update_data))
        return expert_update_queries + user_update_queries
    
    def message_create_queries(self, byoeb_messages: List[ByoebMessageContext]) -> List[Dict[str, Any]]:
        """Generate create queries for messages."""
        if not byoeb_messages:
            print("🔍 MESSAGE_CREATE_QUERIES: No messages to create")
            return []
        
        print(f"🔍 MESSAGE_CREATE_QUERIES: Processing {len(byoeb_messages)} messages for database storage")
        
        # Debug: Check what types we're actually getting
        for i, message in enumerate(byoeb_messages):
            if not hasattr(message, 'message_context'):
                print(f"❌ ERROR: Item {i} in byoeb_messages is type {type(message)}, not ByoebMessageContext")
                print(f"   Content: {message}")
                raise TypeError(f"Expected ByoebMessageContext, got {type(message)} at index {i}")
        
        queries = []
        for i, message in enumerate(byoeb_messages):
            message_id = message.message_context.message_id
            message_type = message.message_context.message_type
            message_text = message.message_context.message_english_text
            
            # Check if this looks like an expert verification message
            is_expert_verification = (
                message_text and 
                (("Question:" in message_text and "Bot_Answer:" in message_text) or
                "Is the answer correct?" in message_text)
            )
            
            query = {
                "_id": message_id,
                "message_data": message.model_dump(),
                "timestamp": str(int(datetime.now().timestamp())),
            }
            queries.append(query)
            
            print(f"🔍 MESSAGE_CREATE_QUERIES: Message {i+1}")
            print(f"   Message ID: {message_id}")
            print(f"   Message Type: {message_type}")
            print(f"   Is Expert Verification: {is_expert_verification}")
            print(f"   Text Preview: {(message_text or '')[:80]}...")
            
        print(f"🔍 MESSAGE_CREATE_QUERIES: Generated {len(queries)} database create queries")
        return queries
    
    def aggregate_queries(
        self,
        results: List[Dict[str, Any]]
    ):
        new_message_queries = {
            constants.CREATE: [],
            constants.UPDATE: [],
        }
        for queries, _, err in results:
            if err is not None or queries is None:
                continue
            message_queries = queries.get(constants.MESSAGE_DB_QUERIES, {})
            if message_queries is not None and message_queries != {}:
                message_create_queries = message_queries.get(constants.CREATE,[])
                message_update_queries = message_queries.get(constants.UPDATE,[])
                new_message_queries[constants.CREATE].extend(message_create_queries)
                new_message_queries[constants.UPDATE].extend(message_update_queries)
        
        return new_message_queries
    
    async def execute_queries(self, queries: Dict[str, Any]):
        """Execute message database queries."""
        if not queries:
            print("🔍 EXECUTE_QUERIES: No queries to execute")
            return

        print(f"🔍 EXECUTE_QUERIES: Starting execution with queries: {list(queries.keys())}")
        
        message_client = await self._get_collection_client(self.collection_name)
        
        if queries.get("create"):
            create_queries = queries["create"]
            print(f"🔍 EXECUTE_QUERIES: Executing {len(create_queries)} CREATE operations")
            
            for i, query in enumerate(create_queries):
                message_id = query.get("_id", "Unknown")
                print(f"   CREATE {i+1}: Message ID = {message_id}")
                
            try:
                result = await message_client.ainsert(create_queries)
                print(f"✅ EXECUTE_QUERIES: CREATE operations completed successfully")
                print(f"   Result: {result}")
            except Exception as e:
                print(f"❌ EXECUTE_QUERIES: CREATE operations failed: {e}")
                raise
                
        if queries.get("update"):
            update_queries = queries["update"]
            print(f"🔍 EXECUTE_QUERIES: Executing {len(update_queries)} UPDATE operations")
            try:
                result = await message_client.aupdate(bulk_queries=update_queries)
                print(f"✅ EXECUTE_QUERIES: UPDATE operations completed successfully")
                print(f"   Result: {result}")
            except Exception as e:
                print(f"❌ EXECUTE_QUERIES: UPDATE operations failed: {e}")
                raise
                
        print(f"🔍 EXECUTE_QUERIES: All database operations completed")

    async def update_message_id(self, old_message_id: str, new_message_id: str):
        """Update a message's ID in the database after sending to external service."""
        print(f"🔄 UPDATE_MESSAGE_ID: Starting ID update process")
        print(f"   Old ID: {old_message_id}")
        print(f"   New ID: {new_message_id}")
        
        try:
            message_collection_client = await self._get_collection_client(self.collection_name)
            
            print(f"🔄 UPDATE_MESSAGE_ID: Looking for document with old ID: {old_message_id}")
            # First, find the document with the old ID
            old_doc = await message_collection_client.afetch({"_id": old_message_id})
            if not old_doc:
                print(f"❌ UPDATE_MESSAGE_ID: Message with ID {old_message_id} not found for update")
                
                # Debug: Check if the message exists with a different structure
                print(f"🔍 UPDATE_MESSAGE_ID: Checking if message exists in different format...")
                try:
                    # Check if it exists in message_data.message_context.message_id
                    alt_query = {"message_data.message_context.message_id": old_message_id}
                    alt_doc = await message_collection_client.afetch(alt_query)
                    if alt_doc:
                        print(f"✅ UPDATE_MESSAGE_ID: Found message in nested structure with _id: {alt_doc.get('_id')}")
                        print(f"   This suggests the message was stored with a different _id than the message_id")
                    else:
                        print(f"❌ UPDATE_MESSAGE_ID: Message not found in nested structure either")
                except Exception as e:
                    print(f"❌ UPDATE_MESSAGE_ID: Error checking nested structure: {e}")
                
                return False
                
            print(f"✅ UPDATE_MESSAGE_ID: Found document with old ID")
            print(f"   Document _id: {old_doc.get('_id')}")
            print(f"   Document timestamp: {old_doc.get('timestamp')}")
            
            # Check the current message_id in the document
            message_data = old_doc.get("message_data", {})
            message_context = message_data.get("message_context", {})
            current_message_id = message_context.get("message_id")
            print(f"   Current message_context.message_id: {current_message_id}")
            
            print(f"🔄 UPDATE_MESSAGE_ID: Deleting document with old ID")
            # Delete the old document
            delete_result = await message_collection_client.adelete_one({"_id": old_message_id})
            print(f"   Delete result: {delete_result}")
            
            print(f"🔄 UPDATE_MESSAGE_ID: Creating new document with updated ID")
            # Update the message_id in the document and insert with new ID
            old_doc["_id"] = new_message_id
            old_doc["message_data"]["message_context"]["message_id"] = new_message_id
            insert_result = await message_collection_client.ainsert_one(old_doc)
            print(f"   Insert result: {insert_result}")
            
            print(f"✅ UPDATE_MESSAGE_ID: Successfully updated message ID: {old_message_id} -> {new_message_id}")
            
            # Verify the update worked
            print(f"🔍 UPDATE_MESSAGE_ID: Verifying update worked...")
            verify_doc = await message_collection_client.afetch({"_id": new_message_id})
            if verify_doc:
                print(f"✅ UPDATE_MESSAGE_ID: Verification successful - document found with new ID")
            else:
                print(f"❌ UPDATE_MESSAGE_ID: Verification failed - document not found with new ID")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ UPDATE_MESSAGE_ID: Error updating message ID: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def delete_message_collection(self):
        """Delete the message collection."""
        try:
            message_client = await self._get_collection_client(self.collection_name)
            if isinstance(message_client, AsyncAzureCosmosMongoDBCollection):
                await message_client.adelete_collection()
                return True, None
            return False, None
        except Exception as e:
            return False, e