"""
Fixed script to upload KB2 and KB3 markdown content to Azure Search
Creates unique IDs for each file to prevent overwrites
"""
import asyncio
import re
import os
from typing import List, Dict
from azure.identity import AzureCliCredential
from azure.search.documents import SearchClient
from openai import AsyncAzureOpenAI

# Configuration
INDEX_NAME = "oncobot_index"
SEARCH_SERVICE = "byoeb-search"
AZURE_OPENAI_ENDPOINT = "https://swasthyabot-oai.openai.azure.com/"

def setup_trapi_embedding_client():
    credential = AzureCliCredential()
    
    from azure.identity import get_bearer_token_provider
    token_provider = get_bearer_token_provider(
        credential, 'https://cognitiveservices.azure.com/.default'
    )
    
    return AsyncAzureOpenAI(
        api_version="2023-12-01-preview",
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        azure_ad_token_provider=token_provider
    )

async def get_embedding(text, client):
    try:
        response = await client.embeddings.create(
            model="text-embedding-3-large",
            input=text,
            dimensions=3072
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return None

def chunk_markdown(file_path):
    """Chunk markdown by headers, including all parent headers in each chunk"""
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

async def upload_chunks_to_azure(chunks, file_name, index_name, search_service):
    """Upload chunks to Azure Search with unique IDs based on filename"""
    search_endpoint = f"https://{search_service}.search.windows.net"
    credential = AzureCliCredential()
    search_client = SearchClient(endpoint=search_endpoint, index_name=index_name, credential=credential)
    
    # Setup embedding client
    embedding_client = setup_trapi_embedding_client()
    
    # Get base filename without extension
    base_name = os.path.splitext(file_name)[0]
    source_name = f"{base_name}_content"
    
    documents = []
    for i, chunk in enumerate(chunks):
        print(f"Processing chunk {i+1}/{len(chunks)}: {chunk['headers'][:50]}...")
        
        # Generate embedding for the combined text
        combined_text = f"Section: {chunk['headers']}\nContent: {chunk['text']}"
        embedding = await get_embedding(combined_text, embedding_client)
        
        if embedding:
            document = {
                'id': f'{base_name}_chunk_{i+1}',  # Unique ID based on filename
                'question': chunk['headers'],  # Use headers as question field
                'answer': chunk['text'],       # Use text as answer field
                'category': 'markdown_section',
                'question_number': i + 1,
                'combined_text': combined_text,
                'source': source_name,  # Unique source for each file
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
    
    print(f"Successfully uploaded {len(documents)} chunks for {file_name} with source '{source_name}'")

async def main():
    kb_files = ['knowledge_base_2.md', 'knowledge_base_3.md']
    for kb_file in kb_files:
        if os.path.exists(kb_file):
            chunks = chunk_markdown(kb_file)
            print(f"File: {kb_file}, Chunks: {len(chunks)}")
            await upload_chunks_to_azure(chunks, kb_file, INDEX_NAME, SEARCH_SERVICE)
        else:
            print(f"File not found: {kb_file}")

if __name__ == "__main__":
    asyncio.run(main())
