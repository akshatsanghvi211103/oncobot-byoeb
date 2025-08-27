import asyncio
import logging
from enum import Enum
from byoeb_integrations.channel.whatsapp.register import RegisterWhatsapp
from byoeb_integrations.channel.qikchat.register import RegisterQikchat
from byoeb_integrations.channel.qikchat.qikchat_client import QikchatClient
from byoeb.chat_app.configuration.config import (
    env_whatsapp_token,
    env_whatsapp_phone_number_id,
    env_whatsapp_auth_token,
    env_qikchat_api_key,
    env_qikchat_verify_token
)
from byoeb_integrations.channel.whatsapp.meta.async_whatsapp_client import AsyncWhatsAppClient

class ChannelType(Enum):
    WHATSAPP = 'whatsapp'
    QIKCHAT = 'qikchat'

class ChannelRegisterFactory:
    def __init__(self):
        self._logger = logging.getLogger(__name__)

    def get(
        self,
        channel_type: str
    ):
        if channel_type == ChannelType.WHATSAPP.value:
            return RegisterWhatsapp(env_whatsapp_token)
        elif channel_type == ChannelType.QIKCHAT.value:
            return RegisterQikchat(env_qikchat_verify_token)
        else:
            self._logger.error(f"Invalid channel type: {channel_type}")
            raise ValueError(f"Invalid channel type: {channel_type}")
    

class ChannelClientFactory:
    _whatsapp_client = None
    _qikchat_client = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(
        self,
        config
    ):
        self._logger = logging.getLogger(__name__)
        self._config = config

    async def __get_whatsapp_client(
        self
    ) -> AsyncWhatsAppClient:
        async with self._lock:
            if self._whatsapp_client is None:
                self._whatsapp_client = AsyncWhatsAppClient(
                    phone_number_id=env_whatsapp_phone_number_id,
                    bearer_token=env_whatsapp_auth_token,
                    reuse_client=self._config["channel"]["whatsapp"]["reuse_client"]
                )
            return self._whatsapp_client

    async def __get_qikchat_client(
        self
    ) -> QikchatClient:
        async with self._lock:
            if self._qikchat_client is None:
                self._qikchat_client = QikchatClient(
                    api_key=env_qikchat_api_key,
                    base_url="https://api.qikchat.in/v1"  # Fixed: Use correct Qikchat API endpoint
                )
            return self._qikchat_client

    async def get(
        self,
        channel_type: str
    ):
        if channel_type == ChannelType.WHATSAPP.value:
            return await self.__get_whatsapp_client()
        elif channel_type == ChannelType.QIKCHAT.value:
            return await self.__get_qikchat_client()
        else:
            self._logger.error(f"Invalid channel type: {channel_type}")
            raise ValueError(f"Invalid channel type: {channel_type}")
    
    async def close(self):
        if isinstance(self._whatsapp_client, AsyncWhatsAppClient):
            await self._whatsapp_client._close()
        if isinstance(self._qikchat_client, QikchatClient):
            await self._qikchat_client.close()