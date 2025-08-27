import re
import os
import asyncio
from azure.identity import AzureCliCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import SearchField, SearchFieldDataType
from openai import AsyncAzureOpenAI

SEARCH_SERVICE = "byoeb-search"
INDEX_NAME = "oncobot_index"
AZURE_OPENAI_ENDPOINT = "https://swasthyabot-oai.openai.azure.com/"

# Initialize TRAPI embedding client
def setup_trapi_embedding_client():
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

async def get_embedding(text, embedding_client):
    """Get embedding using TRAPI text-embedding-3-large_1."""
    try:
        response = await embedding_client.embeddings.create(
            model="text-embedding-3-large",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return None

# Helper: Chunk markdown by headers, including all parent headers in each chunk

def chunk_markdown(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    chunks = []
    header_stack = []
    current_chunk = []
    current_headers = []

    for line in lines:
        header_match = re.match(r'^(#+)\s+(.*)', line)
        if header_match:
            # Save previous chunk
            if current_chunk:
                chunks.append({
                    'headers': ' > '.join(current_headers),
                    'text': ''.join(current_chunk).strip()
                })
                current_chunk = []
            # Update header stack
            level = len(header_match.group(1))
            header = header_match.group(2).strip()
            current_headers = current_headers[:level-1] + [header]
        else:
            current_chunk.append(line)

    # Add last chunk
    if current_chunk:
        chunks.append({
            'headers': ' > '.join(current_headers),
            'text': ''.join(current_chunk).strip()
        })

    # Remove empty chunks
    return [chunk for chunk in chunks if chunk['text']]

# Upload chunks to Azure Search

async def upload_chunks_to_azure(chunks, file_name, index_name, search_service):
    search_endpoint = f"https://{search_service}.search.windows.net"
    credential = AzureCliCredential()
    search_client = SearchClient(endpoint=search_endpoint, index_name=index_name, credential=credential)
    
    # Setup embedding client
    embedding_client = setup_trapi_embedding_client()
    
    # Create unique source identifier based on filename
    if 'knowledge_base_2' in file_name:
        source_id = 'kb2_content'
        file_prefix = 'kb2'
    elif 'knowledge_base_3' in file_name:
        source_id = 'kb3_content'
        file_prefix = 'kb3'
    else:
        source_id = 'markdown_knowledge_base'
        file_prefix = 'md'
    
    documents = []
    for i, chunk in enumerate(chunks):
        print(f"Processing chunk {i+1}/{len(chunks)}: {chunk['headers'][:50]}...")
        
        # Generate embedding for the combined text
        combined_text = f"Section: {chunk['headers']}\nContent: {chunk['text']}"
        embedding = await get_embedding(combined_text, embedding_client)
        
        if embedding:
            document = {
                'id': f'{file_prefix}_chunk_{i+1}',  # Unique ID with file prefix
                'question': chunk['headers'],  # Use headers as question field
                'answer': chunk['text'],       # Use text as answer field
                'category': 'markdown_section',
                'question_number': i + 1,
                'combined_text': combined_text,
                'source': source_id,  # Unique source for each file
                'text_vector_3072': embedding
            }
            documents.append(document)
        else:
            print(f"Skipping chunk {i+1} due to embedding error")
    
    # Upload documents in batches
    batch_size = 50
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        try:
            result = search_client.upload_documents(documents=batch)
            print(f"Uploaded batch {i//batch_size + 1}: {len(batch)} documents for {file_name}")
        except Exception as e:
            print(f"Error uploading batch {i//batch_size + 1} for {file_name}: {e}")
    
    print(f"Successfully uploaded {len(documents)} chunks for {file_name} with source '{source_id}'")

async def main():
    kb_files = ['knowledge_base_2.md', 'knowledge_base_3.md']
    for kb_file in kb_files:
        chunks = chunk_markdown(kb_file)
        print(f"File: {kb_file}, Chunks: {len(chunks)}")
        await upload_chunks_to_azure(chunks, kb_file, INDEX_NAME, SEARCH_SERVICE)

if __name__ == "__main__":
    asyncio.run(main())
