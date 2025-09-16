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
            # speech_voice="en-US-JennyNeural"  # Default voice, will be overridden per request
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
            print(f"🔧 TTS DEBUG - Starting TTS generation")
            print(f"🔧 TTS DEBUG - Input text: '{text[:100]}...' (length: {len(text)})")
            print(f"🔧 TTS DEBUG - Input language: '{language}'")
            self.logger.info(f"🔊 Generating TTS audio for text: {text[:50]}...")
            
            # Map input language to supported Azure Speech Service language codes
            # The Azure Speech Translator only supports Indian locales
            language_mapping = {
                "en": "en-IN",
                "en-US": "en-IN", 
                "en-GB": "en-IN",
                "hi": "hi-IN",
                "hi-IN": "hi-IN",
                "kn": "kn-IN", 
                "kn-IN": "kn-IN",
                "ta": "ta-IN",
                "ta-IN": "ta-IN", 
                "te": "te-IN",
                "te-IN": "te-IN"
            }
            
            mapped_language = language_mapping.get(language, "en-IN")  # Default to English-India
            print(f"🔧 TTS DEBUG - Mapped language '{language}' to '{mapped_language}'")
            
            # Select appropriate voice based on language (this is for logging purposes)
            voice = self.voice_map.get(language, "en-US-JennyNeural")
            print(f"🔧 TTS DEBUG - Selected voice: '{voice}' for language: '{language}'")
            self.logger.info(f"🎙️ Using voice: {voice} for language: {language}")
            
            print(f"🔧 TTS DEBUG - Calling speech_translator.atext_to_speech...")
            print(f"🔧 TTS DEBUG - Speech translator config - Region: {getattr(self.speech_translator, '_AsyncAzureSpeechTranslator__region', 'unknown')}")
            print(f"🔧 TTS DEBUG - Speech translator config - Resource ID: {getattr(self.speech_translator, '_AsyncAzureSpeechTranslator__resource_id', 'unknown')}")
            print(f"🔧 TTS DEBUG - Speech translator config - Has token provider: {getattr(self.speech_translator, '_AsyncAzureSpeechTranslator__token_provider', None) is not None}")
            
            # Generate audio bytes using Azure Speech Services with mapped language
            audio_bytes = await self.speech_translator.atext_to_speech(
                input_text=text,
                source_language=mapped_language  # Use mapped language instead of original
            )
            
            print(f"🔧 TTS DEBUG - Received audio_bytes: {type(audio_bytes)}, length: {len(audio_bytes) if audio_bytes else 'None'}")
            
            if not audio_bytes:
                print(f"🔧 TTS DEBUG - ERROR: No audio bytes generated!")
                self.logger.error("Failed to generate audio bytes")
                return None
                
            self.logger.info(f"✅ Generated {len(audio_bytes)} bytes of MP3 audio")
            
            # Generate unique filename with MP3 extension for QikChat compatibility
            audio_filename = f"tts_audio_{uuid.uuid4().hex}.mp3"
            
            # Upload to blob storage
            status_code, error = await self.blob_storage.aupload_bytes(
                file_name=audio_filename,
                data=audio_bytes,
                file_type=".mp3"
            )
            
            if status_code == 201:  # Created
                # TEMPORARY WORKAROUND: Try using a proxy URL for QikChat compatibility
                # Check if we have a proxy server configured
                import os
                proxy_base_url = os.environ.get("QIKCHAT_AUDIO_PROXY_URL")
                
                if proxy_base_url:
                    # Use proxy URL format: http://proxy-server/audio/filename.mp3
                    audio_url = f"{proxy_base_url.rstrip('/')}/audio/{audio_filename}"
                    self.logger.info(f"✅ Audio uploaded, using proxy URL: {audio_url}")
                else:
                    # Generate shorter SAS URL with minimal expiry for QikChat compatibility
                    audio_url = await self.blob_storage.get_blob_sas_url(audio_filename, expiry_hours=1)
                    self.logger.info(f"✅ Audio uploaded successfully with SAS URL: {audio_url}")
                
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

    async def generate_audio_data(
        self,
        text: str,
        language: str = "en-US",
    ) -> Optional[bytes]:
        """
        Generate audio from text and return raw audio data.
        Returns the audio bytes directly without uploading to blob storage.
        This is useful when the audio will be uploaded to QikChat directly.
        """
        try:
            self.logger.info(f"🔊 Generating TTS audio data for text: {text[:50]}...")
            
            # Select appropriate voice based on language
            voice = self.voice_map.get(language, "en-US-JennyNeural")
            self.logger.info(f"🎙️ Using voice: {voice} for language: {language}")
            
            # Generate audio bytes using Azure Speech Services
            audio_bytes = await self.speech_translator.atext_to_speech(
                input_text=text,
                source_language=language
            )
            
            if not audio_bytes:
                self.logger.error("Failed to generate audio bytes")
                return None
                
            self.logger.info(f"✅ Generated {len(audio_bytes)} bytes of audio data")
            return audio_bytes
                
        except Exception as e:
            self.logger.error(f"Error in generate_audio_data: {e}")
            # Add more specific error details
            import traceback
            self.logger.error(f"TTS Error Details: {traceback.format_exc()}")
            print(f"🔧 TTS Debug - text: '{text[:50]}...', language: '{language}', voice: '{voice if 'voice' in locals() else 'not_set'}'")
            return None
            
    async def generate_audio_file_url(
        self,
        text: str,
        language: str = "en-US",
        base_url: str = None
    ) -> Optional[str]:
        """
        Generate audio from text, save to local file, and return a public URL.
        This creates a temporary file that can be served by the web server.
        """
        try:
            self.logger.info(f"🔊 Generating TTS audio file for text: {text[:50]}...")
            
            # Generate audio bytes
            audio_bytes = await self.generate_audio_data(text, language)
            if not audio_bytes:
                return None
            
            # Create a temporary audio file
            import tempfile
            import os
            
            # Generate unique filename
            audio_filename = f"tts_audio_{uuid.uuid4().hex}.wav"
            
            # Create temp directory if it doesn't exist
            temp_dir = os.path.join(tempfile.gettempdir(), "oncobot_audio")
            os.makedirs(temp_dir, exist_ok=True)
            
            # Save audio file locally
            audio_file_path = os.path.join(temp_dir, audio_filename)
            with open(audio_file_path, 'wb') as f:
                f.write(audio_bytes)
            
            # For now, return a placeholder URL
            # TODO: Replace with actual web server URL when available
            if not base_url:
                base_url = "http://localhost:8000"  # Default fallback
                
            public_url = f"{base_url}/audio/{audio_filename}"
            
            self.logger.info(f"✅ Audio file saved locally: {audio_file_path}")
            self.logger.info(f"📡 Public URL would be: {public_url}")
            
            # Since we don't have a working public URL yet, return None for now
            # This will cause the system to skip audio messages gracefully
            return None
                
        except Exception as e:
            self.logger.error(f"Error in generate_audio_file_url: {e}")
            import traceback
            self.logger.error(f"TTS Error Details: {traceback.format_exc()}")
            return None
