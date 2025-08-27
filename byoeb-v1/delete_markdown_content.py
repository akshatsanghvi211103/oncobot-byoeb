"""
Script to delete existing markdown content from Azure Search index
"""
import asyncio
from azure.identity import AzureCliCredential
from azure.search.documents import SearchClient

# Configuration
INDEX_NAME = "oncobot_index"
SEARCH_SERVICE = "byoeb-search"

async def delete_markdown_content():
    """Delete all markdown content from the search index"""
    search_endpoint = f"https://{SEARCH_SERVICE}.search.windows.net"
    credential = AzureCliCredential()
    search_client = SearchClient(endpoint=search_endpoint, index_name=INDEX_NAME, credential=credential)
    
    print("Searching for markdown content to delete...")
    
    # Find all documents with markdown source
    results = search_client.search(
        search_text="*",
        filter="source eq 'markdown_knowledge_base'",
        select=['id'],
        top=1000  # Get all markdown documents
    )
    
    # Collect document IDs to delete
    doc_ids = []
    for result in results:
        doc_ids.append(result['id'])
    
    print(f"Found {len(doc_ids)} markdown documents to delete")
    
    if doc_ids:
        # Delete documents
        delete_docs = [{'id': doc_id} for doc_id in doc_ids]
        
        try:
            result = search_client.delete_documents(documents=delete_docs)
            print(f"Deleted {len(delete_docs)} markdown documents")
            
            # Check results
            for res in result:
                if not res.succeeded:
                    print(f"Failed to delete document {res.key}: {res.error_message}")
                    
        except Exception as e:
            print(f"Error deleting documents: {e}")
    else:
        print("No markdown documents found to delete")

if __name__ == "__main__":
    asyncio.run(delete_markdown_content())
