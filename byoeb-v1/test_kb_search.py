"""
Test script for hybrid search across all knowledge bases in Azure Search
- KB1: Q&A pairs (234 entries with source='oncobot_knowledge_base')
- KB2 & KB3: Markdown sections (64 entries with source='markdown_knowledge_base')
Uses hybrid search with 60% vector search weight and 40% text search weight
"""
import asyncio
from azure.identity import AzureCliCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from openai import AsyncAzureOpenAI

SEARCH_SERVICE = "byoeb-search"
INDEX_NAME = "oncobot_index"

def setup_trapi_embedding_client():
    """Setup TRAPI embedding client using proper endpoint"""
    scope = "api://trapi/.default"
    credential = get_bearer_token_provider(
        AzureCliCredential(),
        scope,
    )
    
    api_version = '2024-12-01-preview'
    instance = 'gcr/shared'
    embedding_deployment_name = 'text-embedding-3-large_1'
    embedding_endpoint = f'https://trapi.research.microsoft.com/{instance}/openai/deployments/{embedding_deployment_name}'
    
    token = credential()
    return AsyncAzureOpenAI(
        api_key=token,
        base_url=embedding_endpoint,
        api_version=api_version,
    )

async def get_query_embedding(client, query_text):
    """Get embedding for query using TRAPI"""
    try:
        response = await client.embeddings.create(
            model="text-embedding-3-large",
            input=query_text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return None

def setup_search_client():
    search_endpoint = f"https://{SEARCH_SERVICE}.search.windows.net"
    credential = AzureCliCredential()
    return SearchClient(endpoint=search_endpoint, index_name=INDEX_NAME, credential=credential)

async def hybrid_search_all_kbs(search_client, trapi_client, query, qa_top=3, md_top=3, search_mode="hybrid"):
    """
    Perform search across all knowledge bases with different modes
    search_mode options:
    - "vector": 100% vector search
    - "hybrid": 50% vector + 50% text search  
    - "text": 100% text search
    """
    try:
        if search_mode == "text":
            # Pure text search
            return await text_search_fallback(search_client, query, qa_top, md_top)
        
        # Get query embedding for vector or hybrid search
        query_embedding = await get_query_embedding(trapi_client, query)
        if not query_embedding:
            print("Failed to get query embedding, falling back to text search only")
            return await text_search_fallback(search_client, query, qa_top, md_top)
        
        # Create vectorized query with different weights based on mode
        if search_mode == "vector":
            # 100% vector search - no text component
            vector_query = VectorizedQuery(
                vector=query_embedding,
                k_nearest_neighbors=10,
                fields="text_vector_3072",
                weight=1.0  # Full weight to vector search
            )
            search_text = None  # No text search component
        else:  # hybrid mode
            # NOTE: Azure Search uses Reciprocal Rank Fusion (RRF), not simple weighted average
            # The weight parameter influences ranking combination, not direct score mixing
            # Scores are normalized internally using RRF algorithm
            vector_query = VectorizedQuery(
                vector=query_embedding,
                k_nearest_neighbors=10,
                fields="text_vector_3072",
                weight=0.5  # 50% influence in RRF ranking fusion
            )
            search_text = query
        
        # Search Q&A pairs
        qa_results = []
        qa_search = search_client.search(
            search_text=search_text,
            vector_queries=[vector_query],
            top=qa_top,
            filter="source eq 'oncobot_knowledge_base'",
            select=['question', 'answer', 'category', 'question_number', 'combined_text']
        )
        
        for result in qa_search:
            qa_results.append({
                'type': 'Q&A Pair',
                'question_number': result.get('question_number', 0),
                'question': result.get('question', ''),
                'answer': result.get('answer', ''),
                'category': result.get('category', ''),
                'score': result.get('@search.score', 0),
                'search_type': search_mode
            })
        
        # Search markdown sections
        md_results = []
        md_search = search_client.search(
            search_text=search_text,
            vector_queries=[vector_query],
            top=md_top,
            filter="source eq 'markdown_knowledge_base'",
            select=['question', 'answer', 'category', 'question_number', 'combined_text']
        )
        
        for result in md_search:
            md_results.append({
                'type': 'Markdown Section',
                'section_headers': result.get('question', ''),  # Headers stored in 'question' field
                'content': result.get('answer', ''),           # Content stored in 'answer' field
                'category': result.get('category', ''),
                'score': result.get('@search.score', 0),
                'search_type': search_mode
            })
            
        return qa_results, md_results
        
    except Exception as e:
        print(f"Error in {search_mode} search: {e}")
        print("Falling back to text search...")
        return await text_search_fallback(search_client, query, qa_top, md_top)

async def text_search_fallback(search_client, query, qa_top=3, md_top=3):
    """Fallback to text-only search if hybrid search fails"""
    qa_results = search_qa_pairs(search_client, query, qa_top)
    md_results = search_markdown_sections(search_client, query, md_top)
    
    # Mark as text search
    for result in qa_results:
        result['search_type'] = 'text_only'
    for result in md_results:
        result['search_type'] = 'text_only'
        
    return qa_results, md_results

def search_qa_pairs(search_client, query, top=3):
    """Search Q&A pairs from original knowledge base (text-only fallback)"""
    try:
        results = search_client.search(
            search_text=query,
            top=top,
            filter="source eq 'oncobot_knowledge_base'",
            select=['question', 'answer', 'category', 'question_number', 'combined_text'],
            order_by=['search.score() desc']
        )
        
        qa_results = []
        for result in results:
            qa_results.append({
                'type': 'Q&A Pair',
                'question_number': result.get('question_number', 0),
                'question': result.get('question', ''),
                'answer': result.get('answer', ''),
                'category': result.get('category', ''),
                'score': result.get('@search.score', 0),
                'search_type': 'text_only'
            })
        return qa_results
    except Exception as e:
        print(f"Error searching Q&A pairs: {e}")
        return []

def search_markdown_sections(search_client, query, top=3):
    """Search markdown sections from KB2 and KB3 (text-only fallback)"""
    try:
        results = search_client.search(
            search_text=query,
            top=top,
            filter="source eq 'markdown_knowledge_base'",
            select=['question', 'answer', 'category', 'question_number', 'combined_text'],
            order_by=['search.score() desc']
        )
        
        md_results = []
        for result in results:
            md_results.append({
                'type': 'Markdown Section',
                'section_headers': result.get('question', ''),  # Headers stored in 'question' field
                'content': result.get('answer', ''),           # Content stored in 'answer' field
                'category': result.get('category', ''),
                'score': result.get('@search.score', 0),
                'search_type': 'text_only'
            })
        return md_results
    except Exception as e:
        print(f"Error searching markdown sections: {e}")
        return []

def format_results(qa_results, md_results, query, search_mode):
    """Format and display search results with scoring explanation"""
    
    # Get search mode display info
    mode_info = {
        "vector": ("100% VECTOR SEARCH", "🔍V", "Pure cosine similarity (0.0-1.0 range)"),
        "hybrid": ("HYBRID SEARCH (RRF)", "🔍H", "Reciprocal Rank Fusion: combines rankings, not raw scores"),
        "text": ("100% TEXT SEARCH", "🔍T", "Pure BM25 algorithm (0.0-20+ range)")
    }
    
    mode_display, icon, scoring_desc = mode_info.get(search_mode, ("UNKNOWN", "🔍?", "Unknown scoring"))
    
    print(f"\n{'='*80}")
    print(f"SEARCH QUERY: '{query}'")
    print(f"MODE: {mode_display}")
    print(f"SCORING: {scoring_desc}")
    print(f"{'='*80}")
    
    print(f"\n📋 TOP Q&A PAIRS FROM ORIGINAL KNOWLEDGE BASE:")
    print("-" * 60)
    if qa_results:
        for i, result in enumerate(qa_results, 1):
            print(f"\n{i}. {icon} Q{result['question_number']} (Score: {result['score']:.4f})")
            print(f"   Category: {result['category']}")
            print(f"   Question: {result['question']}")
            print(f"   Answer: {result['answer'][:200]}{'...' if len(result['answer']) > 200 else ''}")
    else:
        print("   No Q&A pairs found for this query.")
    
    print(f"\n📄 TOP MARKDOWN SECTIONS FROM KB2 & KB3:")
    print("-" * 60)
    if md_results:
        for i, result in enumerate(md_results, 1):
            print(f"\n{i}. {icon} Markdown Section (Score: {result['score']:.4f})")
            print(f"   Headers: {result['section_headers']}")
            print(f"   Content: {result['content'][:200]}{'...' if len(result['content']) > 200 else ''}")
    else:
        print("   No markdown sections found for this query.")
        
    # Add scoring explanation
    print(f"\n📊 SCORING EXPLANATION:")
    print(f"   • Higher scores = more relevant")
    if search_mode == "vector":
        print(f"   • Vector scores: Cosine similarity (0.0-1.0 range)")
        print(f"   • Measures semantic meaning and concept similarity")
        print(f"   • Example: 0.69 = very similar, 0.30 = somewhat similar")
    elif search_mode == "text":
        print(f"   • Text scores: BM25 algorithm (0.0-20+ range)")
        print(f"   • Based on: term frequency × inverse document frequency × field length")
        print(f"   • Example: 15.96 = high keyword relevance, 6.28 = moderate relevance")
    else:  # hybrid
        print(f"   • Hybrid scores: Reciprocal Rank Fusion (RRF) - NOT simple average!")
        print(f"   • Step 1: Get separate rankings from vector and text search")
        print(f"   • Step 2: Combine rankings using RRF formula: 1/(rank + 60)")
        print(f"   • Step 3: Final score is normalized fusion score (much lower range)")
        print(f"   • Different scale because it's ranking fusion, not score mixing")

async def interactive_hybrid_search(search_client, trapi_client):
    """Interactive search with multiple modes - user can input any question"""
    print("🔍 INTERACTIVE MULTI-MODE SEARCH")
    print("=" * 80)
    print("Available Search Modes:")
    print("  1. 🔍V VECTOR (100% semantic similarity)")
    print("  2. 🔍H HYBRID (50% semantic + 50% keyword)")  
    print("  3. 🔍T TEXT (100% keyword matching)")
    print("\nKnowledge Bases:")
    print("  • KB1: Q&A Pairs (Original Knowledge Base)")
    print("  • KB2 & KB3: Markdown Sections (Radiation Therapy Guides)")
    print("  • Embeddings: TRAPI text-embedding-3-large (3072 dimensions)")
    print("\nCommands: 'quit'/'exit' to stop, 'mode' to change search mode")
    
    current_mode = "hybrid"  # Default mode
    
    while True:
        print(f"\n{'='*80}")
        print(f"Current Mode: {current_mode.upper()}")
        user_input = input("🤔 Enter your question (or 'mode' to change search mode): ").strip()
        
        if user_input.lower() in ['quit', 'exit', '']:
            print("👋 Goodbye!")
            break
            
        if user_input.lower() == 'mode':
            print(f"\nSelect search mode:")
            print("1. Vector (100% semantic)")
            print("2. Hybrid (50% semantic + 50% keyword)")
            print("3. Text (100% keyword)")
            
            mode_choice = input("Enter choice (1-3): ").strip()
            mode_map = {'1': 'vector', '2': 'hybrid', '3': 'text'}
            
            if mode_choice in mode_map:
                current_mode = mode_map[mode_choice]
                print(f"✅ Mode changed to: {current_mode.upper()}")
            else:
                print("❌ Invalid choice, keeping current mode")
            continue
            
        print(f"\n🔍 Searching for: '{user_input}' (Mode: {current_mode.upper()})")
        print("-" * 60)
        
        # Perform search with selected mode
        qa_results, md_results = await hybrid_search_all_kbs(
            search_client, trapi_client, user_input, qa_top=3, md_top=3, search_mode=current_mode
        )
        
        # Format and display results
        format_results(qa_results, md_results, user_input, current_mode)
        
        print(f"\n{'='*60}")
        continue_search = input("🔄 Search another question? (Enter to continue, 'q' to quit, 'mode' to change mode): ").strip()
        if continue_search.lower() in ['q', 'quit', 'exit']:
            print("👋 Goodbye!")
            break
        elif continue_search.lower() == 'mode':
            print(f"\nSelect search mode:")
            print("1. Vector (100% semantic)")
            print("2. Hybrid (50% semantic + 50% keyword)")
            print("3. Text (100% keyword)")
            
            mode_choice = input("Enter choice (1-3): ").strip()
            mode_map = {'1': 'vector', '2': 'hybrid', '3': 'text'}
            
            if mode_choice in mode_map:
                current_mode = mode_map[mode_choice]
                print(f"✅ Mode changed to: {current_mode.upper()}")
            else:
                print("❌ Invalid choice, keeping current mode")

def get_index_stats(search_client):
    """Get statistics about the index"""
    try:
        print("📊 INDEX STATISTICS:")
        print("-" * 40)
        
        # Count Q&A pairs
        qa_count = search_client.search(
            search_text="*",
            filter="source eq 'oncobot_knowledge_base'",
            include_total_count=True,
            top=0
        )
        print(f"Q&A Pairs (KB1): {qa_count.get_count()} entries")
        
        # Count markdown sections
        md_count = search_client.search(
            search_text="*",
            filter="source eq 'markdown_knowledge_base'",
            include_total_count=True,
            top=0
        )
        print(f"Markdown Sections (KB2 & KB3): {md_count.get_count()} entries")
        
        # Total count
        total_count = search_client.search(
            search_text="*",
            include_total_count=True,
            top=0
        )
        print(f"Total Index Entries: {total_count.get_count()}")
        
    except Exception as e:
        print(f"Error getting index statistics: {e}")

async def main():
    print("🏥 ONCOLOGY KNOWLEDGE BASE HYBRID SEARCH TESTER")
    print("=" * 55)
    
    # Setup clients
    search_client = setup_search_client()
    trapi_client = setup_trapi_embedding_client()
    
    try:
        # Get index statistics
        get_index_stats(search_client)
        
        print(f"\n🧪 INTERACTIVE MULTI-MODE SEARCH")
        print("Features:")
        print("- 🔍V Vector Search: 100% semantic similarity (embeddings)")
        print("- 🔍H Hybrid Search: 50% semantic + 50% keyword matching")
        print("- 🔍T Text Search: 100% keyword matching (BM25)")
        print("- Search across all 3 knowledge bases simultaneously")
        print("- Top 3 results from Q&A pairs + Top 3 from markdown sections")
        print("- Real-time mode switching and detailed scoring explanations")
        
        input(f"\nPress Enter to start interactive search...")
        
        # Start interactive search mode
        await interactive_hybrid_search(search_client, trapi_client)
        
        print("\n✅ HYBRID SEARCH SESSION COMPLETED!")
        print("Thank you for testing the oncology knowledge base!")
        
    finally:
        await trapi_client.close()

if __name__ == "__main__":
    asyncio.run(main())
