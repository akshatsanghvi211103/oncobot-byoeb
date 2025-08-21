import logging
import json
from typing import List
from datetime import datetime
from byoeb_core.models.byoeb.message_context import ByoebMessageContext
from byoeb.factory.channel import ChannelClientFactory


class SimpleMessageConsumerService:
    """Simple message consumer service that works without database services."""
    
    def __init__(self, config, channel_client_factory: ChannelClientFactory):
        self._config = config
        self._logger = logging.getLogger(self.__class__.__name__)
        self._channel_client_factory = channel_client_factory
    
    async def consume(self, messages: list) -> List[ByoebMessageContext]:
        """Main method to consume messages - matches the interface of MessageConsmerService."""
        self._logger.info(f"SimpleMessageConsumerService processing {len(messages)} messages")
        
        successfully_processed_messages = []
        
        for message in messages:
            try:
                # Debug: Log what we received from the queue
                # print(f"DEBUG: Raw message from queue: {message}")
                
                # Parse the message
                json_message = json.loads(message)
                # print(f"DEBUG: Parsed JSON message: {json_message}")
                # print(f"DEBUG: JSON message user field: {json_message.get('user', 'NO USER FIELD')}")
                
                byoeb_message = ByoebMessageContext.model_validate(json_message)
                # print(f"DEBUG: Validated ByoebMessageContext: {byoeb_message}")
                # print(f"DEBUG: Validated message user: {byoeb_message.user}")
                
                # Process the message
                await self.process_message(byoeb_message)
                successfully_processed_messages.append(byoeb_message)
                
            except Exception as e:
                self._logger.error(f"Error processing message: {e}")
                # Continue with other messages
        
        self._logger.info(f"Successfully processed {len(successfully_processed_messages)} messages")
        return successfully_processed_messages
    
    async def process_message(self, message_context: ByoebMessageContext):
        """Process a single message without database operations."""
        try:
            # Debug: Log the full message context structure
            # print(f"Full message context: {message_context}")
            # print(f"Message context type: {type(message_context)}")
            # print(f"Message context dict: {message_context.model_dump() if hasattr(message_context, 'model_dump') else 'No model_dump method'}")
            
            user_id = ""
            if message_context.user:
                # print(f"User object exists: {message_context.user}")
                user_id = message_context.user.user_id if message_context.user.user_id else "unknown"
            else:
                self._logger.warning("No user object in message context")
            
            print(f"Processing message from {user_id}")
            
            # For oncology bot, directly get knowledge base response
            if message_context.channel_type == "qikchat":
                await self._process_oncology_query(message_context)
            else:
                print(f"Unsupported channel type: {message_context.channel_type}")
                
        except Exception as e:
            self._logger.error(f"Error processing message: {e}")
    
    async def _process_oncology_query(self, message_context: ByoebMessageContext):
        """Process oncology query using knowledge base."""
        try:
            # Get the user's question from message_context
            user_question = ""
            user_id = ""
            
            # Debug: Log the full message context to understand the structure
            # print(f"Message context user: {message_context.user}")
            # print(f"Message context: {message_context.message_context}")
            
            if message_context.message_context and message_context.message_context.message_english_text:
                user_question = message_context.message_context.message_english_text
            elif message_context.message_context and message_context.message_context.message_source_text:
                user_question = message_context.message_context.message_source_text
            
            # Try different possible user ID fields
            if message_context.user:
                if hasattr(message_context.user, 'user_id') and message_context.user.user_id:
                    user_id = message_context.user.user_id
                elif hasattr(message_context.user, 'phone_number_id') and message_context.user.phone_number_id:
                    user_id = message_context.user.phone_number_id
                elif hasattr(message_context.user, 'phone_number') and message_context.user.phone_number:
                    user_id = message_context.user.phone_number
            
            # print(f"Extracted user_id: '{user_id}', user_question: '{user_question}'")
            
            if not user_question:
                self._logger.warning("No message text found in message context")
                return
            
            if not user_id:
                self._logger.warning("No user ID found in message context")
                return
            
            print(f"Oncology query: {user_question}")
            
            # Query ChromaDB for accurate oncology response
            try:
                import chromadb
                import os
                
                # Connect to ChromaDB - use absolute path
                current_dir = os.path.dirname(os.path.abspath(__file__))
                # Navigate from services/chat/ to byoeb/byoeb/, then to chroma_db
                chroma_path = os.path.join(current_dir, "..", "..", "chroma_db")
                chroma_path = os.path.abspath(chroma_path)
                
                print(f"=== Trying ChromaDB path: {chroma_path} ===")
                client = chromadb.PersistentClient(path=chroma_path)
                collection = client.get_collection("oncology_kb")
                
                # Query the knowledge base with the user's question
                results = collection.query(
                    query_texts=[user_question],
                    n_results=1  # Get the most relevant answer
                )
                
                if results['documents'] and len(results['documents'][0]) > 0:
                    # Extract the answer from the ChromaDB result
                    knowledge_base_response = results['documents'][0][0]
                    
                    # Clean up the response (remove "Question: ... Answer: " format if present)
                    if "Answer:" in knowledge_base_response:
                        response_text = knowledge_base_response.split("Answer:", 1)[1].strip()
                    else:
                        response_text = knowledge_base_response
                        
                    print(f"=== CHROMADB FOUND RELEVANT ANSWER ===")
                    print(f"Similarity Score: {results['distances'][0][0] if results['distances'] else 'N/A'}")
                else:
                    response_text = "I apologize, but I couldn't find a relevant answer to your oncology question in my knowledge base. Please try rephrasing your question or consult with your healthcare provider."
                    print(f"=== NO RELEVANT ANSWER FOUND IN CHROMADB ===")
                    
            except Exception as e:
                print(f"=== CHROMADB ERROR: {e} ===")
                response_text = f"I encountered an error while searching for information about your oncology question: '{user_question}'. Please try again later or consult with your healthcare provider."
            
            print(f"=== WOULD SEND TO {user_id} ===")
            print(f"Response: {response_text}")
            print(f"=== MESSAGE SENDING DISABLED TO SAVE COSTS ===")
            return
            
            # TODO: Integrate ChromaDB for accurate oncology responses
            
            # Get the Qikchat client and send response directly
            channel_client = await self._channel_client_factory.get(message_context.channel_type)
            
            # Create the message data in Qikchat format
            # Try formatting phone number with + prefix
            formatted_user_id = f"+{user_id}" if not user_id.startswith('+') else user_id
            
            message_data = {
                "to_contact": formatted_user_id,
                "type": "text",
                "text": {
                    "body": response_text
                }
            }
            
            # print(f"Sending message data: {message_data}")
            # print(f"Original user_id: {user_id}, Formatted: {formatted_user_id}")
            
            # Send the message using the client's send_message method
            try:
                response = await channel_client.send_message(message_data)
                print(f"Sent oncology response to {formatted_user_id}, response: {response}")
            except Exception as send_error:
                print(f"Error sending message: {send_error}")
                # Try without + prefix if it failed
                if formatted_user_id.startswith('+'):
                    print("Retrying without + prefix...")
                    message_data["to_contact"] = user_id
                    response = await channel_client.send_message(message_data)
                    print(f"Retry successful, response: {response}")
                else:
                    raise
            
        except Exception as e:
            self._logger.error(f"Error processing oncology query: {e}")
            # Send error response only if we have a valid user_id
            if user_id:
                try:
                    channel_client = await self._channel_client_factory.get(message_context.channel_type)
                    error_message_data = {
                        "to_contact": user_id,
                        "type": "text",
                        "text": {
                            "body": "I'm sorry, I encountered an error processing your question. Please try again later."
                        }
                    }
                    await channel_client.send_message(error_message_data)
                        
                except Exception as send_error:
                    self._logger.error(f"Error sending error response: {send_error}")
    
    async def process_messages(self, messages: List[ByoebMessageContext]):
        """Process multiple messages."""
        self._logger.info(f"Processing {len(messages)} messages")
        
        for message_context in messages:
            await self.process_message(message_context)
