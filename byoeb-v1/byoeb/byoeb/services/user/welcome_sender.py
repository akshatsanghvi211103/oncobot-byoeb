import logging
from typing import List
from byoeb_core.models.byoeb.user import User
from byoeb_core.models.byoeb.message_context import (
    ByoebMessageContext,
    MessageContext,
    MessageTypes
)
from byoeb.services.channel.qikchat import QikchatService

class WelcomeMessageSender:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.channel_service = QikchatService()
        
    def _create_welcome_message(self, user: User) -> ByoebMessageContext:
        """Create a welcome message for the user."""
        # Get welcome message in user's language
        welcome_messages = {
            "en": "Welcome to OncoBot! 🌟\n\nI'm here to help you with oncology-related questions. Feel free to ask me anything about cancer care, treatments, or procedures.\n\nYou can ask questions in English, Hindi, or Kannada.",
            "hi": "ऑन्कोबॉट में आपका स्वागत है! 🌟\n\nमैं ऑन्कोलॉजी संबंधी प्रश्नों में आपकी सहायता के लिए यहाँ हूँ। कैंसर की देखभाल, उपचार या प्रक्रियाओं के बारे में मुझसे कुछ भी पूछने में संकोच न करें।\n\nआप अंग्रेजी, हिंदी या कन्नड़ में प्रश्न पूछ सकते हैं।",
            "kn": "ಆಂಕೋಬಾಟ್‌ಗೆ ಸ್ವಾಗತ! 🌟\n\nಆಂಕಾಲಜಿ ಸಂಬಂಧಿತ ಪ್ರಶ್ನೆಗಳಲ್ಲಿ ನಿಮಗೆ ಸಹಾಯ ಮಾಡಲು ನಾನು ಇಲ್ಲಿದ್ದೇನೆ. ಕ್ಯಾನ್ಸರ್ ಆರೈಕೆ, ಚಿಕಿತ್ಸೆಗಳು ಅಥವಾ ಕಾರ್ಯವಿಧಾನಗಳ ಬಗ್ಗೆ ನನ್ನನ್ನು ಏನು ಬೇಕಾದರೂ ಕೇಳಿ।\n\nನೀವು ಇಂಗ್ಲಿಷ್, ಹಿಂದಿ ಅಥವಾ ಕನ್ನಡದಲ್ಲಿ ಪ್ರಶ್ನೆಗಳನ್ನು ಕೇಳಬಹುದು।"
        }
        
        welcome_text = welcome_messages.get(user.user_language, welcome_messages["en"])
        
        # Create message context
        message_context = MessageContext(
            message_type=MessageTypes.REGULAR_TEXT.value,
            message_source_text=welcome_text,
            message_english_text=welcome_text
        )
        
        # Create ByoebMessageContext
        byoeb_message = ByoebMessageContext(
            channel_type="qikchat",
            message_category="notification",
            user=user,
            message_context=message_context
        )
        
        return byoeb_message
    
    async def send_welcome_message(self, user: User) -> bool:
        """Send welcome message to a newly registered user."""
        try:
            # Only send welcome messages to regular users
            if user.user_type != "byoebuser":
                self.logger.info(f"Skipping welcome message for expert user: {user.phone_number_id}")
                return True
                
            self.logger.info(f"Sending welcome message to user: {user.phone_number_id}")
            
            # Create welcome message
            welcome_message = self._create_welcome_message(user)
            
            # Prepare requests for Qikchat
            requests = self.channel_service.prepare_requests(welcome_message)
            
            # Send the messages
            if requests:
                responses = await self.channel_service.send_requests(requests)
                self.logger.info(f"Welcome message sent to {user.phone_number_id}: {responses}")
                return True
            else:
                self.logger.warning(f"No requests generated for welcome message to {user.phone_number_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error in send_welcome_message for {user.phone_number_id}: {e}")
            return False
    
    async def send_welcome_messages(self, users: List[User]) -> bool:
        """Send welcome messages to multiple newly registered users."""
        success_count = 0
        for user in users:
            if await self.send_welcome_message(user):
                success_count += 1
        
        self.logger.info(f"Sent welcome messages to {success_count}/{len(users)} users")
        return success_count == len(users)
