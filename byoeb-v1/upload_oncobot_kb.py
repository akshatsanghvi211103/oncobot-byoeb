"""
Script to upload the oncobot knowledge base to Azure Search
Creates a new index called 'oncobot_index' with the Q&A pairs
"""
import asyncio
import re
from typing import List, Dict
from azure.identity import AzureCliCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    VectorSearchProfile,
    VectorSearchAlgorithmKind,
    VectorSearchAlgorithmMetric,
    HnswAlgorithmConfiguration,
    SemanticConfiguration,
    SemanticPrioritizedFields,
    SemanticField,
    SemanticSearch
)
from byoeb_integrations.embeddings.llama_index.azure_openai import AzureOpenAIEmbed

# Azure configuration
SEARCH_SERVICE = "byoeb-search"
INDEX_NAME = "oncobot_index"
AZURE_OPENAI_ENDPOINT = "https://swasthyabot-oai.openai.azure.com/"

class OncobotKnowledgeUploader:
    def __init__(self):
        self.credential = AzureCliCredential()
        self.token_provider = get_bearer_token_provider(
            self.credential, 
            'https://cognitiveservices.azure.com/.default'
        )
        
        # Initialize embedding client
        self.azure_openai_embed = AzureOpenAIEmbed(
            model='text-embedding-3-large',
            deployment_name='text-embedding-3-large',
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            token_provider=self.token_provider,
            api_version='2023-03-15-preview'
        )
        
        # Initialize search clients
        search_endpoint = f"https://{SEARCH_SERVICE}.search.windows.net"
        self.index_client = SearchIndexClient(
            endpoint=search_endpoint,
            credential=self.credential
        )
        self.search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=INDEX_NAME,
            credential=self.credential
        )

    def parse_knowledge_base(self, file_path: str) -> List[Dict]:
        """Parse the knowledge_base.txt file into structured Q&A pairs"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split by Q patterns
        qa_pairs = []
        sections = re.split(r'\n(?=Q\d+)', content)
        
        for section in sections:
            if not section.strip():
                continue
                
            lines = section.strip().split('\n')
            if len(lines) < 2:
                continue
                
            # Extract question
            q_line = lines[0]
            q_match = re.match(r'Q(\d+)\s*\(Category:\s*([^)]+)\):\s*(.+)', q_line)
            if not q_match:
                continue
                
            q_number = q_match.group(1)
            category = q_match.group(2).strip()
            question = q_match.group(3).strip()
            
            # Extract answer
            answer_lines = []
            for line in lines[1:]:
                if line.startswith('A' + q_number + ':'):
                    answer_lines.append(line[len('A' + q_number + ':'):].strip())
                elif not line.startswith('Q') and answer_lines:
                    answer_lines.append(line.strip())
                elif line.startswith('Q'):
                    break
            
            answer = ' '.join(answer_lines).strip()
            
            if question and answer:
                qa_pairs.append({
                    'id': f"oncobot_qa_{q_number}",
                    'question': question,
                    'answer': answer,
                    'category': category,
                    'question_number': int(q_number),
                    'combined_text': f"Question: {question}\nAnswer: {answer}",
                    'source': 'oncobot_knowledge_base'
                })
        
        return qa_pairs

    async def create_index(self):
        """Create the oncobot search index"""
        print(f"Creating index: {INDEX_NAME}")
        
        # Define the search index
        fields = [
            SearchField(name="id", type=SearchFieldDataType.String, key=True),
            SearchField(name="question", type=SearchFieldDataType.String, searchable=True),
            SearchField(name="answer", type=SearchFieldDataType.String, searchable=True),
            SearchField(name="category", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SearchField(name="question_number", type=SearchFieldDataType.Int32, sortable=True),
            SearchField(name="combined_text", type=SearchFieldDataType.String, searchable=True),
            SearchField(name="source", type=SearchFieldDataType.String, filterable=True),
            SearchField(
                name="text_vector_3072",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=3072,
                vector_search_profile_name="oncobot_vector_profile"
            )
        ]
        
        # Configure vector search
        vector_search = VectorSearch(
            profiles=[
                VectorSearchProfile(
                    name="oncobot_vector_profile",
                    algorithm_configuration_name="oncobot_hnsw_config"
                )
            ],
            algorithms=[
                HnswAlgorithmConfiguration(
                    name="oncobot_hnsw_config",
                    kind=VectorSearchAlgorithmKind.HNSW,
                    parameters={
                        "metric": VectorSearchAlgorithmMetric.COSINE,
                        "m": 4,
                        "efConstruction": 400,
                        "efSearch": 500
                    }
                )
            ]
        )
        
        # Configure semantic search
        semantic_config = SemanticConfiguration(
            name="oncobot_semantic_config",
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="question"),
                content_fields=[
                    SemanticField(field_name="answer"),
                    SemanticField(field_name="combined_text")
                ],
                keywords_fields=[
                    SemanticField(field_name="category")
                ]
            )
        )
        
        semantic_search = SemanticSearch(
            configurations=[semantic_config]
        )
        
        # Create the index
        index = SearchIndex(
            name=INDEX_NAME,
            fields=fields,
            vector_search=vector_search,
            semantic_search=semantic_search
        )
        
        try:
            result = self.index_client.create_index(index)
            print(f"Index '{INDEX_NAME}' created successfully")
            return True
        except Exception as e:
            if "already exists" in str(e):
                print(f"Index '{INDEX_NAME}' already exists")
                return True
            else:
                print(f"Error creating index: {e}")
                return False

    async def upload_documents(self, qa_pairs: List[Dict]):
        """Upload Q&A pairs to the search index with embeddings"""
        print(f"Uploading {len(qa_pairs)} Q&A pairs...")
        
        # Generate embeddings for each Q&A pair
        embedding_function = self.azure_openai_embed.get_embedding_function()
        
        documents = []
        for i, qa in enumerate(qa_pairs):
            print(f"Processing Q&A {i+1}/{len(qa_pairs)}: Q{qa['question_number']}")
            
            # Generate embedding for the combined text
            try:
                embedding = await embedding_function.aget_text_embedding(qa['combined_text'])
                
                document = {
                    'id': qa['id'],
                    'question': qa['question'],
                    'answer': qa['answer'],
                    'category': qa['category'],
                    'question_number': qa['question_number'],
                    'combined_text': qa['combined_text'],
                    'source': qa['source'],
                    'text_vector_3072': embedding
                }
                documents.append(document)
                
            except Exception as e:
                print(f"Error generating embedding for Q{qa['question_number']}: {e}")
                continue
        
        # Upload documents in batches
        batch_size = 50
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            try:
                result = self.search_client.upload_documents(documents=batch)
                print(f"Uploaded batch {i//batch_size + 1}: {len(batch)} documents")
            except Exception as e:
                print(f"Error uploading batch {i//batch_size + 1}: {e}")
        
        print(f"Successfully uploaded {len(documents)} Q&A pairs to index '{INDEX_NAME}'")

    async def test_search(self):
        """Test the search functionality"""
        print("\n=== Testing Search ===")
        
        test_queries = [
            "What is cancer?",
            "side effects of radiotherapy",
            "How many sessions of treatment?",
            "oral cancer causes"
        ]
        
        for query in test_queries:
            print(f"\nSearching for: '{query}'")
            try:
                results = self.search_client.search(
                    search_text=query,
                    top=3,
                    include_total_count=True
                )
                
                for result in results:
                    print(f"Q{result['question_number']}: {result['question'][:100]}...")
                    print(f"Answer: {result['answer'][:150]}...")
                    print("---")
                    
            except Exception as e:
                print(f"Search error: {e}")

async def main():
    uploader = OncobotKnowledgeUploader()
    
    # Parse the knowledge base file
    print("Parsing knowledge_base.txt...")
    qa_pairs = uploader.parse_knowledge_base("knowledge_base.txt")
    print(f"Found {len(qa_pairs)} Q&A pairs")
    
    # Create the index
    if await uploader.create_index():
        # Upload documents
        await uploader.upload_documents(qa_pairs)
        
        # Test search
        await uploader.test_search()
    else:
        print("Failed to create index")

if __name__ == "__main__":
    asyncio.run(main())
