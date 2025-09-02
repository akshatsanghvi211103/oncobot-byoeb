#!/usr/bin/env python3
"""
Check all sources in the Azure Search index
"""
import asyncio
from azure.identity import AzureCliCredential
from azure.search.documents import SearchClient

async def check_all_sources():
    """Check all source types in the index"""
    try:
        client = SearchClient(
            endpoint="https://byoeb-search.search.windows.net",
            index_name="oncobot_index",
            credential=AzureCliCredential()
        )
        
        # Get all documents and check their sources
        results = client.search("*", select=["source"], top=1000)
        
        sources = {}
        total_count = 0
        
        for result in results:
            src = result.get('source', 'unknown')
            sources[src] = sources.get(src, 0) + 1
            total_count += 1
        
        print("📊 ALL SOURCES IN AZURE SEARCH INDEX:")
        print("=" * 50)
        for src, count in sorted(sources.items()):
            print(f"  {src}: {count} entries")
        
        print(f"\nTotal entries: {total_count}")
        
        # Now let's check what specific content exists for each source
        print("\n📋 SAMPLE CONTENT BY SOURCE:")
        print("=" * 50)
        
        for src in sources.keys():
            print(f"\n🔍 Sample from '{src}':")
            sample_results = client.search(
                search_text="*",
                filter=f"source eq '{src}'",
                select=["id", "question", "answer", "combined_text"],
                top=2
            )
            
            for i, sample in enumerate(sample_results):
                print(f"  Sample {i+1}:")
                print(f"    ID: {sample.get('id', 'N/A')}")
                question = sample.get('question', 'N/A')
                answer = sample.get('answer', 'N/A')
                combined = sample.get('combined_text', 'N/A')
                
                if question != 'N/A' and len(question) > 0:
                    print(f"    Question: {question[:100]}...")
                if answer != 'N/A' and len(answer) > 0:
                    print(f"    Answer: {answer[:100]}...")
                if combined != 'N/A' and len(combined) > 0:
                    print(f"    Combined: {combined[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking sources: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(check_all_sources())
