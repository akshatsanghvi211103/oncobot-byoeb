#!/usr/bin/env python3
"""
Test that the generate handler is accessing all knowledge bases (KB1, KB2, KB3)
"""
import asyncio
import sys
import os

# Add the byoeb directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'byoeb'))

async def test_all_knowledge_bases():
    """Test that we can access content from all three knowledge bases"""
    try:
        print("🧪 Testing access to all knowledge bases through generate handler...")
        
        from byoeb.services.chat.message_handlers.user_flow_handlers.generate import ByoebUserGenerateResponse
        
        # Create handler instance
        handler = ByoebUserGenerateResponse()
        
        # Test questions that should hit different knowledge bases
        test_cases = [
            {
                "question": "what is cancer?",
                "expected_source": "oncobot_knowledge_base",
                "kb": "KB1 (Q&A pairs)"
            },
            {
                "question": "radiation therapy to head and neck",
                "expected_sources": ["kb3_content", "kb2_content"],
                "kb": "KB2/KB3 (Markdown files)"
            },
            {
                "question": "side effects hair loss",
                "expected_sources": ["kb2_content", "kb3_content"],
                "kb": "KB2/KB3 (Markdown files)"
            }
        ]
        
        all_sources_found = set()
        
        for test_case in test_cases:
            question = test_case["question"]
            print(f"\n🔎 Testing: '{question}' (Expected from {test_case['kb']})")
            
            chunks = await handler._ByoebUserGenerateResponse__aretrieve_chunks(question, 5)
            print(f"✅ Retrieved {len(chunks)} chunks")
            
            # Check sources
            sources_in_results = set()
            for chunk in chunks:
                if chunk.metadata and chunk.metadata.source:
                    sources_in_results.add(chunk.metadata.source)
                    all_sources_found.add(chunk.metadata.source)
            
            print(f"  Sources found: {sorted(sources_in_results)}")
            
            # Show sample results
            for i, chunk in enumerate(chunks[:2]):
                source = chunk.metadata.source if chunk.metadata else "Unknown"
                print(f"  Chunk {i+1} ({source}): {chunk.text[:80]}...")
        
        print(f"\n📊 SUMMARY:")
        print(f"All sources accessed: {sorted(all_sources_found)}")
        
        expected_sources = {"oncobot_knowledge_base", "kb2_content", "kb3_content"}
        missing_sources = expected_sources - all_sources_found
        
        if missing_sources:
            print(f"❌ Missing access to: {missing_sources}")
            return False
        else:
            print("✅ Successfully accessing all knowledge bases!")
            print("  - KB1 (oncobot_knowledge_base): Q&A pairs")
            print("  - KB2 (kb2_content): Radiation therapy guide")
            print("  - KB3 (kb3_content): Head and neck radiation therapy")
            return True
        
    except Exception as e:
        print(f"❌ Error testing knowledge bases: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_all_knowledge_bases())
    sys.exit(0 if result else 1)
