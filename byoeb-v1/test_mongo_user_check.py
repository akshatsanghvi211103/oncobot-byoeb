import asyncio
from byoeb.services.databases.mongo_db.user_db import UserMongoDBService
from byoeb_core.models.byoeb.user import User
from byoeb.factory.mongo_db import MongoDBFactory
from byoeb.chat_app.configuration.config import app_config

async def test_user_create_and_update():
    mongo_db_factory = MongoDBFactory(app_config, scope="singleton")
    user_db = UserMongoDBService(app_config, mongo_db_factory)

    # Create a new user
    user_id = "test_user_id_123"
    phone_number_id = "test_phone_123"
    user = User(
        user_id=user_id,
        phone_number_id=phone_number_id,
        user_type="normal",
        user_language="en",
        last_conversations=[]
    )
    print("Inserting new user...")
    await user_db.execute_queries({"create": [user_db.user_create_query(user)]})

    # Update the user's language
    user.user_language = "fr"
    print("Updating user language to 'fr'...")
    await user_db.execute_queries({"update": [user_db.user_activity_update_query(user)]})

    # Retrieve the user
    print("Retrieving user...")
    users = await user_db.get_users([user_id])
    if users:
        print("User found:")
        print(users[0].model_dump())
        print(f"User language: {users[0].user_language}")
    else:
        print("User not found!")

if __name__ == "__main__":
    asyncio.run(test_user_create_and_update())
