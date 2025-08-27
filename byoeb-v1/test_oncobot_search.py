"""
Test Azure Search text search with oncobot index
"""
import asyncio
from azure.identity import AzureCliCredential
from azure.search.documents import SearchClient

async def test_oncobot_search():
    print("=== Testing Oncobot Index Text Search ===")
    
    try:
        credential = AzureCliCredential()
        search_endpoint = "https://byoeb-search.search.windows.net"
        
        search_client = SearchClient(
            endpoint=search_endpoint,
            index_name='oncobot_index',
            credential=credential
        )
        
        # Test queries
        test_queries = [
            "What is cancer",
            "side effects of radiotherapy", 
            "How many sessions",
            "oral cancer causes"
        ]
        
        for query in test_queries:
            print(f"\n=== SEARCHING: {query} ===")
            
            results = search_client.search(
                search_text=query,
                top=3,
                include_total_count=True,
                select=['question', 'answer', 'category', 'question_number']
            )
            
            found_any = False
            for result in results:
                found_any = True
                print(f"Q{result.get('question_number', '?')}: {result.get('question', '')[:60]}...")
                print(f"Answer: {result.get('answer', '')[:100]}...")
                print(f"Category: {result.get('category', '')}")
                print("---")
            
            if not found_any:
                print("No results found")
    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_oncobot_search())
