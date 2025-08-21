#!/usr/bin/env python3
"""
Quick test script to check ChromaDB contents
"""
import chromadb
import os

def test_chromadb():
    """Test ChromaDB connection and content"""
    try:
        # Connect to ChromaDB
        chroma_path = "byoeb/byoeb/chroma_db"
        client = chromadb.PersistentClient(path=chroma_path)
        
        # List all collections
        collections = client.list_collections()
        print(f"Found {len(collections)} collections:")
        
        for collection in collections:
            print(f"\nCollection: {collection.name}")
            count = collection.count()
            print(f"Number of documents: {count}")
            
            # Sample a few documents
            if count > 0:
                results = collection.peek(limit=3)
                print("Sample documents:")
                for i, doc in enumerate(results['documents'][:3]):
                    print(f"  {i+1}. {doc[:100]}...")
                    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_chromadb()
