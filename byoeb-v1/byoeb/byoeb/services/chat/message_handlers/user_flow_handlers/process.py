from typing import Dict, Any, List
from byoeb_core.models.byoeb.message_context import ByoebMessageContext, MessageTypes
from byoeb.services.chat.message_handlers.base import Handler

class ByoebUserProcess(Handler):

    async def __handle_process_message_workflow(
        self,
        messages: List[ByoebMessageContext]
    ) -> ByoebMessageContext:
        message = messages[0].model_copy(deep=True)

        # dependency injection
        from byoeb.chat_app.configuration.dependency_setup import text_translator
        from byoeb.chat_app.configuration.dependency_setup import channel_client_factory
        from byoeb.chat_app.configuration.dependency_setup import speech_translator_whisper
        from byoeb_core.convertor.audio_convertor import ogg_opus_to_wav_bytes

        channel_type = message.channel_type
        source_language = message.user.user_language
        translated_en_text = None

        if message.message_context.message_type == MessageTypes.REGULAR_AUDIO.value:
            media_id = message.message_context.media_info.media_id
            print(f"\n=== AUDIO MESSAGE PROCESSING DEBUG ===")
            print(f"Processing audio message with media_id: {media_id}")
            
            channel_client = await channel_client_factory.get(channel_type)
            status, audio_message, err = await channel_client.adownload_media(media_id)
            
            print(f"Media download result: status={status}, audio_message={audio_message is not None}, err={err}")
            
            # Check if media download was successful
            if audio_message is None or err is not None:
                print(f"❌ Failed to download audio media: {err}")
                print(f"=== END AUDIO PROCESSING DEBUG ===\n")
                raise Exception(f"Failed to download audio media: {err}")
            
            print(f"✅ Audio download successful. Data size: {len(audio_message.data)} bytes, mime_type: {audio_message.mime_type}")
            
            # Convert audio format
            audio_message_wav = ogg_opus_to_wav_bytes(audio_message.data)
            
            # Speech to text
            audio_to_text = await speech_translator_whisper.aspeech_to_text(audio_message_wav, source_language)
            
            # Translate to English if needed
            if source_language != "en":
                translated_en_text = await text_translator.atranslate_text(
                    input_text=audio_to_text,
                    source_language=source_language,
                    target_language="en"
                )
            else:
                translated_en_text = audio_to_text
            
            message.message_context.media_info.media_type = audio_message.mime_type
        
        else:
            source_text = message.message_context.message_source_text
            
            if source_language != "en":
                translated_en_text = await text_translator.atranslate_text(
                    input_text=source_text,
                    source_language=source_language,
                    target_language="en"
                )
            else:
                translated_en_text = source_text
            
        message.message_context.message_english_text = translated_en_text
        return message

    async def handle(
        self,
        messages: List[ByoebMessageContext]
    ) -> Dict[str, Any]:
        message = None
        try:
            message = await self.__handle_process_message_workflow(messages)
        except Exception as e:
            raise e
        
        if self._successor:
            return await self._successor.handle([message])