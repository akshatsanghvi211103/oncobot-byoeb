#!/usr/bin/env python3
"""
Simple audio proxy server for QikChat compatibility.
This serves audio files from Azure Blob Storage without exposing SAS tokens.
"""
from flask import Flask, Response, request, abort
import requests
import os
import asyncio
import logging
from azure.identity import DefaultAzureCredential
import sys

# Add project paths
sys.path.append(os.path.abspath('.'))
sys.path.append(os.path.abspath('./byoeb'))
sys.path.append(os.path.abspath('./byoeb-core'))
sys.path.append(os.path.abspath('./byoeb-integrations'))

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize Azure Blob Storage client
from byoeb_integrations.media_storage.azure.async_azure_blob_storage import AsyncAzureBlobStorage

blob_storage = None

async def init_blob_storage():
    """Initialize blob storage client"""
    global blob_storage
    credential = DefaultAzureCredential()
    blob_storage = AsyncAzureBlobStorage(
        storage_account_name="smartkcstorage1",
        container_name="oncobot-container",
        credential=credential
    )

@app.route('/audio/<filename>')
def serve_audio(filename):
    """
    Serve audio file from Azure Blob Storage.
    This provides a clean URL that QikChat can access without SAS tokens.
    """
    try:
        # Validate filename (security check)
        if not filename.endswith('.mp3') or '..' in filename or '/' in filename:
            abort(400, "Invalid filename")
        
        # Generate SAS URL for the file
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            sas_url = loop.run_until_complete(blob_storage.get_blob_sas_url(filename, expiry_hours=1))
        finally:
            loop.close()
        
        if not sas_url:
            abort(404, "File not found")
        
        # Fetch the file from Azure Blob Storage
        response = requests.get(sas_url, stream=True, timeout=30)
        
        if response.status_code != 200:
            app.logger.error(f"Failed to fetch {filename} from blob storage: {response.status_code}")
            abort(502, "Failed to fetch audio file")
        
        # Stream the audio file to QikChat
        def generate():
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        
        return Response(
            generate(),
            mimetype='audio/mpeg',
            headers={
                'Content-Type': 'audio/mpeg',
                'Content-Length': response.headers.get('Content-Length', ''),
                'Cache-Control': 'public, max-age=3600',
                'Access-Control-Allow-Origin': '*'
            }
        )
        
    except Exception as e:
        app.logger.error(f"Error serving audio file {filename}: {e}")
        abort(500, "Internal server error")

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "qikchat-audio-proxy"}

if __name__ == '__main__':
    # Initialize blob storage
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_blob_storage())
    
    print("🎵 QikChat Audio Proxy Server")
    print("=" * 40)
    print("🚀 Starting server on http://localhost:5001")
    print("📱 Use URLs like: http://your-ngrok-url.com/audio/filename.mp3")
    print("🔗 This will serve audio files without SAS token complexity")
    
    app.run(host='0.0.0.0', port=5001, debug=True)