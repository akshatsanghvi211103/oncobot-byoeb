#!/usr/bin/env python3
"""
Minimal webhook test server to verify Qikchat integration
without Azure dependencies.
"""

import json
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/")
async def health():
    return {"status": "Chat bot is running", "webhook": "/webhook/whk"}

@app.post("/webhook/whk")
async def qikchat_webhook(request: Request):
    """Handle incoming Qikchat messages"""
    body = await request.json()
    print(f"🎯 Received Qikchat webhook: {json.dumps(body, indent=2)}")
    
    # Simple response for testing
    response_message = "Hello! I received your message. This is a test response."
    
    print(f"📤 Would send response: {response_message}")
    
    return JSONResponse(
        content={"status": "received", "message": "Message processed"},
        status_code=200
    )

@app.post("/webhook/qikchat")
async def qikchat_webhook_alt(request: Request):
    """Alternative endpoint for Qikchat messages"""
    return await qikchat_webhook(request)

if __name__ == '__main__':
    print("🚀 Starting minimal Qikchat webhook test server...")
    print("📡 Webhook endpoint: http://127.0.0.1:5000/webhook/whk")
    print("🔍 Health check: http://127.0.0.1:5000/")
    uvicorn.run(app, host="127.0.0.1", port=5000)
