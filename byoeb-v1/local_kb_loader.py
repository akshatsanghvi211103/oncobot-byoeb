"""
Local knowledge base loader for BYOeB - loads files from local directory
"""
import os
import asyncio
import logging
from pathlib import Path
from typing import List
from datetime import datetime
from byoeb_core.data_parser.llama_index_text_parser import LLamaIndexTextParser, LLamaIndexTextSplitterType
from byoeb_core.models.media_storage.file_data import FileMetadata, FileData

logger = logging.getLogger("local_kb_service")

def load_kb_from_local_files(files_directory: str, vector_store):
    """
    Load knowledge base from local text files
    
    Args:
        files_directory: Path to directory containing text files
        vector_store: Vector store instance to add chunks to
    """
    text_parser = LLamaIndexTextParser(
        chunk_size=300,
        chunk_overlap=50,
    )
    
    # Clear existing data
    vector_store.delete_store()
    
    # Load all text files from directory
    files_data = load_local_files(files_directory)
    
    if not files_data:
        print("No files found or loaded")
        return 0
    
    # Parse into chunks
    chunks = text_parser.get_chunks_from_collection(
        files_data,
        splitter_type=LLamaIndexTextSplitterType.SENTENCE
    )
    
    print(f"Generated {len(chunks)} chunks from {len(files_data)} files")
    
    # Add to vector store
    vector_store.add_nodes(chunks)
    
    collection_count = vector_store.collection.count()
    print(f"Final collection count: {collection_count}")
    return collection_count

def load_local_files(directory_path: str) -> List[FileData]:
    """
    Load all text files from a local directory
    """
    files_data = []
    directory = Path(directory_path)
    
    if not directory.exists():
        print(f"Directory does not exist: {directory_path}")
        return files_data
    
    # Get all text files
    text_files = list(directory.glob("*.txt"))
    print(f"Found {len(text_files)} text files in {directory_path}")
    
    for file_path in text_files:
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Create metadata
            metadata = FileMetadata(
                file_name=file_path.name,
                file_type=file_path.suffix,
                creation_time=datetime.now().isoformat()
            )
            
            # Create FileData object
            file_data = FileData(
                data=content.encode('utf-8'),
                metadata=metadata
            )
            
            files_data.append(file_data)
            print(f"Loaded: {file_path.name}")
            
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
    
    return files_data

def load_kb_from_single_file(file_path: str, vector_store):
    """
    Load knowledge base from a single text file
    """
    text_parser = LLamaIndexTextParser(
        chunk_size=300,
        chunk_overlap=50,
    )
    
    # Clear existing data
    vector_store.delete_store()
    
    try:
        # Read the single file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Create metadata
        metadata = FileMetadata(
            file_name=os.path.basename(file_path),
            file_type=os.path.splitext(file_path)[1],
            creation_time=datetime.now().isoformat()
        )
        
        # Create FileData object
        file_data = FileData(
            data=content.encode('utf-8'),
            metadata=metadata
        )
        
        # Parse into chunks
        chunks = text_parser.get_chunks_from_collection(
            [file_data],
            splitter_type=LLamaIndexTextSplitterType.SENTENCE
        )
        
        print(f"Generated {len(chunks)} chunks from {file_path}")
        
        # Add to vector store
        vector_store.add_nodes(chunks)
        
        collection_count = vector_store.collection.count()
        print(f"Final collection count: {collection_count}")
        return collection_count
        
    except Exception as e:
        print(f"Error loading file {file_path}: {e}")
        return 0

# Example usage functions
async def create_kb_from_local_directory(directory_path: str = "knowledge_base_files"):
    """
    Main function to create KB from local directory
    """
    try:
        # Import the vector store - you'll need to configure this
        from byoeb.kb_app.configuration.dependency_setup import vector_store
        return load_kb_from_local_files(directory_path, vector_store)
    except ImportError as e:
        print(f"Could not import vector_store: {e}")
        print("Make sure you have the proper dependencies configured")
        return 0

async def create_kb_from_single_local_file(file_path: str = "knowledge_base.txt"):
    """
    Main function to create KB from single file
    """
    try:
        # Import the vector store - you'll need to configure this
        from byoeb.kb_app.configuration.dependency_setup import vector_store
        return load_kb_from_single_file(file_path, vector_store)
    except ImportError as e:
        print(f"Could not import vector_store: {e}")
        print("Make sure you have the proper dependencies configured")
        return 0

if __name__ == "__main__":
    # Test the local loading
    print("Testing local KB loading...")
    
    # Test with single file (using the knowledge_base.txt from parent directory)
    asyncio.run(create_kb_from_single_local_file("../knowledge_base.txt"))
