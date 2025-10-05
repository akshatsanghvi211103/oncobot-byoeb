import threading
import logging
from enum import Enum
from typing import Dict, Optional, Any, List
from byoeb_integrations.llms.azure_openai.async_azure_openai import AsyncAzureOpenAILLM
from byoeb_core.translators.text.base import BaseTextTranslator


class AsyncAzureOpenAITextTranslator(BaseTextTranslator):
    __DEFAULT_TEMPERATURE = 0

    def __init__(
        self,
        llm_client: AsyncAzureOpenAILLM,
        bot_config: dict,
    ):
        self.llm_client = llm_client
        self.bot_config = bot_config
        self.__logger = logging.getLogger(self.__class__.__name__)

    def translate_text(self, input_text, source_language, target_language, system_prompt, **kwargs):
        raise NotImplementedError

    async def atranslate_text(self, input_text, source_language, target_language, **kwargs):
        """
        Translate text using LLM. This method signature matches the Azure Text Translator
        to ensure compatibility with existing code.
        """
        try:
            # If source and target languages are the same, return input text
            if source_language == target_language:
                self.__logger.debug(f"Translation skipped - same language ({source_language}): '{input_text[:100]}...'")
                return input_text
            
            # Get system and user prompts from bot config
            # When translating TO English, we need a different system prompt
            if target_language == "en":
                # Translating FROM some language TO English
                system_prompt = f"You are a translation assistant. Translate the provided {source_language} text to English. Respond with ONLY the translated English text, without any explanation, quotes, or additional formatting."
            else:
                # Translating FROM English TO some other language (use existing logic)
                system_prompt = self.bot_config["llm_translation"]["system_prompt"].get(target_language)
                if not system_prompt:
                    self.__logger.warning(f"No system prompt found for target language '{target_language}', using fallback")
                    system_prompt = f"You are a translation assistant. Translate the provided text to {target_language}. Respond with ONLY the translated text, without any explanation, quotes, or additional formatting."
            
            user_prompt = self.bot_config["llm_translation"]["user_prompt"]
            
            # Log the original text
            self.__logger.info(f"🔤 LLM Translation - Original ({source_language}): '{input_text}'")
            
            # Build the prompt
            prompt = [{"role": "system", "content": system_prompt}]
            formatted_user_prompt = user_prompt.replace("<TEXT>", input_text)
            prompt.append({"role": "user", "content": formatted_user_prompt})
            
            # Generate translation using LLM
            llm_resp, translated_text = await self.llm_client.agenerate_response(
                prompts=prompt
            )
            
            # Log the translated text
            self.__logger.info(f"🔤 LLM Translation - Translated ({target_language}): '{translated_text}'")
            
            return translated_text
            
        except Exception as e:
            self.__logger.error(f"Error in LLM translation from {source_language} to {target_language}: {e}")
            # Fallback: return original text to avoid breaking the flow
            self.__logger.warning(f"Returning original text due to translation error: '{input_text}'")
            return input_text

    # Legacy method for backward compatibility
    async def atranslate_text_with_prompts(self, input_text, source_language, target_language, system_prompt, user_prompt, **kwargs):
        """
        Legacy method that accepts system_prompt and user_prompt parameters directly.
        This is for backward compatibility with existing test files.
        """
        try:
            assert source_language == "en", "Currently only source language as English is supported"
            if source_language == target_language:
                return input_text
                
            # Log the original text
            self.__logger.info(f"🔤 LLM Translation (Legacy) - Original ({source_language}): '{input_text}'")
            
            prompt = [{"role": "system", "content": system_prompt}]
            user_prompt = user_prompt.replace("<TEXT>", input_text)
            prompt.append({"role": "user", "content": user_prompt})
            llm_resp, translated_text = await self.llm_client.agenerate_response(
                prompts=prompt
            )
            
            # Log the translated text
            self.__logger.info(f"🔤 LLM Translation (Legacy) - Translated ({target_language}): '{translated_text}'")
            
            return translated_text
            
        except Exception as e:
            self.__logger.error(f"Error in legacy LLM translation from {source_language} to {target_language}: {e}")
            # Fallback: return original text to avoid breaking the flow
            self.__logger.warning(f"Returning original text due to translation error: '{input_text}'")
            return input_text