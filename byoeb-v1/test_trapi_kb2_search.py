"""
Test script to verify TRAPI message consumer can find KB2 content with new source structure
"""
import asyncio
import sys
import os

# Add the byoeb directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'byoeb'))

from byoeb.services.chat.trapi_message_consumer import TRAPIMessageConsumerService

async def test_kb2_search():
    """Test that KB2-specific content can be found"""
    
    # Create a minimal config for testing
    config = {}
    
    # Initialize the service without channel factory for testing
    service = TRAPIMessageConsumerService(config, None)
    
    # Test queries that should find KB2 content
    test_queries = [
        "What is brachytherapy?",
        "Tell me about linear accelerator",
        "What happens in the multidisciplinary tumor board?",
        "How do I do mouth washes during treatment?"
    ]
    
    for query in test_queries:
        print(f"\n=== TESTING QUERY: '{query}' ===")
        try:
            results = await service._search_knowledge_base(query, kb1_limit=2, kb2_kb3_limit=3)
            
            print(f"Found {len(results)} total results:")
            
            kb2_found = False
            for i, result in enumerate(results, 1):
                source = result.get('source', 'Unknown')
                if source == 'KB2_Markdown':
                    kb2_found = True
                    headers = result.get('section_headers', '')[:60]
                    content = result.get('content', '')[:100]
                    score = result.get('score', 0)
                    print(f"  {i}. 🎯 {source}: {headers}...")
                    print(f"     Content: {content}...")
                    print(f"     Score: {score:.3f}")
                elif source == 'KB1_QA':
                    question = result.get('question', '')[:60]
                    score = result.get('score', 0)
                    print(f"  {i}. 📝 {source}: {question}...")
                    print(f"     Score: {score:.3f}")
                elif source == 'KB3_Markdown':
                    headers = result.get('section_headers', '')[:60]
                    score = result.get('score', 0)
                    print(f"  {i}. 📖 {source}: {headers}...")
                    print(f"     Score: {score:.3f}")
            
            if kb2_found:
                print("  ✅ KB2 content found!")
            else:
                print("  ❌ No KB2 content found")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_kb2_search())
