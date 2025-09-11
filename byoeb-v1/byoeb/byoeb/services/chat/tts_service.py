import asyncio
import os
import tempfile
import uuid
from typing import Optional, Tuple
import logging
from azure.identity import DefaultAzureCredential

from byoeb_integrations.translators.speech.azure.async_azure_speech_translator import AsyncAzureSpeechTranslator
from byoeb_integrations.media_storage.azure.async_azure_blob_storage import AsyncAzureBlobStorage


class TTSService:
    def __init__(
        self,
        token_provider,
        speech_region: str,
        resource_id: str,
        blob_storage: AsyncAzureBlobStorage,
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        # Language to voice mapping for better TTS quality
        self.voice_map = {
            "en-US": "en-US-JennyNeural",
            "en": "en-US-JennyNeural", 
            "hi-IN": "hi-IN-SwaraNeural",
            "hi": "hi-IN-SwaraNeural",
            "es-ES": "es-ES-ElviraNeural",
            "es": "es-ES-ElviraNeural",
            "fr-FR": "fr-FR-DeniseNeural", 
            "fr": "fr-FR-DeniseNeural"
        }
        self.speech_translator = AsyncAzureSpeechTranslator(
            # key=speech_key,  # Use 'key' parameter instead of 'speech_key'
            region=speech_region,
            resource_id=resource_id,  # Ensure resource_id is passed here
            token_provider=token_provider,
            speech_voice="en-US-JennyNeural"  # Default voice, will be overridden per request
        )
        self.blob_storage = blob_storage
        
    async def generate_audio_url(
        self,
        text: str,
        language: str = "en-US",
    ) -> Optional[str]:
        """
        Generate audio from text and upload to Azure Blob Storage.
        Returns the public URL of the uploaded audio file.
        """
        try:
            self.logger.info(f"🔊 Generating TTS audio for text: {text[:50]}...")
            
            # Select appropriate voice based on language
            voice = self.voice_map.get(language, "en-US-JennyNeural")
            self.logger.info(f"🎙️ Using voice: {voice} for language: {language}")
            
            # Update speech translator voice for this request
            self.speech_translator.speech_voice = voice
            
            # Generate audio bytes using Azure Speech Services
            audio_bytes = await self.speech_translator.atext_to_speech(
                input_text=text,
                source_language=language
            )
            
            if not audio_bytes:
                self.logger.error("Failed to generate audio bytes")
                return None
                
            self.logger.info(f"✅ Generated {len(audio_bytes)} bytes of audio")
            
            # Generate unique filename
            audio_filename = f"tts_audio_{uuid.uuid4().hex}.wav"
            
            # Upload to blob storage
            status_code, error = await self.blob_storage.aupload_bytes(
                file_name=audio_filename,
                data=audio_bytes,
                file_type=".wav"
            )
            
            if status_code == 201:  # Created
                audio_url = self.blob_storage.get_blob_url(audio_filename)
                self.logger.info(f"✅ Audio uploaded successfully: {audio_url}")
                return audio_url
            else:
                self.logger.error(f"Failed to upload audio to blob storage: {error}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error in generate_audio_url: {e}")
            # Add more specific error details
            import traceback
            self.logger.error(f"TTS Error Details: {traceback.format_exc()}")
            print(f"🔧 TTS Debug - text: '{text[:50]}...', language: '{language}', voice: '{voice if 'voice' in locals() else 'not_set'}'")
            return None
            
    async def cleanup_old_audio_files(self, max_age_hours: int = 24):
        """
        Clean up old audio files from blob storage to save space.
        This could be called periodically.
        """
        try:
            # Implementation for cleanup would go here
            # For now, we'll keep all files
            pass
        except Exception as e:
            self.logger.error(f"Error cleaning up audio files: {e}")
