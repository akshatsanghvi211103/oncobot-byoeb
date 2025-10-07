import logging
import json
import byoeb.chat_app.configuration.dependency_setup as dependency_setup
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

USER_API_NAME = 'user_api'

user_apis_router = APIRouter()
_logger = logging.getLogger(USER_API_NAME)

@user_apis_router.post("/register_users")
async def register_users(request: Request):
    print("🔧 DEBUG: API register_users endpoint called", flush=True)
    body = await request.json()
    print(f"🔧 DEBUG: API received body: {body}", flush=True)
    
    # Write to debug file at API level
    import os
    debug_file = os.path.join(os.getcwd(), "api_debug.log")
    with open(debug_file, "a") as f:
        f.write(f"API register_users called with body: {body}\n")
    
    response = await dependency_setup.users_handler.aregister(body)
    print("Response: ", response.message)
    return JSONResponse(
        content=response.message,
        status_code=response.status_code
    )

@user_apis_router.post("/update_users")
async def update_users():
    return JSONResponse(content={"message": "received"}, status_code=200)

@user_apis_router.delete("/delete_users")
async def delete_users(request: Request):
    body = await request.json()
    response = await dependency_setup.users_handler.adelete(body)
    return JSONResponse(
        content=response.message,
        status_code=response.status_code
    )

@user_apis_router.get("/get_users")
async def get_users(request: Request):
    body = await request.json()
    response = await dependency_setup.users_handler.aget(body)
    return JSONResponse(
        content=response.message,
        status_code=response.status_code
    )