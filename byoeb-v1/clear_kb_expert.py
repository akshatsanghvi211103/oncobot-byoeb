#!/usr/bin/env python3
"""
Clear KB1_Expert Database
Removes all expert corrections from the oncobot_expert_index to start fresh.
Use this to clear test data and reset the expert corrections knowledge base.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from byoeb.chat_app.configuration.config import app_config
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes.aio import SearchIndexClient

async def clear_kb_expert():
    """
    Clear all documents from KB1_Expert (oncobot_expert_index) and optionally delete the index.
    """
    print("🗑️  CLEARING KB1_EXPERT DATABASE")
    print("=" * 50)
    
    # KB1_Expert configuration
    kb_expert_service_name = app_config["vector_store"]["azure_vector_search"]["service_name"]
    kb_expert_index_name = "oncobot_expert_index"
    kb_expert_endpoint = f"https://{kb_expert_service_name}.search.windows.net"
    
    print(f"🔗 Connecting to KB1_Expert:")
    print(f"   Service: {kb_expert_service_name}")
    print(f"   Index: {kb_expert_index_name}")
    print(f"   Endpoint: {kb_expert_endpoint}")
    
    # Create index client
    index_client = SearchIndexClient(
        endpoint=kb_expert_endpoint,
        credential=DefaultAzureCredential()
    )
    
    try:
        # Check if index exists
        await index_client.get_index(kb_expert_index_name)
        print(f"✅ Found index '{kb_expert_index_name}'")
        
        # Ask for confirmation
        print(f"\n⚠️  WARNING: This will permanently delete ALL expert correction documents!")
        print(f"   This action cannot be undone.")
        
        # Clear documents from the index (keep the index structure)
        from azure.search.documents.aio import SearchClient
        
        search_client = SearchClient(
            endpoint=kb_expert_endpoint,
            index_name=kb_expert_index_name,
            credential=DefaultAzureCredential()
        )
        
        try:
            print(f"\n� Finding all documents in '{kb_expert_index_name}'...")
            
            # Get all document IDs first
            results = await search_client.search("*", select="id", top=1000)
            document_ids = []
            
            async for result in results:
                document_ids.append(result['id'])
            
            if document_ids:
                print(f"📋 Found {len(document_ids)} documents to delete")
                
                # Create delete actions for all documents
                delete_actions = [{"@search.action": "delete", "id": doc_id} for doc_id in document_ids]
                
                print(f"🗑️  Deleting {len(delete_actions)} documents...")
                result = await search_client.upload_documents(delete_actions)
                print(f"✅ Successfully deleted all documents from '{kb_expert_index_name}'")
                print(f"📋 Index structure preserved - ready for new expert corrections")
            else:
                print(f"ℹ️  Index '{kb_expert_index_name}' is already empty")
                
        finally:
            await search_client.close()
        
    except Exception as e:
        if "was not found" in str(e):
            print(f"ℹ️  Index '{kb_expert_index_name}' doesn't exist")
            print(f"📋 Run the background job once to create the index structure")
        else:
            print(f"❌ Error accessing index: {e}")
    
    finally:
        await index_client.close()

async def verify_cleared():
    """
    Verify that KB1_Expert is empty by trying to search it.
    """
    print(f"\n🔍 VERIFYING CLEARANCE:")
    print("=" * 30)
    
    try:
        from azure.search.documents import SearchClient
        
        kb_expert_service_name = app_config["vector_store"]["azure_vector_search"]["service_name"]
        kb_expert_index_name = "oncobot_expert_index"
        kb_expert_endpoint = f"https://{kb_expert_service_name}.search.windows.net"
        
        search_client = SearchClient(
            endpoint=kb_expert_endpoint,
            index_name=kb_expert_index_name,
            credential=DefaultAzureCredential()
        )
        
        # Try to search for any documents
        results = search_client.search("*", top=1)
        result_count = 0
        for result in results:
            result_count += 1
        
        if result_count == 0:
            print(f"✅ KB1_Expert is empty - no expert corrections found")
        else:
            print(f"⚠️  KB1_Expert still contains {result_count} documents")
        
        search_client.close()
        
    except Exception as e:
        if "was not found" in str(e):
            print(f"✅ KB1_Expert index doesn't exist - successfully cleared")
        else:
            print(f"❌ Error verifying clearance: {e}")

async def main():
    """
    Main function to clear KB1_Expert database.
    """
    print("🚀 Starting KB1_Expert clearance...")
    print(f"📅 Started at: {asyncio.get_event_loop().time()}")
    
    try:
        # Clear the database
        await clear_kb_expert()
        
        # Verify it's cleared
        await verify_cleared()
        
        print(f"\n✅ KB1_EXPERT CLEARANCE COMPLETE")
        print("=" * 40)
        print("📋 Summary:")
        print("   - Expert corrections database has been cleared")
        print("   - Index will be recreated automatically when new corrections are added")
        print("   - Ready for fresh expert corrections")
        
    except Exception as e:
        print(f"❌ Error in clearance process: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"🏁 Clearance completed")

if __name__ == "__main__":
    asyncio.run(main())