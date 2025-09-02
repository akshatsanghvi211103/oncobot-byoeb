import aiohttp
import asyncio
import logging
import os
from typing import Dict, Any, List, Optional
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class QikchatClient:
    """
    HTTP client for Qikchat API interactions.
    
    Key Differences from WhatsApp:
    1. Single API key authentication instead of multiple tokens
    2. Different base URL and endpoints
    3. Simpler authentication header structure
    4. Different response format handling
    """
    
    def __init__(self, api_key: str = None, base_url: str = "https://api.qikchat.in/v1"):
        # Use provided API key or get from environment
        self.api_key = api_key or os.getenv("QIKCHAT_API_KEY")
        if not self.api_key:
            raise ValueError("Qikchat API key not provided. Set QIKCHAT_API_KEY environment variable.")
            
        self.base_url = base_url.rstrip('/')
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Headers for all requests - Qikchat uses QIKCHAT-API-KEY header
        self.headers = {
            "QIKCHAT-API-KEY": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        self.logger.info(f"Qikchat client initialized with API key: {self.api_key[:8]}...")
    
    async def send_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a message via Qikchat API.
        
        Key Differences from WhatsApp:
        1. Single endpoint for all message types
        2. Simpler request structure
        3. Different response format
        """
        endpoint = f"{self.base_url}/messages"
        
        async with aiohttp.ClientSession() as session:
            try:
                self.logger.debug(f"Sending message to Qikchat: {json.dumps(message_data, indent=2)}")
                
                async with session.post(
                    endpoint,
                    headers=self.headers,
                    json=message_data
                ) as response:
                    response_data = await response.json()
                    
                    if response.status == 200:
                        self.logger.info(f"Message sent successfully: {response_data.get('message_id')}")
                        return response_data
                    else:
                        self.logger.error(f"Failed to send message. Status: {response.status}, Response: {response_data}")
                        raise Exception(f"Qikchat API error: {response_data}")
                        
            except aiohttp.ClientError as e:
                self.logger.error(f"HTTP client error: {str(e)}")
                raise
            except Exception as e:
                self.logger.error(f"Unexpected error sending message: {str(e)}")
                raise
    
    async def send_audio_message(self, to_contact: str, audio_url: str) -> Dict[str, Any]:
        """
        Send an audio message via Qikchat API.
        
        Args:
            to_contact: The recipient's contact ID
            audio_url: The direct URL to the audio file
        
        Returns:
            Response from Qikchat API
        """
        message_data = {
            "to_contact": to_contact,
            "type": "audio",
            "audio": {
                "link": audio_url
            }
        }
        
        return await self.send_message(message_data)
    
    async def send_batch_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Send multiple messages.
        
        Key Differences from WhatsApp:
        1. May support batch endpoint (depends on Qikchat API)
        2. Fallback to individual sends if batch not supported
        """
        # Check if Qikchat supports batch sending
        batch_endpoint = f"{self.base_url}/messages/batch"
        
        # For now, send individually (can be optimized if Qikchat supports batch)
        results = []
        for message in messages:
            try:
                result = await self.send_message(message)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Failed to send message in batch: {str(e)}")
                results.append({"error": str(e)})
        
        return results
    
    async def mark_as_read(self, message_id: str, from_number: str) -> Dict[str, Any]:
        """
        Mark a message as read.
        
        Key Differences from WhatsApp:
        1. Different endpoint structure
        2. May require different parameters
        """
        endpoint = f"{self.base_url}/messages/{message_id}/read"
        
        read_data = {
            "from": from_number,
            "message_id": message_id
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    endpoint,
                    headers=self.headers,
                    json=read_data
                ) as response:
                    response_data = await response.json()
                    
                    if response.status == 200:
                        self.logger.debug(f"Message marked as read: {message_id}")
                        return response_data
                    else:
                        self.logger.warning(f"Failed to mark message as read: {response_data}")
                        return {"error": response_data}
                        
            except Exception as e:
                self.logger.error(f"Error marking message as read: {str(e)}")
                return {"error": str(e)}
    
    async def get_media(self, media_id: str) -> bytes:
        """
        Download media file by ID.
        
        Key Differences from WhatsApp:
        1. For Qikchat, media_id might be a full URL or just an ID
        2. Different media endpoint structure
        3. May have different authentication requirements
        """
        # Check if media_id is a full URL or just an ID
        if media_id.startswith('http://') or media_id.startswith('https://'):
            # media_id is a full URL, use it directly
            endpoint = media_id
            self.logger.info(f"Media ID is a full URL: {endpoint}")
        else:
            # media_id is just an ID, construct the endpoint
            endpoint = f"{self.base_url}/media/{media_id}"
            self.logger.info(f"Media ID is an ID, constructed endpoint: {endpoint}")
        
        self.logger.info(f"Attempting to download media from: {endpoint}")
        self.logger.info(f"Using headers: {self.headers}")
        
        async with aiohttp.ClientSession() as session:
            try:
                # For direct URLs, we might not need authentication headers
                headers = self.headers if not media_id.startswith('http') else {}
                
                async with session.get(
                    endpoint,
                    headers=headers
                ) as response:
                    self.logger.info(f"Media download response status: {response.status}")
                    self.logger.info(f"Media download response headers: {dict(response.headers)}")
                    
                    if response.status == 200:
                        media_data = await response.read()
                        self.logger.debug(f"Downloaded media: {media_id}, size: {len(media_data)} bytes")
                        return media_data
                    else:
                        error_data = await response.text()
                        self.logger.error(f"Failed to download media. Status: {response.status}")
                        self.logger.error(f"Error response: {error_data}")
                        self.logger.error(f"Response headers: {dict(response.headers)}")
                        raise Exception(f"Media download failed: {error_data}")
                        
            except Exception as e:
                self.logger.error(f"Error downloading media: {str(e)}")
                raise
    
    async def adownload_media(self, media_id: str):
        """
        Download media file by ID and return in the format expected by the byoeb system.
        Returns: (status, MediaData, error)
        """
        try:
            # Use the existing get_media method
            media_data = await self.get_media(media_id)
            
            # For Qikchat, we use audio/wav as default based on the convert_message.py
            mime_type = "audio/wav"  # Default for Qikchat audio messages
            
            # Create MediaData object (we'll create a simple version since import is having issues)
            from typing import NamedTuple
            
            class MediaData(NamedTuple):
                data: bytes
                mime_type: str
            
            media_obj = MediaData(data=media_data, mime_type=mime_type)
            return 200, media_obj, None
            
        except Exception as e:
            self.logger.error(f"Error in adownload_media: {str(e)}")
            return 500, None, str(e)
    
    async def upload_media(self, media_data: bytes, mime_type: str, filename: str) -> Dict[str, Any]:
        """
        Upload media file to Qikchat.
        
        Key Differences from WhatsApp:
        1. Different upload endpoint
        2. May have different file size limits
        3. Different response format
        """
        endpoint = f"{self.base_url}/media/upload"
        
        # Prepare multipart form data
        data = aiohttp.FormData()
        data.add_field('file', media_data, filename=filename, content_type=mime_type)
        
        # Don't include Content-Type header for multipart uploads
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    endpoint,
                    headers=headers,
                    data=data
                ) as response:
                    response_data = await response.json()
                    
                    if response.status == 200:
                        self.logger.info(f"Media uploaded successfully: {response_data.get('media_id')}")
                        return response_data
                    else:
                        self.logger.error(f"Failed to upload media: {response_data}")
                        raise Exception(f"Media upload failed: {response_data}")
                        
            except Exception as e:
                self.logger.error(f"Error uploading media: {str(e)}")
                raise
    
    async def get_webhook_info(self) -> Dict[str, Any]:
        """
        Get current webhook configuration.
        """
        endpoint = f"{self.base_url}/webhook"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    endpoint,
                    headers=self.headers
                ) as response:
                    response_data = await response.json()
                    return response_data
                    
            except Exception as e:
                self.logger.error(f"Error getting webhook info: {str(e)}")
                return {"error": str(e)}
    
    async def set_webhook(self, webhook_url: str, verify_token: str) -> Dict[str, Any]:
        """
        Set webhook URL for receiving messages.
        """
        endpoint = f"{self.base_url}/webhook"
        
        webhook_data = {
            "url": webhook_url,
            "verify_token": verify_token
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    endpoint,
                    headers=self.headers,
                    json=webhook_data
                ) as response:
                    response_data = await response.json()
                    
                    if response.status == 200:
                        self.logger.info(f"Webhook set successfully: {webhook_url}")
                        return response_data
                    else:
                        self.logger.error(f"Failed to set webhook: {response_data}")
                        raise Exception(f"Webhook setup failed: {response_data}")
                        
            except Exception as e:
                self.logger.error(f"Error setting webhook: {str(e)}")
                raise

    async def close(self):
        """
        Close any persistent connections.
        For QikchatClient, this is mostly a placeholder since we create
        new sessions per request, but it maintains interface compatibility.
        """
        self.logger.debug("QikchatClient close called (no persistent connections to close)")
        pass
