import threading
from enum import Enum
from typing import Dict, Optional, Any, List
from byoeb_integrations.llms.azure_openai.async_azure_openai import AsyncAzureOpenAILLM
from byoeb_core.translators.text.base import BaseTextTranslator



class AsyncAzureOpenAITextTranslator(BaseTextTranslator):
    __DEFAULT_TEMPERATURE = 0

    def __init__(
        self,
        llm_client: AsyncAzureOpenAILLM,
    ):
        self.llm_client = llm_client

    def translate_text(self, input_text, source_language, target_language, system_prompt, **kwargs):
        raise NotImplementedError

    async def atranslate_text(self, input_text, source_language, target_language, system_prompt, user_prompt, **kwargs):
        assert source_language == "en", "Currently only source language as English is supported"
        if source_language == target_language:
            return input_text
        prompt = [{"role": "system", "content": system_prompt}]
        user_prompt = user_prompt.replace("<TEXT>", input_text)
        prompt.append({"role": "user", "content": user_prompt})
        llm_resp, response = await self.llm_client.agenerate_response(
            prompts=prompt
        )
        return response