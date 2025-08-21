import logging
import json
import byoeb.services.knowledge_base.local_chromadb as kb
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse

KB_API_NAME = 'kb_api'

kb_apis_router = APIRouter()
_logger = logging.getLogger(KB_API_NAME)

@kb_apis_router.get("/load")
async def load_from_blob_store(request: Request):
    count = await kb.create_kb_from_blob_store()
    return JSONResponse(
        content={"message": f"Loaded {count} documents"},
        status_code=200
    )

@kb_apis_router.get("/load_local")
async def load_from_local_files(
    request: Request,
    directory: str = Query("knowledge_base_files", description="Directory containing knowledge base files")
):
    """
    Load knowledge base from local text files
    """
    try:
        # Import the local loader
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from local_kb_loader import create_kb_from_local_directory
        
        count = await create_kb_from_local_directory(directory)
        return JSONResponse(
            content={"message": f"Loaded {count} documents from local directory: {directory}"},
            status_code=200
        )
    except Exception as e:
        _logger.error(f"Error loading from local files: {e}")
        return JSONResponse(
            content={"error": f"Failed to load local files: {str(e)}"},
            status_code=500
        )

@kb_apis_router.get("/load_local_file")
async def load_from_single_local_file(
    request: Request,
    file_path: str = Query("knowledge_base.txt", description="Path to single knowledge base file")
):
    """
    Load knowledge base from a single local text file
    """
    try:
        # Import the local loader
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from local_kb_loader import create_kb_from_single_local_file
        
        count = await create_kb_from_single_local_file(file_path)
        return JSONResponse(
            content={"message": f"Loaded {count} documents from file: {file_path}"},
            status_code=200
        )
    except Exception as e:
        _logger.error(f"Error loading from local file: {e}")
        return JSONResponse(
            content={"error": f"Failed to load local file: {str(e)}"},
            status_code=500
        )

@kb_apis_router.get("/load")
async def load_from_blob_store(request: Request):
    count = await kb.create_kb_from_blob_store()
    return JSONResponse(
        content={"message": f"Loaded {count} documents"},
        status_code=200
    )

# @kb_apis_router.post("/add_document")
# async def add_document(request: Request):
#     body = await request.json()
#     response = await dependency_setup.users_handler.aregister(body)
#     print("Response: ", response.message)
#     return JSONResponse(
#         content=response.message,
#         status_code=response.status_code
#     )

# @kb_apis_router.delete("/delete_document")
# async def delete_document(request: Request):
#     body = await request.json()
#     response = await dependency_setup.users_handler.adelete(body)
#     return JSONResponse(
#         content=response.message,
#         status_code=response.status_code
#     )

# @kb_apis_router.post("/replace_document")
# async def replace_document(request: Request):
#     body = await request.json()
#     response = await dependency_setup.users_handler.aget(body)
#     return JSONResponse(
#         content=response.message,
#         status_code=response.status_code
#     )