import asyncio
import os
import logging
from typing import Any, List
from datetime import datetime, timedelta
from byoeb_core.media_storage.base import BaseMediaStorage
from byoeb_core.models.media_storage.file_data import FileMetadata, FileData
from azure.storage.blob.aio import BlobServiceClient
from azure.storage.blob import generate_blob_sas, BlobSasPermissions, UserDelegationKey
from azure.identity import DefaultAzureCredential
from azure.core.exceptions import (
    ResourceNotFoundError,
    ResourceExistsError,
    ClientAuthenticationError,
    HttpResponseError
)

class StatusCodes:
    OK = 200
    CREATED = 201
    NO_CONTENT = 204
    NOT_FOUND = 404
    CONFLICT = 409
    UNAUTHORIZED = 401
    INTERNAL_SERVER_ERROR = 500

class AsyncAzureBlobStorage(BaseMediaStorage):
    def __init__(
        self,
        container_name: str,
        account_url: str,
        credentials: None,
        connection_string: str = None,
        **kwargs
    ):
        self.__logger = logging.getLogger(self.__class__.__name__)
        if container_name is None:
            raise ValueError("container_name must be provided")
        if credentials is not None and account_url is not None:
            self.__blob_service_client = BlobServiceClient(
                account_url=account_url,
                container_name=container_name,
                credential=credentials
            )
        elif connection_string is not None:
            self.__blob_service_client = BlobServiceClient.from_connection_string(
                connection_string=connection_string,
                container_name=container_name
            )
        else:
            raise ValueError("Either account url and credentials or connection_string must be provided")
        self.__container_name = container_name
    
    async def aget_file_properties(
        self,
        file_name,
    ) -> (str, FileMetadata | str):
        blob_client = self.__blob_service_client.get_blob_client(
            container=self.__container_name,
            blob=file_name
        )
        try:
            properties = await blob_client.get_blob_properties()
            return StatusCodes.OK, FileMetadata(
                file_name=file_name,
                file_type=properties.metadata.get("file_type"),
                creation_time=properties.creation_time.strftime("%Y-%m-%d %H:%M:%S"),
            )
        except ResourceNotFoundError as e:
            self.__logger.error("Blob not found: %s", e)
            return StatusCodes.NOT_FOUND, e.message 
        except Exception as e:
            self.__logger.error("Error getting blob properties: %s", e)
            raise e
        
    async def aget_all_files_properties(
        self,
    ) -> List[FileMetadata]:
        container_name = self.__container_name
        container_client = self.__blob_service_client.get_container_client(container_name)
        files = []
        async for blob in container_client.list_blobs():
            status, properties = await self.aget_file_properties(blob.name)
            if isinstance(properties, FileMetadata):
                files.append(properties)
        return files
    
    async def aupload_file(
        self,
        file_name,
        file_path,
        file_type=None,
    ):
        from azure.storage.blob import ContentSettings
        
        blob_client = self.__blob_service_client.get_blob_client(
            container=self.__container_name,
            blob=file_name
        )
        if file_type is None:
            file_type = os.path.splitext(file_path)[1]
        metadata = {
            "file_name": file_name,
            "file_type": file_type,
        }
        
        # Set appropriate content type based on file extension
        content_type = "application/octet-stream"  # default
        if file_type.lower() in ['.wav', '.wave']:
            content_type = "audio/wav"
        elif file_type.lower() in ['.mp3']:
            content_type = "audio/mpeg"
        elif file_type.lower() in ['.mp4']:
            content_type = "audio/mp4"
        elif file_type.lower() in ['.ogg']:
            content_type = "audio/ogg"
        
        content_settings = ContentSettings(content_type=content_type)
        
        try:
            with open(file_path, "rb") as data:
                await blob_client.upload_blob(
                    data, 
                    metadata=metadata,
                    content_settings=content_settings
                )
            return StatusCodes.CREATED, None
        except ResourceExistsError as e:
            self.__logger.error("Blob already exists: %s", e)
            return StatusCodes.CONFLICT, e.message
        except Exception as e:
            self.__logger.error("Error uploading audio file to blob storage: %s", e)
            raise e
    
    async def aupload_bytes(
        self,
        file_name: str,
        data: bytes,
        file_type: str = None,
    ):
        from azure.storage.blob import ContentSettings
        
        blob_client = self.__blob_service_client.get_blob_client(
            container=self.__container_name,
            blob=file_name
        )
        if file_type is None:
            file_type = os.path.splitext(file_name)[1]
        metadata = {
            "file_name": file_name,
            "file_type": file_type,
        }
        
        # Set appropriate content type based on file extension
        content_type = "application/octet-stream"  # default
        if file_type.lower() in ['.wav', '.wave']:
            content_type = "audio/wav"
        elif file_type.lower() in ['.mp3']:
            content_type = "audio/mpeg"
        elif file_type.lower() in ['.mp4']:
            content_type = "audio/mp4"
        elif file_type.lower() in ['.ogg']:
            content_type = "audio/ogg"
        
        content_settings = ContentSettings(content_type=content_type)
        
        try:
            await blob_client.upload_blob(
                data, 
                metadata=metadata, 
                overwrite=True,
                content_settings=content_settings
            )
            return StatusCodes.CREATED, None
        except Exception as e:
            self.__logger.error("Error uploading bytes to blob storage: %s", e)
            raise e
    
    def get_blob_url(self, file_name: str) -> str:
        """Get the public URL for a blob"""
        blob_client = self.__blob_service_client.get_blob_client(
            container=self.__container_name,
            blob=file_name
        )
        return blob_client.url
        
    async def get_blob_sas_url(self, file_name: str, expiry_hours: int = 1) -> str:
        """
        Generate a User Delegation SAS URL for temporary public access to a blob.
        This works with Azure AD authentication when shared key access is disabled.
        
        Args:
            file_name: Name of the blob file
            expiry_hours: How many hours the URL should be valid (default: 1 hour)
            
        Returns:
            SAS URL that allows temporary public access to the blob
        """
        
        # QIKCHAT COMPATIBILITY: Try different approaches based on environment variables
        import os
        
        # Option 1: Use public URLs (requires public container)
        if os.environ.get("QIKCHAT_USE_PUBLIC_URLS", "false").lower() == "true":
            self.__logger.info(f"Using public URL for QikChat compatibility: {file_name}")
            return self.get_blob_url(file_name)
        
        # Option 2: Use proxy server 
        proxy_base_url = os.environ.get("QIKCHAT_AUDIO_PROXY_URL")
        if proxy_base_url:
            proxy_url = f"{proxy_base_url.rstrip('/')}/audio/{file_name}"
            self.__logger.info(f"Using proxy URL for QikChat compatibility: {proxy_url}")
            return proxy_url
        try:
            blob_client = self.__blob_service_client.get_blob_client(
                container=self.__container_name,
                blob=file_name
            )
            
            # For Azure AD authentication, we need to use User Delegation SAS
            start_time = datetime.utcnow()
            expiry_time = start_time + timedelta(hours=expiry_hours)
            
            # Get user delegation key from the service
            try:
                delegation_key = await self.__blob_service_client.get_user_delegation_key(
                    key_start_time=start_time,
                    key_expiry_time=expiry_time
                )
                
                # Generate User Delegation SAS token with compatible service version
                from azure.storage.blob import generate_blob_sas
                sas_token = generate_blob_sas(
                    account_name=blob_client.account_name,
                    container_name=self.__container_name,
                    blob_name=file_name,
                    user_delegation_key=delegation_key,
                    permission=BlobSasPermissions(read=True),
                    expiry=expiry_time,
                    start=start_time,
                    version="2022-11-02"  # Use older, more compatible service version
                )
                
                # Construct the full SAS URL
                sas_url = f"{blob_client.url}?{sas_token}"
                self.__logger.info(f"Generated User Delegation SAS URL for {file_name}, expires in {expiry_hours} hours")
                self.__logger.info(f"SAS URL: {sas_url}")
                
                # Test the URL accessibility
                try:
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.head(sas_url) as response:
                            self.__logger.info(f"SAS URL test - Status: {response.status}")
                            if response.status != 200:
                                self.__logger.warning(f"SAS URL may not be accessible - Status: {response.status}")
                except Exception as test_error:
                    self.__logger.warning(f"Could not test SAS URL accessibility: {test_error}")
                
                return sas_url
                
            except Exception as delegation_error:
                self.__logger.error(f"Failed to get user delegation key: {delegation_error}")
                self.__logger.info(f"Trying public URL as fallback for QikChat compatibility")
                # Fall back to regular public URL (temporary workaround for QikChat access issues)
                return self.get_blob_url(file_name)
            
        except Exception as e:
            self.__logger.error(f"Failed to generate User Delegation SAS URL for {file_name}: {e}")
            self.__logger.info(f"Returning public URL as fallback for QikChat compatibility")
            # Fall back to regular URL - temporary workaround for QikChat 403 issues
            return self.get_blob_url(file_name)
        
    async def adownload_file(
        self,
        file_name,
    ) -> (str, FileData | str):
        blob_client = self.__blob_service_client.get_blob_client(
            container=self.__container_name,
            blob=file_name
        )
        blob_download_reponse = None
        try:
            blob_download_reponse = await blob_client.download_blob()
            properties = await blob_client.get_blob_properties()
            return StatusCodes.OK, FileData(
                data=await blob_download_reponse.readall(),
                metadata=FileMetadata(
                    file_name=file_name,
                    file_type=properties.metadata.get("file_type"),
                    creation_time=properties.creation_time.strftime("%Y-%m-%d %H:%M:%S"),
                )
            )
        except ResourceNotFoundError as e:
            self.__logger.error("Blob not found: %s", e)
            return StatusCodes.NOT_FOUND, e.message
        except Exception as e:
            self.__logger.error("Error downloading audio file from blob storage: %s", e)
            raise e
    
    async def adelete_file(
        self,
        file_name: str,
    ) -> Any:
        blob_client = self.__blob_service_client.get_blob_client(
            container=self.__container_name,
            blob=file_name
        )
        try:
            await blob_client.delete_blob()
        except Exception as e:
            self.__logger.error("Error deleting blob from blob storage: %s", e)
            raise e
    
    def get_blob_service_client(self):
        return self.__blob_service_client
    
    def get_container_name(self):
        return self.__container_name
    
    def get_blob_clinet(
        self,
        blob_name: str
    ):
        return self.__blob_service_client.get_blob_client(
            container=self.__container_name,
            blob=blob_name
        )
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.__blob_service_client.__aexit__(exc_type, exc_val, exc_tb)
        self.__logger.info("Container %s closed", self.__container_name)

    async def _close(self):
        await self.__blob_service_client.close()
        self.__blob_service_client = None
        self.__logger.info("Container %s closed", self.__container_name)
    
    # def __del__(self):
    #     loop = asyncio.get_event_loop()
    #     if loop.is_running():
    #         # If the loop is running, create a future and wait for it
    #         asyncio.ensure_future(
    #             self.__blob_service_client.close(),
    #             loop=loop
    #         ).__await__()
    #     else:
    #         # If no loop is running, use asyncio.run
    #         asyncio.run(self.__blob_service_client.close())
    #     self.__logger.info("Container %s closed", self.__container_name)
    