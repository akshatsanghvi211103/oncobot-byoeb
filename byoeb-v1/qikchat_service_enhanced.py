"""
BYOeB Qikchat Service with 24-Hour Template Logic
Updated to handle WhatsApp Business API 24-hour rule
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import byoeb.services.chat.constants as constants
import byoeb.services.chat.utils as utils
import byoeb_integrations.channel.qikchat.request_payload as qik_req_payload
from byoeb.services.channel.base import BaseChannelService, MessageReaction
from byoeb_core.models.byoeb.message_context import (
    User,
    ByoebMessageContext,
    MessageContext,
    ReplyContext,
    MediaContext,
    MessageTypes
)

class QikchatServiceWithTemplates(BaseChannelService):
    """
    Enhanced Qikchat service with 24-hour rule and template support
    """
    __client_type = "qikchat"
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        # Track last interaction times to enforce 24-hour rule
        self.last_user_interactions = {}
        
    def _is_within_24_hour_window(self, phone_number: str) -> bool:
        """
        Check if we're within 24-hour window for free-form messages
        """
        if phone_number not in self.last_user_interactions:
            return False
            
        last_interaction = self.last_user_interactions[phone_number]
        now = datetime.now()
        time_diff = now - last_interaction
        
        return time_diff < timedelta(hours=24)
    
    def _update_user_interaction_time(self, phone_number: str):
        """
        Update the last interaction time when user sends a message
        """
        self.last_user_interactions[phone_number] = datetime.now()
        self.logger.info(f"Updated interaction time for {phone_number}")
    
    def _should_use_template(self, phone_number: str) -> bool:
        """
        Determine if we should use a template message (24+ hours since last interaction)
        """
        return not self._is_within_24_hour_window(phone_number)
    
    def prepare_oncology_response(
        self,
        user_message: str,
        phone_number: str,
        kb_response: str
    ) -> Dict[str, Any]:
        """
        Prepare oncology bot response based on 24-hour rule
        """
        # Check if we need to use template
        if self._should_use_template(phone_number):
            self.logger.info(f"Using template for re-engagement: {phone_number}")
            
            # Use template for re-engagement
            template_message = {
                "to_contact": phone_number,
                "type": "template",
                "template": {
                    "name": "testing",  # Use your approved template
                    "language": "en",
                    "components": []
                }
            }
            return template_message
        else:
            self.logger.info(f"Using free-form message within 24h window: {phone_number}")
            
            # Use free-form message with oncology response
            oncology_message = {
                "to_contact": phone_number,
                "type": "text",
                "text": {
                    "body": f"🏥 **BYOeB Oncology Assistant**\n\n{kb_response}\n\n📋 Do you have any other questions about cancer treatment or care?"
                }
            }
            return oncology_message
    
    def prepare_requests(
        self,
        byoeb_message_contexts: List[ByoebMessageContext]
    ) -> List[Dict[str, Any]]:
        """
        Enhanced prepare_requests with template logic
        """
        requests = []
        
        for context in byoeb_message_contexts:
            phone_number = context.user.phone_number
            
            # Update interaction time when we receive a user message
            if context.message_context.message_type == MessageTypes.TEXT:
                self._update_user_interaction_time(phone_number)
            
            # Prepare response based on context
            if hasattr(context, 'oncology_response'):
                # This is an oncology bot response
                user_message = context.message_context.message_body
                kb_response = context.oncology_response
                
                request = self.prepare_oncology_response(
                    user_message, phone_number, kb_response
                )
                requests.append(request)
                
            else:
                # Regular message processing
                message_context = context.message_context
                
                if message_context.message_type == MessageTypes.TEXT:
                    if self._should_use_template(phone_number):
                        # Use template for re-engagement
                        request = {
                            "to_contact": phone_number,
                            "type": "template",
                            "template": {
                                "name": "testing",
                                "language": "en", 
                                "components": []
                            }
                        }
                    else:
                        # Use free-form text message
                        request = qik_req_payload.get_qikchat_text_request(
                            phone_number,
                            message_context.message_body
                        )
                    requests.append(request)
                
                elif message_context.message_type == MessageTypes.INTERACTIVE:
                    # Interactive messages only if within 24h window
                    if not self._should_use_template(phone_number):
                        request = qik_req_payload.get_qikchat_interactive_request(
                            phone_number,
                            message_context.interactive_message
                        )
                        requests.append(request)
                    else:
                        # Fall back to template
                        request = {
                            "to_contact": phone_number,
                            "type": "template",
                            "template": {
                                "name": "testing",
                                "language": "en",
                                "components": []
                            }
                        }
                        requests.append(request)
        
        return requests
    
    def prepare_reaction_requests(
        self,
        message_reactions: List[MessageReaction]
    ) -> List[Dict[str, Any]]:
        """
        Prepare reaction requests - only if within 24h window
        """
        reactions = []
        for message_reaction in message_reactions:
            phone_number = message_reaction.phone_number_id
            
            # Only send reactions within 24h window
            if not self._should_use_template(phone_number):
                reaction_request = qik_req_payload.get_qikchat_reaction_request(
                    phone_number,
                    message_reaction.message_id,
                    message_reaction.reaction
                )
                reactions.append(reaction_request)
            else:
                self.logger.warning(f"Skipping reaction for {phone_number} - outside 24h window")
        
        return reactions

    async def send_requests(self, requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Send requests using Qikchat client
        """
        from byoeb_integrations.channel.qikchat.qikchat_client import QikchatClient
        
        client = QikchatClient()
        responses = []
        
        for request in requests:
            try:
                response = await client.send_message(request)
                responses.append(response)
                
                # Log template vs free-form usage
                if request.get('type') == 'template':
                    self.logger.info(f"Sent template message: {response.get('data', [{}])[0].get('id')}")
                else:
                    self.logger.info(f"Sent free-form message: {response.get('data', [{}])[0].get('id')}")
                    
            except Exception as e:
                self.logger.error(f"Failed to send request: {str(e)}")
                responses.append({"error": str(e)})
        
        return responses

    def create_conv(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create conversation context from Qikchat webhook data
        """
        try:
            # Extract phone number and message
            phone_number = message_data.get('from', '')
            message_body = message_data.get('text', {}).get('body', '')
            
            # Update interaction time when receiving user message
            if phone_number and message_body:
                self._update_user_interaction_time(phone_number)
            
            # Create conversation context
            conv_data = {
                "user_phone": phone_number,
                "message": message_body,
                "timestamp": datetime.now().isoformat(),
                "within_24h_window": self._is_within_24_hour_window(phone_number)
            }
            
            return conv_data
            
        except Exception as e:
            self.logger.error(f"Error creating conversation: {str(e)}")
            return {"error": str(e)}

# Example usage for testing
async def test_template_logic():
    """
    Test the template logic locally
    """
    service = QikchatServiceWithTemplates()
    
    # Simulate scenarios
    test_phone = "919739811075"
    
    print("🧪 Testing Template Logic")
    print("=" * 40)
    
    # Test 1: First contact (should use template)
    print("📱 Test 1: First contact")
    should_template = service._should_use_template(test_phone)
    print(f"   Should use template: {should_template}")
    
    # Test 2: User sends message (updates interaction time)
    print("📱 Test 2: User sends message")
    service._update_user_interaction_time(test_phone)
    should_template = service._should_use_template(test_phone)
    print(f"   Should use template: {should_template}")
    
    # Test 3: Bot response within 24h
    print("📱 Test 3: Bot responds to oncology question")
    response = service.prepare_oncology_response(
        "What are side effects of radiotherapy?",
        test_phone,
        "Common side effects include skin irritation and fatigue..."
    )
    print(f"   Response type: {response.get('type')}")
    if response.get('type') == 'text':
        print(f"   Message preview: {response['text']['body'][:50]}...")
    
    print("\n✅ Template logic test complete!")

if __name__ == "__main__":
    asyncio.run(test_template_logic())
