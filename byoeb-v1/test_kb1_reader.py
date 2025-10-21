#!/usr/bin/env python3
"""
Test KB1 Reader
Reads and displays all entries from KB1 (oncobot_knowledge_base) in raw form.
"""

import asyncio
import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'byoeb'))

from byoeb.chat_app.configuration.config import app_config

async def read_kb1_entries():
    """
    Read all entries from KB1 knowledge base (Azure Vector Search) and display them raw.
    """
    try:
        print("🚀 Starting KB1 reader...")
        print(f"📅 Started at: {datetime.now()}")
        print(f"{'='*80}")
        
        # Import Azure Search dependencies and credentials
        from azure.search.documents.aio import SearchClient
        from azure.identity import DefaultAzureCredential
        
        # Get Azure Search configuration from app_config
        azure_search_service_name = app_config["vector_store"]["azure_vector_search"]["service_name"]
        azure_search_doc_index_name = app_config["vector_store"]["azure_vector_search"]["doc_index_name"]
        
        # Construct endpoint URL
        search_endpoint = f"https://{azure_search_service_name}.search.windows.net"
        
        print(f"🔗 Connecting to Azure Search:")
        print(f"   Service: {azure_search_service_name}")
        print(f"   Endpoint: {search_endpoint}")
        print(f"   Index: {azure_search_doc_index_name}")
        
        # Create search client with DefaultAzureCredential
        search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=azure_search_doc_index_name,
            credential=DefaultAzureCredential()
        )
        
        # Search for all KB1 entries (Q&A pairs)
        print(f"\n🔍 Searching for KB1 entries (source='oncobot_knowledge_base')...")
        
        # Use search to get all entries with KB1 source
        search_results = await search_client.search(
            search_text="*",  # Get all documents
            filter="source eq 'oncobot_knowledge_base'",
            select=['id', 'question', 'answer', 'category', 'combined_text', 'source', 'question_number'],
            top=1000  # Get up to 1000 entries
        )
        
        kb1_entries = []
        async for result in search_results:
            kb1_entries.append(dict(result))
        
        print(f"📊 Found {len(kb1_entries)} KB1 entries")
        print(f"{'='*80}")
        
        # Display first 5 entries in raw form as samples
        sample_count = min(5, len(kb1_entries))
        print(f"\n🔍 DISPLAYING FIRST {sample_count} ENTRIES AS SAMPLES:")
        
        for i in range(sample_count):
            entry = kb1_entries[i]
            print(f"\n{'─'*60}")
            print(f"📋 KB1 SAMPLE ENTRY #{i+1}")
            print(f"{'─'*60}")
            
            # Display all fields in raw form
            for field, value in entry.items():
                if value is not None:
                    # Truncate very long values for readability
                    if isinstance(value, str) and len(value) > 200:
                        display_value = value[:200] + "..."
                    else:
                        display_value = value
                    print(f"{field:15}: {display_value}")
                else:
                    print(f"{field:15}: None")
            
            print(f"{'─'*60}")
        
        # Show a few more entries with just question and answer
        if len(kb1_entries) > sample_count:
            print(f"\n🔍 ADDITIONAL ENTRIES (QUESTION & ANSWER ONLY):")
            additional_count = min(10, len(kb1_entries) - sample_count)
            
            for i in range(sample_count, sample_count + additional_count):
                entry = kb1_entries[i]
                print(f"\n📋 ENTRY #{i+1}:")
                print(f"   Question: {entry.get('question', 'N/A')}")
                print(f"   Answer: {entry.get('answer', 'N/A')[:150]}..." if len(entry.get('answer', '')) > 150 else f"   Answer: {entry.get('answer', 'N/A')}")
                print(f"   Category: {entry.get('category', 'N/A')}")
                print(f"   ID: {entry.get('id', 'N/A')}")
        
        print(f"\n{'='*80}")
        print(f"✅ COMPLETE: Displayed {len(kb1_entries)} KB1 entries in raw form")
        print(f"📅 Finished at: {datetime.now()}")
        
        # Summary statistics
        print(f"\n📊 KB1 STATISTICS:")
        print(f"   Total entries: {len(kb1_entries)}")
        
        # Count by category
        categories = {}
        for entry in kb1_entries:
            category = entry.get('category', 'Unknown')
            categories[category] = categories.get(category, 0) + 1
        
        print(f"   Categories:")
        for category, count in categories.items():
            print(f"     - {category}: {count}")
        
        # Count entries with question numbers
        with_qnum = sum(1 for entry in kb1_entries if entry.get('question_number'))
        print(f"   Entries with question_number: {with_qnum}")
        print(f"   Entries without question_number: {len(kb1_entries) - with_qnum}")
        
        await search_client.close()
        
    except Exception as e:
        print(f"❌ Error reading KB1: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """
    Main function to read and display KB1 entries.
    """
    await read_kb1_entries()

if __name__ == "__main__":
    asyncio.run(main())