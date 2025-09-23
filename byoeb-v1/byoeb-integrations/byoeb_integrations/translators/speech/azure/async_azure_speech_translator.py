from typing import Any
import azure.cognitiveservices.speech as speechsdk
from byoeb_core.translators.speech.base import BaseSpeechTranslator

class AsyncAzureSpeechTranslator(BaseSpeechTranslator):
    __voice_dict = {
        "male": {
            "en-IN": "en-IN-PrabhatNeural",
            "hi-IN": "hi-IN-MadhurNeural",
            "kn-IN": "kn-IN-GaganNeural",
            "ta-IN": "ta-IN-ValluvarNeural",
            "te-IN": "te-IN-MohanNeural",
        },
        "female": {
            "en-IN": "en-IN-NeerjaNeural",
            "hi-IN": "hi-IN-SwaraNeural",
            "kn-IN": "kn-IN-SapnaNeural",
            "ta-IN": "ta-IN-PallaviNeural",
            "te-IN": "te-IN-ShrutiNeural",
        },
    }
    def __init__(self,
        region,
        key=None,
        token_provider=None,
        resource_id=None,
        speech_voice: str = "female",
        country_code: str = "IN",
        **kwargs
    ):
        if region is None:
            raise ValueError("region must be provided")
        if token_provider is None and key is None:
            raise ValueError("Either token_provider or key must be provided with region")
        print("cool", resource_id, "bruh", token_provider, "nice")
        if token_provider is not None and resource_id is None:
            raise ValueError("resource_id must be provided with token_provider")
        self.__key = key
        self.__region = region
        self.__speech_voice = speech_voice
        self.__token_provider = token_provider
        self.__resource_id = resource_id
        self.__country_code = f"-{country_code.upper()}"

    def speech_to_text(
        self,
        audio_file: str,
        source_language: str, 
        **kwargs
    ) -> Any:
        raise NotImplementedError
    
    async def aspeech_to_text(
        self,
        audio_data: bytes,
        source_language: str,
        **kwargs
    ) -> str:
        speech_config = self.__get_speech_config()
        speech_config.speech_recognition_language =  f"{source_language}-IN"
        # Create a push stream
        push_stream = speechsdk.audio.PushAudioInputStream()
        audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

        # Create speech recognizer with audio stream
        speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config, audio_config=audio_config
        )
        try:
            # Push audio bytes to the stream
            push_stream.write(audio_data)
            push_stream.close()

            # Perform speech recognition
            result = speech_recognizer.recognize_once_async().get()
            return result.text
        except Exception as e:
            raise RuntimeError(f"Error in speech recognition: {e}")
        
    def text_to_speech(
        self,
        input_text: str,
        source_language: str,
        **kwargs
    ) -> Any:
        raise NotImplementedError

    async def atext_to_speech(
        self,
        input_text: str,
        source_language: str,
        **kwargs
    ) -> bytes:
        try:
            print(f"🔧 SPEECH DEBUG - Starting TTS synthesis")
            print(f"🔧 SPEECH DEBUG - Input text: '{input_text[:100]}...' (length: {len(input_text)})")
            print(f"🔧 SPEECH DEBUG - Source language: '{source_language}'")
            print(f"🔧 SPEECH DEBUG - Speech voice: '{self.__speech_voice}'")
            print(f"🔧 SPEECH DEBUG - Country code: '{self.__country_code}'")
            # self.logger.info(f"🔊 Generating TTS audio for text: {input_text[:50]}...")
            
            speech_config = self.__get_speech_config()
            print(f"🔧 SPEECH DEBUG - Got speech config")
            
            # Build the voice key
            voice_key = source_language + self.__country_code
            print(f"🔧 SPEECH DEBUG - Voice key: '{voice_key}'")
            print(f"🔧 SPEECH DEBUG - Available voices in dict: {list(self.__voice_dict.get(self.__speech_voice, {}).keys())}")
            
            if self.__speech_voice not in self.__voice_dict:
                print(f"🔧 SPEECH DEBUG - ERROR: Speech voice '{self.__speech_voice}' not found in voice dict")
                raise ValueError(f"Speech voice '{self.__speech_voice}' not found")
            
            if voice_key not in self.__voice_dict[self.__speech_voice]:
                print(f"🔧 SPEECH DEBUG - ERROR: Voice key '{voice_key}' not found for speech voice '{self.__speech_voice}'")
                print(f"🔧 SPEECH DEBUG - Available keys: {list(self.__voice_dict[self.__speech_voice].keys())}")
                raise ValueError(f"Voice key '{voice_key}' not found for speech voice '{self.__speech_voice}'")
            
            selected_voice = self.__voice_dict[self.__speech_voice][voice_key]
            print(f"🔧 SPEECH DEBUG - Selected voice: '{selected_voice}'")
            
            speech_config.speech_synthesis_voice_name = selected_voice
            print(f"🔧 SPEECH DEBUG - Set voice name in config")
            
            # Set output format to MP3 for QikChat compatibility (48KHz 96KBitRate)
            speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Audio48Khz96KBitRateMonoMp3)
            print(f"🔧 SPEECH DEBUG - Set output format to MP3")
            # self.logger.info(f"🔧 SPEECH DEBUG - Set output format to MP3")

            # Create a pull audio output stream
            pull_stream = speechsdk.audio.PullAudioOutputStream()
            print(f"🔧 SPEECH DEBUG - Created pull stream")

            # Configure the audio output to use the pull stream
            audio_config = speechsdk.audio.AudioOutputConfig(stream=pull_stream)
            print(f"🔧 SPEECH DEBUG - Created audio config")

            # Create the speech synthesizer
            speech_synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=speech_config, audio_config=audio_config
            )
            print(f"🔧 SPEECH DEBUG - Created speech synthesizer")

            # Perform text-to-speech synthesis
            print(f"🔧 SPEECH DEBUG - Starting synthesis...")
            result = speech_synthesizer.speak_text_async(input_text).get()
            print(f"🔧 SPEECH DEBUG - Synthesis completed")
            print(f"🔧 SPEECH DEBUG - Result reason: {result.reason}")
            print(f"🔧 SPEECH DEBUG - Result audio data length: {len(result.audio_data) if result.audio_data else 'None'}")
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                audio_bytes: bytes = result.audio_data
                print(f"🔧 SPEECH DEBUG - SUCCESS: Generated {len(audio_bytes)} bytes of audio")
                return audio_bytes
            elif result.reason == speechsdk.ResultReason.Canceled:
                # Handle cancellation more safely
                print(f"🔧 SPEECH DEBUG - ERROR: Speech synthesis canceled")
                try:
                    # Try to get error details from the result properties
                    error_details = getattr(result, 'error_details', 'No error details available')
                    print(f"🔧 SPEECH DEBUG - ERROR: Error details: {error_details}")
                    raise RuntimeError(f"Speech synthesis canceled - {error_details}")
                except Exception as detail_error:
                    print(f"🔧 SPEECH DEBUG - ERROR: Could not get cancellation details: {detail_error}")
                    raise RuntimeError(f"Speech synthesis canceled - unable to get error details")
            else:
                print(f"🔧 SPEECH DEBUG - ERROR: Unexpected result reason: {result.reason}")
                # Try to get any available error information
                error_info = getattr(result, 'error_details', f'Unknown error with reason: {result.reason}')
                print(f"🔧 SPEECH DEBUG - ERROR: Additional info: {error_info}")
                raise RuntimeError(f"Unexpected synthesis result: {result.reason} - {error_info}")
                
        except Exception as e:
            print(f"🔧 SPEECH DEBUG - EXCEPTION in atext_to_speech: {type(e).__name__}: {e}")
            import traceback
            print(f"🔧 SPEECH DEBUG - Traceback: {traceback.format_exc()}")
            raise RuntimeError(f"Error in text-to-speech: {e}")
    
    def __get_speech_config(self):
        print(f"🔧 AUTH DEBUG - Getting speech config...")
        print(f"🔧 AUTH DEBUG - Region: '{self.__region}'")
        print(f"🔧 AUTH DEBUG - Has token provider: {self.__token_provider is not None}")
        print(f"🔧 AUTH DEBUG - Has key: {self.__key is not None}")
        print(f"🔧 AUTH DEBUG - Resource ID: '{self.__resource_id}'")
        
        if self.__token_provider is not None:
            try:
                print(f"🔧 AUTH DEBUG - Using token provider authentication")
                token = self.__token_provider()
                print(f"🔧 AUTH DEBUG - Got token from provider (length: {len(token) if token else 'None'})")
                auth_token = "aad#" + self.__resource_id + "#" + token
                print(f"🔧 AUTH DEBUG - Built auth token (length: {len(auth_token)})")
                config = speechsdk.SpeechConfig(
                    auth_token=auth_token, region=self.__region
                )
                print(f"🔧 AUTH DEBUG - Created SpeechConfig with token auth")
                return config
            except Exception as e:
                print(f"🔧 AUTH DEBUG - ERROR getting token: {type(e).__name__}: {e}")
                raise
        else:
            print(f"🔧 AUTH DEBUG - Using key authentication")
            if not self.__key:
                print(f"🔧 AUTH DEBUG - ERROR: No key provided!")
                raise ValueError("No authentication key provided")
            config = speechsdk.SpeechConfig(
                subscription=self.__key, region=self.__region
            )
            print(f"🔧 AUTH DEBUG - Created SpeechConfig with key auth")
            return config
    def change_speech_voice(
        self,
        speech_voice: str
    ):
        self.__speech_voice = speech_voice

    def change_voice_dict(
        self,
        voice_dict: dict
    ):
        self.__voice_dict = voice_dict