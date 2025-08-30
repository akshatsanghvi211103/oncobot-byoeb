#!/usr/bin/env python3
"""
Test MongoDB/Cosmos DB connection and create collections for conversation history
"""
import asyncio
import os
from dotenv import load_dotenv
import pymongo
from datetime import datetime

# Load environment variables
load_dotenv('byoeb/keys.env')

async def test_mongodb_connection():
    """Test connection to Azure Cosmos DB (MongoDB API) and set up collections"""
    try:
        # Get connection string from environment
        connection_string = os.getenv('MONGO_DB_CONNECTION_STRING')
        if not connection_string:
            print("❌ MONGO_DB_CONNECTION_STRING not found in environment")
            return False
            
        if '<password>' in connection_string:
            print("❌ Please replace <password> in the connection string with actual credentials")
            return False
            
        print("🔌 Testing MongoDB connection...")
        print(f"Connection string: {connection_string[:50]}...")
        
        # Create MongoDB client
        client = pymongo.MongoClient(connection_string)
        
        # Test connection
        client.admin.command('ping')
        print("✅ Successfully connected to MongoDB!")
        
        # Connect to oncobotdb database
        db = client['oncobotdb']
        print(f"✅ Connected to database: oncobotdb")
        
        # List existing collections
        collections = db.list_collection_names()
        print(f"📁 Existing collections: {collections}")
        
        # Create users collection if it doesn't exist
        if 'users' not in collections:
            users_collection = db['users']
            # Create index on user_id for better performance
            users_collection.create_index("_id")
            print("✅ Created 'users' collection")
        else:
            print("✅ 'users' collection already exists")
            
        # Create messages collection if it doesn't exist  
        if 'messages' not in collections:
            messages_collection = db['messages']
            # Create indexes for better performance
            messages_collection.create_index("_id")
            messages_collection.create_index("timestamp")
            print("✅ Created 'messages' collection")
        else:
            print("✅ 'messages' collection already exists")
            
        # Test basic operations
        print("\n🧪 Testing basic operations...")
        
        # Test user collection
        users_collection = db['users']
        test_user = {
            "_id": "test_user_12345",
            "User": {
                "user_id": "test_user_12345",
                "user_name": "Test User",
                "phone_number_id": "911234567890",
                "experts": {
                    "medical": ["918904954952"],
                    "logistical": []
                },
                "created_timestamp": int(datetime.now().timestamp()),
                "activity_timestamp": int(datetime.now().timestamp()),
                "last_conversations": []
            }
        }
        
        # Insert test user (replace if exists)
        result = users_collection.replace_one(
            {"_id": test_user["_id"]}, 
            test_user, 
            upsert=True
        )
        print(f"✅ Test user operation: {'updated' if result.matched_count > 0 else 'inserted'}")
        
        # Test message collection
        messages_collection = db['messages']
        test_message = {
            "_id": "test_message_12345",
            "message_data": {
                "message_context": {
                    "message_id": "test_message_12345",
                    "message_english_text": "Test conversation history message",
                    "message_source_text": "Test conversation history message"
                },
                "user": {
                    "user_id": "test_user_12345",
                    "phone_number_id": "911234567890"
                }
            },
            "timestamp": str(int(datetime.now().timestamp()))
        }
        
        # Insert test message (replace if exists)
        result = messages_collection.replace_one(
            {"_id": test_message["_id"]}, 
            test_message, 
            upsert=True
        )
        print(f"✅ Test message operation: {'updated' if result.matched_count > 0 else 'inserted'}")
        
        # Query test data
        user_count = users_collection.count_documents({})
        message_count = messages_collection.count_documents({})
        print(f"📊 Collection stats: {user_count} users, {message_count} messages")
        
        # Clean up test data
        users_collection.delete_one({"_id": "test_user_12345"})
        messages_collection.delete_one({"_id": "test_message_12345"})
        print("🧹 Cleaned up test data")
        
        client.close()
        print("\n🎉 MongoDB connection and setup successful!")
        print("✅ Ready for conversation history tracking")
        return True
        
    except Exception as e:
        print(f"❌ MongoDB connection failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("=== MongoDB Connection Test ===")
    success = asyncio.run(test_mongodb_connection())
    if success:
        print("\n🚀 You can now start using conversation history tracking!")
    else:
        print("\n⚠️  Please check your credentials and try again")
