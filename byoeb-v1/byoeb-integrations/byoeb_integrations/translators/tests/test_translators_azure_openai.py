import os
import asyncio
import pytest
import logging
from azure.identity import DefaultAzureCredential
from byoeb_integrations import test_environment_path
from dotenv import load_dotenv
from azure.identity import get_bearer_token_provider, AzureCliCredential
from byoeb_integrations.llms.azure_openai.async_azure_openai import AsyncAzureOpenAILLM
from byoeb.chat_app.configuration.config import app_config, bot_config
from byoeb_integrations.translators.text.azure.async_azure_text_translator import AsyncAzureTextTranslator
from byoeb_integrations.translators.text.azure.async_openai_text_translator import AsyncAzureOpenAITextTranslator


load_dotenv(test_environment_path)

credential = DefaultAzureCredential()

AZURE_COGNITIVE_ENDPOINT = app_config["app"]["azure_cognitive_endpoint"]
LLM_MODEL = app_config["llms"]["azure"]["model"]
LLM_ENDPOINT = app_config["llms"]["azure"]["endpoint"]
LLM_API_VERSION = app_config["llms"]["azure"]["api_version"]

token_provider = get_bearer_token_provider(
    AzureCliCredential(), AZURE_COGNITIVE_ENDPOINT
)

async_azure_openai_llm = AsyncAzureOpenAILLM(
    model=LLM_MODEL,
    azure_endpoint=LLM_ENDPOINT,
    token_provider=token_provider,
    api_version=LLM_API_VERSION
)

@pytest.fixture
def event_loop():
    """Create and provide a new event loop for each test."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()

async def aazure_translate_text_en_hi():
    async_openai_text_translator = AsyncAzureOpenAITextTranslator(
        llm_client=async_azure_openai_llm,
        bot_config=bot_config
    )

    system_prompt = bot_config["llm_translation"]["system_prompt"]["hi"]
    user_prompt = bot_config["llm_translation"]["user_prompt"]


    input_text = "After your radiation therapy, it's important to continue eating a balanced diet to support your recovery. You can include soft, moist, and bland foods such as soft-cooked vegetables, boneless chicken, minced meats, half-boiled eggs, simple khichdi, custards, puddings, and ice cream. Ensure you stay hydrated by drinking plenty of liquids like water, milk, and coconut water. Avoid spicy, very hot, and tough fibrous foods, as well as alcohol and tobacco. If you experience any side effects like a dry mouth or difficulty swallowing, use gravies and sauces to soften foods and consider blending or puréeing your meals. Always consult with your healthcare provider or a dietitian for personalized dietary advice."
    source_language = "en"
    target_language = "hi"
    translated_text = await async_openai_text_translator.atranslate_text_with_prompts(
        input_text=input_text,
        source_language=source_language,
        target_language=target_language,
        system_prompt=system_prompt,
        user_prompt=user_prompt
    )
    print(translated_text)
    assert translated_text is not None
    assert translated_text != input_text


async def aazure_translate_text_en_en():
    async_openai_text_translator = AsyncAzureOpenAITextTranslator(
        llm_client=async_azure_openai_llm,
        bot_config=bot_config
    )

    system_prompt = bot_config["llm_translation"]["system_prompt"]["en"]
    user_prompt = bot_config["llm_translation"]["user_prompt"]
    
    input_text = "Hello, how are you?"
    source_language = "en"
    target_language = "en"
    translated_text = await async_openai_text_translator.atranslate_text_with_prompts(
        input_text=input_text,
        source_language=source_language,
        target_language=target_language,
        system_prompt=system_prompt,
        user_prompt=user_prompt
    )
    print(translated_text)
    assert translated_text is not None
    assert translated_text == input_text

# asyncio.run(aazure_translate_text_en_hi())
def test_aazure_translate_text_en_hi(event_loop):
    event_loop.run_until_complete(aazure_translate_text_en_hi())

def test_aazure_translate_text_en_en(event_loop):
    event_loop.run_until_complete(aazure_translate_text_en_en())

if __name__ == "__main__":
    event_loop = asyncio.get_event_loop()
    event_loop.run_until_complete(aazure_translate_text_en_hi())
    event_loop.run_until_complete(aazure_translate_text_en_en())
    event_loop.close()