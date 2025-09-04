import logging
import json
import byoeb.chat_app.configuration.dependency_setup as dependency_setup
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse

CHAT_API_NAME = 'chat_api'
chat_apis_router = APIRouter()
_logger = logging.getLogger(CHAT_API_NAME)

@chat_apis_router.post("/receive")
async def receive(request: Request):
    """
    Handle incoming WhatsApp messages.
    """
    body = await request.json()
    # print("Received the request: ", json.dumps(body))
    _logger.info(f"Received the request: {json.dumps(body)}")
    response = await dependency_setup.message_producer_handler.handle(body)
    _logger.info(f"Response: {response}")
    return JSONResponse(
        content=response.message,
        status_code=response.status_code
    )

@chat_apis_router.post("/webhook/qikchat")
async def qikchat_webhook(request: Request):
    """
    Handle incoming Qikchat messages.
    """
    body = await request.json()
    _logger.info(f"Received Qikchat webhook: {json.dumps(body)}")
    response = await dependency_setup.message_producer_handler.handle(body)
    _logger.info(f"Qikchat Response: {response}")
    return JSONResponse(
        content=response.message,
        status_code=response.status_code
    )

# Alias endpoint to support existing external webhook path
@chat_apis_router.post("/webhook/whk")
async def qikchat_webhook_alias(request: Request):
    """
    Handle incoming Qikchat messages from /webhook/whk path.
    """
    print("=== WEBHOOK ENDPOINT HIT - PRINT STATEMENT ===")
    _logger.info("=== WEBHOOK ENDPOINT HIT ===")
    try:
        # print("Attempting to parse JSON body...")
        _logger.info("Attempting to parse JSON body...")
        body = await request.json()
        # print("JSON parsing successful!")
        # print(f"Body type: {type(body)}")
        # print(f"Body keys: {list(body.keys()) if isinstance(body, dict) else 'Not a dict'}")
        # _logger.info("JSON parsing successful!")
        
        _logger.info(f"=== FULL QIKCHAT WEBHOOK PAYLOAD ===")
        _logger.info(f"Raw JSON: {json.dumps(body, indent=2)}")
        _logger.info(f"Payload type: {type(body)}")
        if isinstance(body, dict):
            _logger.info(f"Top-level keys: {list(body.keys())}")
        _logger.info(f"=== END PAYLOAD DEBUG ===")
        
        # print("Starting message processing...")
        _logger.info("Starting message processing...")
        response = await dependency_setup.message_producer_handler.handle(body)
        # print(f"Message processing completed. Response: {response}")
        _logger.info(f"Message processing completed. Response: {response}")
        
        # Handle the case where response.message might be an Exception object
        response_content = response.message
        if isinstance(response.message, Exception):
            response_content = str(response.message)
        
        return JSONResponse(
            content=response_content,
            status_code=response.status_code
        )
    except json.JSONDecodeError as e:
        print(f"JSON DECODE ERROR: {str(e)}")
        _logger.error(f"JSON DECODE ERROR: {str(e)}")
        return JSONResponse(
            content=f"Invalid JSON: {str(e)}",
            status_code=400
        )
    except Exception as e:
        print(f"WEBHOOK ERROR: {str(e)}")
        print(f"Error type: {type(e)}")
        _logger.error(f"WEBHOOK ERROR: {str(e)}")
        _logger.error(f"Error type: {type(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        _logger.error(f"Full traceback: {traceback.format_exc()}")
        return JSONResponse(
            content=f"Webhook processing error: {str(e)}",
            status_code=500
        )

@chat_apis_router.get("/get_bot_messages")
async def get_bot_messages(
    request: Request, 
    timestamp: str = Query(..., description="Unix timestamp as a string")
):
    """
    Get all messages for a specific BO.
    """
    responses = await dependency_setup.message_db_service.get_latest_bot_messages_by_timestamp(timestamp)
    byoeb_response = []
    for response in responses:
        byoeb_response.append(response.model_dump())
    return JSONResponse(
        content=byoeb_response,
        status_code=200
    )

@chat_apis_router.delete("/delete_message_collection")
async def delete_collection(
    request: Request,
):
    """
    Delete a collection from the database.
    """
    response, e = await dependency_setup.mongo_db_service.delete_message_collection()
    if response == True:
        return JSONResponse(
            content="Successfully deleted",
            status_code=200
        )
    elif response == False and e is None:
        return JSONResponse(
            content="Failed to delete",
            status_code=500
        )
    elif e is not None:
        return JSONResponse(
            content=f"Error: {e}",
            status_code=500
        )
