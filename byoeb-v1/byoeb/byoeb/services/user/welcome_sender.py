import logging
import uuid
from typing import List
from byoeb_core.models.byoeb.user import User
from byoeb_core.models.byoeb.message_context import (
    ByoebMessageContext,
    MessageContext,
    MessageTypes,
    ReplyContext
)
from byoeb.services.channel.qikchat import QikchatService
from byoeb.chat_app.configuration.config import bot_config

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

    def _create_follow_up_questions_message(self, user: User) -> ByoebMessageContext:
        """Create an interactive message with common oncology questions."""
        # Get questions from bot config
        initial_questions_config = bot_config["template_messages"]["user"]["onboarding"]["initial_questions"]
        questions = initial_questions_config["questions"].get(user.user_language, initial_questions_config["questions"]["en"])
        # Use short description for button text (under 20 chars)
        if user.user_language == "hi":
            description = "प्रश्न चुनें"  # "Choose question" - 10 chars
        elif user.user_language == "kn":
            description = "ಪ್ರಶ್ನೆ ಆಯ್ಕೆ ಮಾಡಿ"  # "Choose question" - 14 chars  
        else:  # English
            description = "Choose a question"  # 17 chars
        
        # Create short button labels (max 20 chars) with full questions as descriptions
        if user.user_language == "hi":
            short_labels = ["कैंसर प्रकार", "रेडिएशन", "लक्षण"]
        elif user.user_language == "kn":
            short_labels = ["ಕ್ಯಾನ್ಸರ್", "ವಿಕಿರಣ", "ಲಕ್ಷಣಗಳು"]
        else:  # English
            short_labels = ["Cancer Types", "Radiation", "Symptoms"]
        
        # Use the short labels for buttons (all are under 20 chars)
        truncated_questions = short_labels[:3]  # Limit to 3 questions
        
        # Create interactive list additional info
        interactive_list_additional_info = {
            "description": description,
            "row_texts": truncated_questions,
            "full_questions": questions[:3],  # Store full questions for reference
            "has_follow_up_questions": True
        }
        
        # Create message context
        message_context = MessageContext(
            message_id=str(uuid.uuid4()),
            message_type=MessageTypes.INTERACTIVE_LIST.value,
            message_source_text=description,
            message_english_text=description,
            additional_info=interactive_list_additional_info
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
        """Send welcome message and follow-up questions to a newly registered user."""
        try:
            # Only send welcome messages to regular users
            if user.user_type != "byoebuser":
                self.logger.info(f"Skipping welcome message for expert user: {user.phone_number_id}")
                return True
                
            self.logger.info(f"Sending welcome message to user: {user.phone_number_id}")
            
            # Create and send welcome message
            welcome_message = self._create_welcome_message(user)
            welcome_requests = self.channel_service.prepare_requests(welcome_message)
            
            if welcome_requests:
                welcome_responses = await self.channel_service.send_requests(welcome_requests)
                self.logger.info(f"Welcome message sent to {user.phone_number_id}: {welcome_responses}")
            else:
                self.logger.warning(f"No welcome requests generated for {user.phone_number_id}")
                return False
            
            # Create and send follow-up questions message
            follow_up_message = self._create_follow_up_questions_message(user)
            follow_up_requests = self.channel_service.prepare_requests(follow_up_message)
            
            if follow_up_requests:
                follow_up_responses = await self.channel_service.send_requests(follow_up_requests)
                self.logger.info(f"Follow-up questions sent to {user.phone_number_id}: {follow_up_responses}")
                return True
            else:
                self.logger.warning(f"No follow-up requests generated for {user.phone_number_id}")
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
