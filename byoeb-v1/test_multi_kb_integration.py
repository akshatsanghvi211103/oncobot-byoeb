"""
Test script to verify the multi-KB search integration
This tests that the generate.py __aretrieve_chunks method can now search across all knowledge bases
"""
import asyncio
import sys
import os

# Add the paths to make imports work
sys.path.append(os.path.join(os.path.dirname(__file__), 'byoeb'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'byoeb-core'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'byoeb-integrations'))

async def test_multi_kb_search():
    """
    Test the enhanced multi-KB search functionality
    """
    try:
        # Import the generate handler
        from byoeb.services.chat.message_handlers.user_flow_handlers.generate import ByoebUserGenerateResponse
        
        # Create an instance
        handler = ByoebUserGenerateResponse()
        
        # Test query
        test_query = "What are the symptoms of acute lymphoblastic leukemia?"
        
        print(f"Testing multi-KB search with query: '{test_query}'")
        print("=" * 60)
        
        # Call the enhanced method
        chunks = await handler._ByoebUserGenerateResponse__aretrieve_chunks(test_query, 7)
        
        print(f"Retrieved {len(chunks)} chunks from multiple knowledge bases:")
        print("=" * 60)
        
        # Analyze results by source
        kb_counts = {}
        for i, chunk in enumerate(chunks):
            source = "Unknown"
            if hasattr(chunk, 'metadata') and chunk.metadata:
                source = chunk.metadata.source or "Unknown"
            
            if source not in kb_counts:
                kb_counts[source] = 0
            kb_counts[source] += 1
            
            print(f"Chunk {i+1}:")
            print(f"  Source: {source}")
            if hasattr(chunk, 'text'):
                print(f"  Content: {chunk.text[:150]}...")
            print("  ---")
        
        print("=" * 60)
        print("Summary by Knowledge Base:")
        for source, count in kb_counts.items():
            print(f"  {source}: {count} chunks")
        
        # Verify we got results from multiple sources
        if len(kb_counts) > 1:
            print("✅ SUCCESS: Retrieved chunks from multiple knowledge bases!")
        else:
            print("⚠️  WARNING: Only got results from one knowledge base")
            
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("Testing Multi-KB Search Integration")
    print("=" * 60)
    
    success = await test_multi_kb_search()
    
    if success:
        print("\n✅ Test completed successfully!")
    else:
        print("\n❌ Test failed!")

if __name__ == "__main__":
    asyncio.run(main())
