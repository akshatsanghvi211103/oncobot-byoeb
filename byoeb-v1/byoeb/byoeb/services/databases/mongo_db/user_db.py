import byoeb.services.chat.constants as constants
from aiocache import Cache
from datetime import datetime, timedelta
from byoeb_core.models.byoeb.user import User
from byoeb.factory import MongoDBFactory
from typing import List, Dict, Any
from byoeb.services.databases.mongo_db.base import BaseMongoDBService

class UserMongoDBService(BaseMongoDBService):
    """Service class for user-related MongoDB operations."""

    def __init__(self, config, mongo_db_factory: MongoDBFactory):
        super().__init__(config, mongo_db_factory)
        self._history_length = self._config["app"]["history_length"]
        self.collection_name = self._config["databases"]["mongo_db"]["user_collection"]
        self.cache = Cache(Cache.MEMORY)
    
    async def invalidate_user_cache(self, user_id: str):
        print(self.cache)
        await self.cache.delete(user_id)

    async def get_user_activity_timestamp(self, user_id: str):
        """Get the user's last activity timestamp with caching."""
        cached_data = await self.cache.get(user_id)
        if cached_data is not None and isinstance(cached_data, dict):
            user = User(**cached_data)
            return user.activity_timestamp, True

        user_collection_client = await self._get_collection_client(self.collection_name)
        user_obj = await user_collection_client.afetch({"_id": user_id})

        if user_obj is None:
            return None

        user = User(**user_obj["User"])
        activity_timestamp = user.activity_timestamp

        await self.cache.set(user_id, user.model_dump(), ttl=3600)
        return activity_timestamp, False

    async def get_users(self, user_ids: List[str]) -> List[User]:
        """Fetch multiple users from the database."""
        # print(f"[DEBUG] get_users called with user_ids: {user_ids}")
        # print(f"[DEBUG] Using collection: '{self.collection_name}'")
        user_collection_client = await self._get_collection_client(self.collection_name)
        users_obj = await user_collection_client.afetch_all({"_id": {"$in": user_ids}})
        # print(f"[DEBUG] Raw users_obj from DB: {users_obj}")
        users = []
        for user_obj in users_obj:
            user = User(**user_obj["User"])
            # print(f"[DEBUG] Retrieved user with user_id: '{user.user_id}', phone_number_id: '{user.phone_number_id}', conversations: {len(user.last_conversations)}")
            # if user.last_conversations:
            #     print(f"[DEBUG]  Recent conversations: {user.last_conversations}")
            users.append(user)
        return users

    def user_create_query(self, user: User, qa: Dict[str, Any] = None):
        """Generate create query for new user."""
        latest_timestamp = str(int(datetime.now().timestamp()))
        user_data = {
            "_id": user.user_id,
            "User": {
                "user_id": user.user_id,
                "phone_number_id": user.phone_number_id,
                "user_type": user.user_type,
                "user_language": user.user_language,
                "activity_timestamp": latest_timestamp,
                "last_conversations": []
            }
        }

        print(f"[DEBUG] Creating user in collection '{self.collection_name}' with user_id: '{user.user_id}', phone_number_id: '{user.phone_number_id}'")
        if qa is not None:
            user_data["User"]["last_conversations"] = [qa]
            # print(f"[DEBUG] Initial conversation: Q: {qa.get('question', 'N/A')} | A: {qa.get('answer', 'N/A')[:50]}...")
        else:
            print(f"[DEBUG] No initial conversations")

        return user_data

    def user_activity_update_query(self, user: User, qa: Dict[str, Any] = None):
        """Generate update query for user activity, ensuring all fields are set for upsert."""
        latest_timestamp = str(int(datetime.now().timestamp()))
        update_data = {
            "$set": {
                "User.user_id": user.user_id,
                "User.phone_number_id": user.phone_number_id,
                "User.user_type": user.user_type,
                "User.user_language": user.user_language,
                "User.activity_timestamp": latest_timestamp,
            }
        }
        if qa is not None:
            last_convs = user.last_conversations
            if len(last_convs) >= self._history_length:
                last_convs.pop(0)
            last_convs.append(qa)
            update_data["$set"]["User.last_conversations"] = last_convs
        return ({"_id": user.user_id}, update_data)
    
    def aggregate_queries(
        self,
        results: List[Dict[str, Any]]
    ):
        new_user_queries = {
            constants.CREATE: [],
            constants.UPDATE: [],
        }
        for queries, _, err in results:
            if err is not None or queries is None:
                continue
            user_queries = queries.get(constants.USER_DB_QUERIES, {})
            if user_queries is not None and user_queries != {}:
                user_create_queries = user_queries.get(constants.CREATE,[])
                user_update_queries = user_queries.get(constants.UPDATE,[])
                new_user_queries[constants.CREATE].extend(user_create_queries)
                new_user_queries[constants.UPDATE].extend(user_update_queries)
        
        return new_user_queries
    
    async def execute_queries(self, queries: Dict[str, Any]):
        """Execute user database queries."""
        if not queries:
            return

        user_client = await self._get_collection_client(self.collection_name)
        if queries.get("create"):
            print(f"[DEBUG] About to call ainsert with: {queries['create']}")
            try:
                result = await user_client.ainsert(queries["create"])
                print(f"[DEBUG] ainsert returned: {result}")
                # Try to unpack if tuple
                if isinstance(result, tuple):
                    inserted_ids, error = result
                    print(f"[VERIFY] Inserted IDs: {inserted_ids}, Error: {error}")
                else:
                    print(f"[VERIFY] ainsert result: {result}")
            except Exception as e:
                print(f"[VERIFY] Exception during insert: {e}")
            # Verification: fetch the user back and print last_conversations
            for doc in queries["create"]:
                user_id = doc["_id"]
                try:
                    user_obj = await user_client.afetch({"_id": user_id})
                    print(f"[VERIFY] After CREATE fetch for user {user_id}: {user_obj}")
                    if user_obj:
                        print(f"[VERIFY] After CREATE, user {user_id} last_conversations: {user_obj['User'].get('last_conversations', [])}")
                except Exception as e:
                    print(f"[VERIFY] Exception during fetch after insert: {e}")
        if queries.get("update"):
            await user_client.aupdate(bulk_queries=queries["update"])
            # Verification: fetch the user back and print last_conversations
            for update in queries["update"]:
                user_id = update[0]["_id"]
                user_obj = await user_client.afetch({"_id": user_id})
                # if user_obj:
                #     print(f"[VERIFY] After UPDATE, user {user_id} last_conversations: {user_obj['User'].get('last_conversations', [])}")