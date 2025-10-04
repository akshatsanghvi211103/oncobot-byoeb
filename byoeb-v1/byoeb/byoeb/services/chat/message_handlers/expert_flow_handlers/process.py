from typing import List, Dict, Any
from byoeb_core.models.byoeb.message_context import ByoebMessageContext, MessageTypes
from byoeb.services.chat.message_handlers.base import Handler

class ByoebExpertProcess(Handler):
    
    async def handle(
        self,
        messages: List[ByoebMessageContext]
    ) -> Dict[str, Any]:
        from byoeb.chat_app.configuration.dependency_setup import text_translator
        from byoeb.chat_app.configuration.config import bot_config
        message = messages[0]
        system_prompt = bot_config["llm_translation"]["system_prompt"]["en"]
        user_prompt = bot_config["llm_translation"]["user_prompt"]
        translated_en_text = await text_translator.atranslate_text(
            input_text=message.message_context.message_source_text,
            source_language=message.user.user_language,
            target_language="en",
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )
        message.message_context.message_english_text = translated_en_text
        if self._successor:
            return await self._successor.handle([message])