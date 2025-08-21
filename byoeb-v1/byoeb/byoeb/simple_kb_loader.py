"""
Simplified local knowledge base loader using ChromaDB directly
"""
import chromadb
import json
import os
from pathlib import Path
from typing import List
import uuid

def load_knowledge_base_to_chroma(file_path: str = "../../knowledge_base.txt"):
    """
    Load knowledge base from text file directly into ChromaDB
    """
    
    # Initialize ChromaDB
    chroma_client = chromadb.PersistentClient(path="./chroma_db")
    
    # Create or get collection
    collection_name = "oncology_kb"
    try:
        # Delete existing collection if it exists
        chroma_client.delete_collection(name=collection_name)
        print(f"Deleted existing collection: {collection_name}")
    except:
        pass
    
    collection = chroma_client.create_collection(name=collection_name)
    print(f"Created new collection: {collection_name}")
    
    # Read the knowledge base file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"Successfully read file: {file_path}")
    except Exception as e:
        print(f"Error reading file: {e}")
        return
    
    # Parse Q&A pairs
    documents = []
    metadatas = []
    ids = []
    
    lines = content.strip().split('\n')
    current_qa = {}
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.startswith('Q') and ':' in line:
            # Process previous Q&A if exists
            if current_qa.get('question') and current_qa.get('answer'):
                # Create document text combining question and answer
                doc_text = f"Question: {current_qa['question']}\nAnswer: {current_qa['answer']}"
                documents.append(doc_text)
                
                # Create metadata
                metadata = {
                    "type": "qa_pair",
                    "question": current_qa['question'],
                    "answer": current_qa['answer'],
                    "category": current_qa.get('category', 'general')
                }
                metadatas.append(metadata)
                
                # Create unique ID
                qa_id = f"qa_{len(documents)}"
                ids.append(qa_id)
            
            # Start new Q&A
            current_qa = {}
            
            # Parse question line
            if '(Category:' in line:
                # Extract category
                category_start = line.find('(Category:') + 10
                category_end = line.find(')', category_start)
                category = line[category_start:category_end].strip()
                current_qa['category'] = category
                
                # Extract question (after the colon)
                question_start = line.find(':', line.find(')')) + 1
                current_qa['question'] = line[question_start:].strip()
            else:
                # No category, just extract question
                question_start = line.find(':') + 1
                current_qa['question'] = line[question_start:].strip()
                
        elif line.startswith('A') and ':' in line and 'question' in current_qa:
            # This is an answer line
            answer_start = line.find(':') + 1
            current_qa['answer'] = line[answer_start:].strip()
    
    # Process the last Q&A pair
    if current_qa.get('question') and current_qa.get('answer'):
        doc_text = f"Question: {current_qa['question']}\nAnswer: {current_qa['answer']}"
        documents.append(doc_text)
        
        metadata = {
            "type": "qa_pair",
            "question": current_qa['question'],
            "answer": current_qa['answer'],
            "category": current_qa.get('category', 'general')
        }
        metadatas.append(metadata)
        
        qa_id = f"qa_{len(documents)}"
        ids.append(qa_id)
    
    print(f"Parsed {len(documents)} Q&A pairs")
    
    # Add to ChromaDB in batches
    batch_size = 50
    for i in range(0, len(documents), batch_size):
        batch_docs = documents[i:i+batch_size]
        batch_metadatas = metadatas[i:i+batch_size]
        batch_ids = ids[i:i+batch_size]
        
        collection.add(
            documents=batch_docs,
            metadatas=batch_metadatas,
            ids=batch_ids
        )
        print(f"Added batch {i//batch_size + 1}: {len(batch_docs)} documents")
    
    # Verify the collection
    count = collection.count()
    print(f"Total documents in collection: {count}")
    
    return collection

def test_knowledge_base(collection, query: str = "What is cancer?"):
    """
    Test the knowledge base with a sample query
    """
    print(f"\nTesting with query: '{query}'")
    print("-" * 50)
    
    results = collection.query(
        query_texts=[query],
        n_results=3
    )
    
    for i, (doc, metadata, score) in enumerate(zip(
        results['documents'][0], 
        results['metadatas'][0],
        results['distances'][0]
    )):
        print(f"\nResult {i+1} (similarity: {1-score:.3f}):")
        print(f"Category: {metadata.get('category', 'N/A')}")
        print(f"Question: {metadata.get('question', 'N/A')}")
        print(f"Answer: {metadata.get('answer', 'N/A')}")
        print("-" * 30)

if __name__ == "__main__":
    print("Loading oncology knowledge base into ChromaDB...")
    
    # Load the knowledge base
    collection = load_knowledge_base_to_chroma()
    
    if collection:
        # Test with some queries
        test_queries = [
            "What is cancer?",
            "What are the side effects of radiotherapy?",
            "How long does radiotherapy take?",
            "Can I eat during treatment?"
        ]
        
        for query in test_queries:
            test_knowledge_base(collection, query)
            
        print("\n" + "="*60)
        print("Knowledge base successfully loaded!")
        print("You can now use this ChromaDB collection for your oncology chatbot.")
        print("Collection name: 'oncology_kb'")
        print("Database path: './chroma_db'")
