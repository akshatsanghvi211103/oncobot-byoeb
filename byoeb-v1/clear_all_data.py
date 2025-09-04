#!/usr/bin/env python3
"""
Script to clear all data from queues and MongoDB collections
"""
import asyncio
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'byoeb'))

from byoeb.chat_app.configuration.dependency_setup import message_db_service
from byoeb.chat_app.configuration.config import app_config

async def clear_mongodb_data():
    """Clear all MongoDB message collections"""
    print("🗑️ Clearing MongoDB message collections...")
    
    if message_db_service is None:
        print("❌ MongoDB service not available (db_provider is 'none')")
        return False
        
    try:
        response, error = await message_db_service.delete_message_collection()
        if error:
            print(f"❌ Error clearing MongoDB: {error}")
            return False
        else:
            print("✅ MongoDB message collection cleared successfully")
            return True
    except Exception as e:
        print(f"❌ Exception clearing MongoDB: {e}")
        return False

def clear_azure_queues():
    """Clear Azure Storage queues using Azure CLI"""
    import subprocess
    
    print("🗑️ Clearing Azure Storage queues...")
    
    queues = ['botmessages', 'statusmessages', 'channelmessages']
    account_name = 'kgretrieval'
    
    for queue_name in queues:
        try:
            print(f"  Clearing queue: {queue_name}")
            result = subprocess.run([
                'az', 'storage', 'message', 'clear',
                '--queue-name', queue_name,
                '--account-name', account_name,
                '--auth-mode', 'login'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"  ✅ Queue {queue_name} cleared successfully")
            else:
                if "QueueNotFound" in result.stderr:
                    print(f"  ⚠️ Queue {queue_name} does not exist (already empty)")
                else:
                    print(f"  ❌ Error clearing queue {queue_name}: {result.stderr}")
        except Exception as e:
            print(f"  ❌ Exception clearing queue {queue_name}: {e}")

async def main():
    """Main function to clear all data"""
    print("🧹 Starting data cleanup process...")
    print("=" * 50)
    
    # Clear Azure Storage queues
    clear_azure_queues()
    print()
    
    # Clear MongoDB collections
    mongodb_success = await clear_mongodb_data()
    print()
    
    print("=" * 50)
    if mongodb_success:
        print("✅ All data cleared successfully!")
    else:
        print("⚠️ Data clearing completed with some issues")
    
    print("🎉 Cleanup process finished.")

if __name__ == "__main__":
    asyncio.run(main())
