#!/usr/bin/env python3
"""
Quick test to verify knowledge base search integration is working
"""
import asyncio
import sys
import os

# Add the byoeb directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'byoeb'))

async def test_knowledge_base_search():
    """Test that knowledge base search is working properly"""
    try:
        print("🔍 Testing knowledge base search integration...")
        
        # Import the vector store from dependency setup
        from byoeb.chat_app.configuration.dependency_setup import vector_store
        print(f"✅ Vector store loaded: {type(vector_store).__name__}")
        
        # Test a sample search
        test_query = "cancer treatment"
        print(f"🔎 Searching for: '{test_query}'")
        
        chunks = await vector_store.aretrieve_top_k_chunks(
            test_query,
            k=3,
            search_type="dense",
            select=["id", "combined_text", "source", "question", "answer"],
            vector_field="text_vector_3072"
        )
        
        print(f"✅ Found {len(chunks)} chunks")
        
        if chunks:
            print("\n📋 Sample results:")
            for i, chunk in enumerate(chunks[:2]):  # Show first 2 chunks
                print(f"\nChunk {i+1}:")
                print(f"  ID: {chunk.chunk_id}")
                print(f"  Text: {chunk.text[:200]}..." if len(chunk.text) > 200 else f"  Text: {chunk.text}")
                if hasattr(chunk, 'metadata') and chunk.metadata:
                    print(f"  Source: {getattr(chunk.metadata, 'source', 'Unknown')}")
        
        return len(chunks) > 0
        
    except Exception as e:
        print(f"❌ Error testing knowledge base: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    success = await test_knowledge_base_search()
    
    if success:
        print("\n🎉 Knowledge base search is working correctly!")
        print("✅ KB1 (Q&A pairs), KB2 and KB3 (markdown files) should be accessible")
    else:
        print("\n⚠️ Knowledge base search test failed")
        print("❌ Please check KB upload and Azure Vector Search configuration")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
