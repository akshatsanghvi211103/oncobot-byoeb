"""
Test script to verify TRAPI integration works with O3 and embeddings
"""
import asyncio
from openai import AsyncAzureOpenAI
from azure.identity import ChainedTokenCredential, AzureCliCredential, ManagedIdentityCredential, get_bearer_token_provider

async def test_trapi_setup():
    print("=== Testing TRAPI Setup ===")
    
    # Setup TRAPI credentials
    scope = "api://trapi/.default"
    credential = get_bearer_token_provider(
        ChainedTokenCredential(
            AzureCliCredential(),
            ManagedIdentityCredential(),
        ),
        scope,
    )
    
    api_version = '2024-12-01-preview'
    instance = 'gcr/shared'
    
    # Setup O3 client
    o3_deployment_name = 'o3_2025-04-16'
    o3_endpoint = f'https://trapi.research.microsoft.com/{instance}/openai/deployments/{o3_deployment_name}'
    
    token = credential()
    o3_client = AsyncAzureOpenAI(
        api_key=token,
        base_url=o3_endpoint,
        api_version=api_version,
    )
    
    print("✅ O3 client initialized")
    
    # Test O3 with direct calls
    try:
        response = await o3_client.chat.completions.create(
            model="o3",
            messages=[
                {"role": "system", "content": "You are a helpful oncology assistant"},
                {"role": "user", "content": "What is cancer in simple terms?"}
            ],
            max_completion_tokens=200  # O3 doesn't support temperature parameter
        )
        o3_response = response.choices[0].message.content
        print(f"✅ O3 Response: {o3_response[:100]}...")
    except Exception as e:
        print(f"❌ O3 Error: {e}")
    
    # Setup embedding client
    embedding_deployment_name = 'text-embedding-3-large_1'
    embedding_endpoint = f'https://trapi.research.microsoft.com/{instance}/openai/deployments/{embedding_deployment_name}'
    
    embedding_client = AsyncAzureOpenAI(
        api_key=token,
        base_url=embedding_endpoint,
        api_version=api_version,
    )
    
    print("✅ Embedding client initialized")
    
    # Test embeddings
    try:
        response = await embedding_client.embeddings.create(
            model="text-embedding-3-large",
            input="What is cancer?"
        )
        embedding = response.data[0].embedding
        print(f"✅ Embedding generated: {len(embedding)} dimensions")
        print(f"Sample values: {embedding[:5]}")
    except Exception as e:
        print(f"❌ Embedding Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_trapi_setup())
