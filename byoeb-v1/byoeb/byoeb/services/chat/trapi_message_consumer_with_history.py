import logging
import json
from typing import List, Optional
from datetime import datetime
from byoeb_core.models.byoeb.message_context import ByoebMessageContext
from byoeb.factory.channel import ChannelClientFactory

# TRAPI imports
from openai import AsyncAzureOpenAI
from azure.identity import ChainedTokenCredential, AzureCliCredential, ManagedIdentityCredential, get_bearer_token_provider

# Database imports for conversation history
from byoeb.services.databases.mongo_db import UserMongoDBService, MessageMongoDBService
from byoeb_core.models.byoeb.user import User


class TRAPIMessageConsumerServiceWithHistory:
    """Enhanced TRAPI message consumer with conversation history tracking."""
    
    def __init__(
        self, 
        config, 
        channel_client_factory: ChannelClientFactory,
        user_db_service: Optional[UserMongoDBService] = None,
        message_db_service: Optional[MessageMongoDBService] = None,
        speech_translator=None,
        text_translator=None
    ):
        self._config = config
        self._logger = logging.getLogger(self.__class__.__name__)
        self._channel_client_factory = channel_client_factory
        self._user_db_service = user_db_service
        self._message_db_service = message_db_service
        self._speech_translator = speech_translator
        self._text_translator = text_translator
        
        # Initialize TRAPI clients
        self._setup_trapi_clients()
        
        # Initialize knowledge base search
        self._setup_knowledge_base()
    
    def _setup_trapi_clients(self):
        """Setup TRAPI clients for LLM and embeddings."""
        scope = "api://trapi/.default"
        credential = get_bearer_token_provider(
            ChainedTokenCredential(
                AzureCliCredential(),
                ManagedIdentityCredential(),
            ),
            scope,
        )
        
        api_version = '2024-12-01-preview'
        instance = 'gcr/shared'
        
        # Setup O3 client for text generation
        o3_deployment_name = 'o3_2025-04-16'
        o3_endpoint = f'https://trapi.research.microsoft.com/{instance}/openai/deployments/{o3_deployment_name}'
        
        token = credential()
        self.o3_client = AsyncAzureOpenAI(
            api_key=token,
            base_url=o3_endpoint,
            api_version=api_version,
        )
        
        # Setup embedding client for text-embedding-3-large_1
        embedding_deployment_name = 'text-embedding-3-large_1'
        embedding_endpoint = f'https://trapi.research.microsoft.com/{instance}/openai/deployments/{embedding_deployment_name}'
        
        self.embedding_client = AsyncAzureOpenAI(
            api_key=token,
            base_url=embedding_endpoint,
            api_version=api_version,
        )
        
        self._logger.info("TRAPI clients initialized successfully")
    
    def _setup_knowledge_base(self):
        """Setup knowledge base search clients."""
        try:
            from azure.search.documents.aio import SearchClient
            from azure.identity import AzureCliCredential
            import os
            
            search_endpoint = "https://byoeb-search.search.windows.net"
            # Use Azure CLI credential for consistency with working implementation
            credential = AzureCliCredential()
            
            # Initialize single search client for unified index containing all 3 KBs
            self.search_client = SearchClient(
                endpoint=search_endpoint,
                index_name="oncobot_index",  # Unified index with all KBs
                credential=credential
            )
            
            self._logger.info("Knowledge base search clients initialized")
            
        except Exception as e:
            self._logger.error(f"Failed to setup knowledge base: {e}")
    
    async def consume(self, messages: list) -> List[ByoebMessageContext]:
        """Main method to consume messages with conversation history."""
        self._logger.info(f"TRAPIMessageConsumerService processing {len(messages)} messages")
        
        successfully_processed_messages = []
        
        for message in messages:
            try:
                # Parse the message
                json_message = json.loads(message)
                byoeb_message = ByoebMessageContext.model_validate(json_message)
                
                # Process the message with conversation history
                await self.process_message_with_history(byoeb_message)
                successfully_processed_messages.append(byoeb_message)
                
            except Exception as e:
                self._logger.error(f"Error processing message: {e}")
                # Continue with other messages
        
        # Save conversation history to database
        if self._user_db_service and self._message_db_service:
            await self._save_conversation_history(successfully_processed_messages)
        
        self._logger.info(f"Successfully processed {len(successfully_processed_messages)} messages")
        return successfully_processed_messages
    
    async def process_message_with_history(self, message_context: ByoebMessageContext):
        """Process a single message with conversation history context."""
        try:
            user_id = ""
            if message_context.user:
                user_id = message_context.user.user_id if message_context.user.user_id else "unknown"
            else:
                self._logger.warning("No user object in message context")
                user_id = "unknown"
            
            # Get user's conversation history
            conversation_history = await self._get_conversation_history(user_id)
            
            # Handle voice messages
            user_text = await self._handle_voice_message(message_context)
            if not user_text:
                user_text = message_context.message_context.message_source_text
            
            print(f"🔤 User Input: {user_text}")
            
            # Search knowledge bases
            kb_context = await self._search_knowledge_bases(user_text)
            print(f"📚 KB Search Results: {len(kb_context.split()) if kb_context else 0} words found")
            
            # Generate response with conversation history context
            response = await self._generate_response_with_history(
                user_text, 
                kb_context, 
                conversation_history
            )
            
            print(f"🤖 Bot Response: {response[:100]}{'...' if len(response) > 100 else ''}")
            print(f"📏 Full Response Length: {len(response)} characters")
            
            # Update message context with response
            message_context.message_context.message_english_text = response
            
            # Safely update additional_info if it exists
            if message_context.reply_context and hasattr(message_context.reply_context, 'additional_info'):
                if not message_context.reply_context.additional_info:
                    message_context.reply_context.additional_info = {}
                message_context.reply_context.additional_info["kb_search_performed"] = True
                message_context.reply_context.additional_info["conversation_history_used"] = len(conversation_history) > 0
                message_context.reply_context.additional_info["timestamp"] = str(int(datetime.now().timestamp()))
            else:
                self._logger.warning("reply_context or additional_info not available for updating metadata")
            
            # NOTE: Message sending is disabled to prevent echoing user messages
            # await self._send_response(message_context, response)
            print("Message sending disabled - bot will not echo user messages")
            
            # Store conversation history using the existing byoeb system
            await self._store_conversation_history_existing_system(user_id, user_text, response)
            
            self._logger.info(f"Processed message for user {user_id} with conversation history")
            
        except Exception as e:
            self._logger.error(f"Error in process_message_with_history: {e}")
            # Send a fallback response
            # NOTE: Message sending is disabled to prevent echoing
            # await self._send_fallback_response(message_context)
            print("Error processing message, but message sending disabled to prevent echoing")

    async def _store_conversation_history_existing_system(self, user_id: str, user_question: str, bot_response: str):
        """Store conversation history using the existing byoeb system (same as user_flow_handlers/send.py)."""
        try:
            if not self._user_db_service:
                self._logger.warning("User database service not available - skipping conversation history storage")
                return
            
            print(f"💾 Storing conversation: Q: '{user_question[:50]}...', A: '{bot_response[:50]}...'")
            
            # Import constants to use the exact same format as the existing system
            from byoeb.services.chat import constants
            
            # Get the user first, or create if doesn't exist
            users = await self._user_db_service.get_users([user_id])
            if not users:
                print(f"👤 User {user_id} not found - creating new user")
                # Create a new user with minimal required data
                new_user = User(
                    user_id=user_id,
                    user_name="Unknown User",  # Will be updated when user info is available
                    phone_number_id="",
                    experts={"medical": ["918904954952"], "logistical": []},
                    created_timestamp=int(datetime.now().timestamp()),
                    activity_timestamp=int(datetime.now().timestamp()),
                    last_conversations=[]  # Start with empty conversation history
                )
                
                # Create user in database
                user_create_data = {
                    "_id": user_id,
                    "User": new_user.model_dump()
                }
                create_queries = {constants.CREATE: [user_create_data]}
                await self._user_db_service.execute_queries(create_queries)
                print(f"✅ Created new user {user_id}")
                
                # Use the newly created user
                user = new_user
            else:
                user = users[0]
                print(f"✅ Found existing user {user_id}")
            
            # Create Q&A pair in the EXACT same format as the existing system
            qa = {
                constants.QUESTION: user_question,
                constants.ANSWER: bot_response
            }
            
            # Use the existing user_activity_update_query method
            update_query = self._user_db_service.user_activity_update_query(user, qa)
            
            # Execute the update query using the exact same format as send.py
            user_db_queries = {constants.UPDATE: [update_query]}
            await self._user_db_service.execute_queries(user_db_queries)
            
            # IMPORTANT: Invalidate user cache so next retrieval gets fresh data
            await self._user_db_service.invalidate_user_cache(user_id)
            
            print(f"✅ Conversation history stored successfully for user {user_id}")
            self._logger.info(f"Stored conversation history for user {user_id} using existing byoeb system")
            
        except Exception as e:
            print(f"❌ Error storing conversation history: {e}")
            self._logger.error(f"Error storing conversation history: {e}")
    
    async def _get_conversation_history(self, user_id: str) -> List[dict]:
        """Retrieve user's conversation history from database with Azure Cosmos DB compatibility."""
        print(f"🔍 Retrieving conversation history for user: {user_id}")
        
        if not self._user_db_service:
            print("❌ No user database service available")
            return []

        try:
            # Get user activity and check if user exists
            print(f"📞 Checking user activity for: {user_id}")
            activity_result = await self._user_db_service.get_user_activity_timestamp(user_id)
            
            if activity_result is None:
                print(f"⚠️ User {user_id} doesn't exist in database - no conversation history")
                return []
            
            print(f"✅ User activity found: {activity_result}")
            
            # Safely unpack the result - Azure Cosmos DB may return different formats
            activity_timestamp = None
            cached = False
            
            if isinstance(activity_result, tuple):
                if len(activity_result) >= 2:
                    activity_timestamp, cached = activity_result
                elif len(activity_result) == 1:
                    activity_timestamp = activity_result[0]
            else:
                activity_timestamp = activity_result
            
            print(f"🕐 Activity timestamp: {activity_timestamp}, Cached: {cached}")
            
            if activity_timestamp is None:
                print(f"⚠️ No activity timestamp for user {user_id}")
                return []
            
            # Get the user to access conversation history
            print(f"📞 Getting user data for: {user_id} (fresh from DB to ensure latest conversations)")
            users = await self._user_db_service.get_users([user_id])
            if not users:
                print(f"⚠️ User {user_id} not found in get_users")
                return []
            
            user = users[0]
            conversation_history = user.last_conversations or []
            print(f"📚 Found {len(conversation_history)} conversations in user.last_conversations")
            print(f"📚 Raw conversation history: {conversation_history}")
            
            # Validate conversation history format for Azure Cosmos DB compatibility
            validated_history = []
            # Import constants to use the exact same format as the existing system
            from byoeb.services.chat import constants
            
            for i, conv in enumerate(conversation_history):
                print(f"  Conv {i+1}: {type(conv)} - {conv}")
                # Check for both formats: constants.QUESTION/ANSWER and lowercase strings for backward compatibility
                if isinstance(conv, dict) and (
                    (constants.QUESTION in conv and constants.ANSWER in conv) or
                    ('question' in conv and 'answer' in conv)
                ):
                    # Normalize to lowercase format for internal use
                    normalized_conv = {
                        'question': conv.get(constants.QUESTION) or conv.get('question', ''),
                        'answer': conv.get(constants.ANSWER) or conv.get('answer', '')
                    }
                    validated_history.append(normalized_conv)
                    q_text = normalized_conv['question'][:50] if normalized_conv['question'] else 'No question'
                    print(f"    ✅ Valid conversation: Q: {q_text}...")
                else:
                    print(f"    ❌ Invalid conversation format: {type(conv)}")
                    self._logger.warning(f"Invalid conversation format skipped: {type(conv)}")
            
            print(f"📊 Retrieved {len(validated_history)} valid conversations for user {user_id}")
            self._logger.info(f"Retrieved {len(validated_history)} valid conversations for user {user_id}")
            return validated_history
            
        except Exception as e:
            print(f"❌ Error getting conversation history for {user_id}: {e}")
            self._logger.error(f"Error getting conversation history for {user_id}: {e}")
            # Log additional context for Azure Cosmos DB debugging
            if "delegate" in str(e) or "__delegate_class__" in str(e):
                self._logger.error("Azure Cosmos DB compatibility issue detected - check MongoDB driver version and connection")
            return []

    async def _save_conversation_history(self, processed_messages: List[ByoebMessageContext]):
        """Save processed messages to conversation history with Azure Cosmos DB compatibility."""
        if not self._user_db_service or not self._message_db_service:
            return
        
        try:
            user_updates = []
            message_creates = []
            
            for message in processed_messages:
                if not message.user:
                    continue
                
                user_id = message.user.user_id
                
                # Create conversation entry - ensure Azure Cosmos DB compatibility
                conversation_entry = {
                    "question": str(message.message_context.message_source_text or ""),
                    "answer": str(message.message_context.message_english_text or ""),
                    "timestamp": int(datetime.now().timestamp()),
                    "conversation_id": str(message.message_context.message_id or "")
                }
                
                # Get current user to update conversation history
                try:
                    users = await self._user_db_service.get_users([user_id])
                    if users:
                        user = users[0]
                        
                        # Create user activity update query with conversation
                        update_query = self._user_db_service.user_activity_update_query(user, conversation_entry)
                        user_updates.append(update_query)
                    else:
                        # Create new user if doesn't exist - Azure Cosmos DB compatible format
                        new_user = User(
                            user_id=user_id,
                            user_name=str(message.user.user_name or "Unknown User"),
                            phone_number_id=str(message.user.phone_number_id or ""),
                            experts={"medical": ["918904954952"], "logistical": []},
                            created_timestamp=int(datetime.now().timestamp()),
                            activity_timestamp=int(datetime.now().timestamp()),
                            last_conversations=[conversation_entry]
                        )
                        
                        user_create_data = {
                            "_id": user_id,
                            "User": new_user.model_dump()
                        }
                        user_updates.append(({"_id": user_id}, {"$set": user_create_data}, {"upsert": True}))
                    
                except Exception as user_error:
                    self._logger.error(f"Error processing user {user_id}: {user_error}")
                    continue
                
                # Create message storage with error handling
                try:
                    message_creates.extend(self._message_db_service.message_create_queries([message]))
                except Exception as message_error:
                    self._logger.error(f"Error creating message query: {message_error}")
            
            # Execute database updates with Azure Cosmos DB error handling
            if user_updates:
                try:
                    await self._user_db_service.execute_queries({"update": user_updates})
                    self._logger.info(f"Saved conversation history for {len(user_updates)} users")
                except Exception as e:
                    self._logger.error(f"Error saving user updates: {e}")
                    # Check for Azure Cosmos DB specific errors
                    if "delegate" in str(e) or "__delegate_class__" in str(e):
                        self._logger.error("Azure Cosmos DB delegate error - check connection and compatibility")
            
            if message_creates:
                try:
                    await self._message_db_service.execute_queries({"create": message_creates})
                    self._logger.info(f"Saved {len(message_creates)} messages to database")
                except Exception as e:
                    self._logger.error(f"Error saving messages: {e}")
                    # Check for Azure Cosmos DB specific errors
                    if "delegate" in str(e) or "__delegate_class__" in str(e):
                        self._logger.error("Azure Cosmos DB delegate error - check connection and compatibility")
                
        except Exception as e:
            self._logger.error(f"Error saving conversation history: {e}")
            # Log additional context for troubleshooting
            if "delegate" in str(e) or "__delegate_class__" in str(e):
                self._logger.error("Azure Cosmos DB compatibility issue - this may be related to MongoDB driver version or API compatibility")
    
    async def _generate_response_with_history(self, user_text: str, kb_context: str, conversation_history: List[dict]) -> str:
        """Generate response using O3 with conversation history context."""
        try:
            print(f"🧠 TRAPI O3: Generating response for '{user_text[:50]}{'...' if len(user_text) > 50 else ''}'")
            print(f"🔧 TRAPI O3: Client configured: {hasattr(self, 'o3_client')}")
            
            # Build conversation history context
            history_context = ""
            if conversation_history:
                history_context = "\n\nPrevious conversation context:\n"
                for conv in conversation_history[-3:]:  # Last 3 conversations
                    history_context += f"Q: {conv['question']}\nA: {conv['answer']}\n\n"
                print(f"📚 Using {len(conversation_history)} conversation history entries")
            else:
                print("📚 No conversation history available")
            
            # Enhanced prompt with conversation history
            system_prompt = f"""You are an expert oncology assistant providing evidence-based information about cancer care. 

Use the following knowledge base information to answer the user's question:
{kb_context}

{history_context}

Guidelines:
- Provide accurate, evidence-based oncology information
- Be empathetic and supportive
- If the question relates to previous conversation, acknowledge the context
- Always recommend consulting with healthcare professionals for personalized advice
- Keep responses clear and accessible
- If you don't have specific information, say so clearly"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ]

            print("🔄 TRAPI O3: Calling Azure OpenAI API...")
            print(f"🔧 TRAPI O3: Using model: o3_2025-04-16")
            print(f"� TRAPI O3: Messages count: {len(messages)}")
            
            response = await self.o3_client.chat.completions.create(
                model="o3_2025-04-16",
                messages=messages,
                max_completion_tokens=1000,
                # Note: O3 model only supports default temperature (1.0)
            )
            
            generated_response = response.choices[0].message.content
            print(f"✅ TRAPI O3: Response generated successfully ({len(generated_response)} chars)")
            print(f"🤖 TRAPI O3: Response preview: {generated_response[:100]}...")
            return generated_response
            
        except Exception as e:
            print(f"❌ TRAPI O3: Error generating response: {e}")
            print(f"❌ TRAPI O3: Error type: {type(e)}")
            import traceback
            print(f"❌ TRAPI O3: Full traceback: {traceback.format_exc()}")
            self._logger.error(f"Error generating response with history: {e}")
            return "I apologize, but I'm having trouble processing your question right now. Please try again or consult with your healthcare provider."
    
    async def _handle_voice_message(self, message_context: ByoebMessageContext) -> Optional[str]:
        """Handle voice message transcription."""
        try:
            if (message_context.message_context and 
                message_context.message_context.additional_info and
                message_context.message_context.additional_info.get("media_url") and 
                self._speech_translator):
                
                media_url = message_context.message_context.additional_info.get("media_url")
                # Transcribe voice message
                transcribed_text = await self._speech_translator.translate(media_url)
                self._logger.info(f"Transcribed voice message: {transcribed_text[:100]}...")
                return transcribed_text
            return None
        except Exception as e:
            self._logger.error(f"Error handling voice message: {e}")
            return None
    
    async def _get_embedding(self, text: str) -> List[float]:
        """Get embedding using TRAPI text-embedding-3-large_1."""
        try:
            response = await self.embedding_client.embeddings.create(
                model="text-embedding-3-large",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            self._logger.error(f"Error getting embedding: {e}")
            raise

    async def _search_knowledge_bases(self, query: str) -> str:
        """Search across all knowledge bases using vector search with TRAPI embeddings."""
        try:
            print(f"🔍 Starting vector search for: '{query[:50]}{'...' if len(query) > 50 else ''}'")
            
            # Get query embedding using TRAPI
            try:
                query_embedding = await self._get_embedding(query)
                print("✅ Successfully generated query embedding")
            except Exception as e:
                print(f"❌ Embedding error, falling back to text search: {e}")
                return await self._text_search_fallback(query)
            
            # Create vectorized query for pure vector search (100% semantic similarity)
            from azure.search.documents.models import VectorizedQuery
            vector_query = VectorizedQuery(
                vector=query_embedding,
                k_nearest_neighbors=10,  # Increased for better semantic matching
                fields="text_vector_3072",
                weight=1.0  # Full weight for vector search (100% semantic)
            )
            
            all_results = []
            
            # Search KB1: Q&A pairs with pure vector search - get top 3
            print("🔍 Searching KB1: Q&A pairs (top 3) - 100% vector search")
            qa_results = await self.search_client.search(
                search_text=None,  # No text search component - pure vector search
                vector_queries=[vector_query],
                top=3,  # Exactly 3 results
                filter="source eq 'oncobot_knowledge_base'",
                select=['question', 'answer', 'category', 'combined_text', 'question_number']
            )
            
            kb1_results = []
            async for result in qa_results:
                kb1_results.append({
                    'source': 'KB1_QA',
                    'question': result.get('question', ''),
                    'answer': result.get('answer', ''),
                    'category': result.get('category', ''),
                    'combined_text': result.get('combined_text', ''),
                    'question_number': result.get('question_number', 0),
                    'score': result.get('@search.score', 0),
                    'search_type': 'vector'
                })
            
            # Search KB2: Radiation Therapy Guide sections - get top 2
            print("🔍 Searching KB2: Radiation Therapy Guide sections - 100% vector search")
            kb2_search = await self.search_client.search(
                search_text=None,  # No text search component - pure vector search
                vector_queries=[vector_query],
                top=2,  # Get top 2 KB2 results
                filter="source eq 'kb2_content'",
                select=['question', 'answer', 'category', 'combined_text', 'question_number']
            )
            
            kb2_results = []
            async for result in kb2_search:
                kb2_results.append({
                    'source': 'KB2_Markdown',
                    'section_headers': result.get('question', ''),
                    'content': result.get('answer', ''),
                    'category': result.get('category', ''),
                    'combined_text': result.get('combined_text', ''),
                    'score': result.get('@search.score', 0),
                    'search_type': 'vector'
                })
            
            # Search KB3: Head and Neck Radiation Therapy sections - get top 2
            print("🔍 Searching KB3: Head and Neck Radiation Therapy sections - 100% vector search")
            kb3_search = await self.search_client.search(
                search_text=None,  # No text search component - pure vector search
                vector_queries=[vector_query],
                top=2,  # Get top 2 KB3 results
                filter="source eq 'kb3_content'",
                select=['question', 'answer', 'category', 'combined_text', 'question_number']
            )
            
            kb3_results = []
            async for result in kb3_search:
                kb3_results.append({
                    'source': 'KB3_Markdown',
                    'section_headers': result.get('question', ''),
                    'content': result.get('answer', ''),
                    'category': result.get('category', ''),
                    'combined_text': result.get('combined_text', ''),
                    'score': result.get('@search.score', 0),
                    'search_type': 'vector'
                })
            
            # Combine all results: 3 KB1 + 2 KB2 + 2 KB3 = 7 total
            all_results = kb1_results + kb2_results + kb3_results
            markdown_total = len(kb2_results) + len(kb3_results)
            
            print(f"📊 Search results: {len(kb1_results)} Q&A + {markdown_total} Markdown = {len(all_results)} total")
            
            # Print detailed results
            for i, result in enumerate(all_results):
                if result['source'] == 'KB1_QA':
                    print(f"  {i+1}. 🔍V Q{result['question_number']}: {result['question'][:50]}... (Score: {result['score']:.3f})")
                elif result['source'] == 'KB2_Markdown':
                    print(f"  {i+1}. 🔍V KB2: {result['section_headers'][:50]}... (Score: {result['score']:.3f})")
                elif result['source'] == 'KB3_Markdown':
                    print(f"  {i+1}. 🔍V KB3: {result['section_headers'][:50]}... (Score: {result['score']:.3f})")
            
            # Build context from retrieved results
            if all_results:
                context_text = ""
                qa_context = []
                md_context = []
                
                for result in all_results:
                    if result['source'] == 'KB1_QA':
                        qa_context.append(f"Q{result['question_number']}: {result['question']}\\nA: {result['answer']}")
                    elif result['source'] in ['KB2_Markdown', 'KB3_Markdown']:
                        kb_label = result['source'].replace('_Markdown', '')
                        md_context.append(f"{kb_label} Section: {result['section_headers']}\\nContent: {result['content']}")
                
                # Combine Q&A and markdown contexts
                context_parts = []
                if qa_context:
                    context_parts.append("=== Q&A KNOWLEDGE BASE (KB1) ===\\n" + "\\n\\n".join(qa_context))
                if md_context:
                    context_parts.append("=== RADIATION THERAPY GUIDES (KB2 & KB3) ===\\n" + "\\n\\n".join(md_context))
                
                context_text = "\\n\\n".join(context_parts)
                print(f"✅ KB Search: Generated context with {len(context_text)} characters")
                return context_text
            else:
                print("⚠️ KB Search: No results found")
                return "No specific information found in the knowledge base for this query. I'll provide a general oncology response based on my training."
                
        except Exception as e:
            print(f"❌ Vector search error: {e}")
            print("🔄 Falling back to text search")
            self._logger.error(f"Error in vector search: {e}")
            return await self._text_search_fallback(query)

    async def _text_search_fallback(self, query: str) -> str:
        """Fallback to text-only search when vector search fails."""
        try:
            print(f"🔍 Text search fallback for: '{query[:50]}{'...' if len(query) > 50 else ''}'")
            
            all_results = []
            
            # Search KB1: Q&A pairs (text-only) - exactly 3
            qa_results = await self.search_client.search(
                search_text=query,
                top=3,
                filter="source eq 'oncobot_knowledge_base'",
                select=['question', 'answer', 'category', 'combined_text', 'question_number']
            )
            
            kb1_results = []
            async for result in qa_results:
                kb1_results.append({
                    'source': 'KB1_QA',
                    'question': result.get('question', ''),
                    'answer': result.get('answer', ''),
                    'category': result.get('category', ''),
                    'combined_text': result.get('combined_text', ''),
                    'question_number': result.get('question_number', 0),
                    'score': result.get('@search.score', 0),
                    'search_type': 'text_only'
                })
            
            # Search KB2: Radiation Therapy Guide sections (text-only)
            kb2_results_search = await self.search_client.search(
                search_text=query,
                top=2,
                filter="source eq 'kb2_content'",
                select=['question', 'answer', 'category', 'combined_text', 'question_number']
            )
            
            kb2_results = []
            async for result in kb2_results_search:
                kb2_results.append({
                    'source': 'KB2_Markdown',
                    'section_headers': result.get('question', ''),
                    'content': result.get('answer', ''),
                    'category': result.get('category', ''),
                    'combined_text': result.get('combined_text', ''),
                    'score': result.get('@search.score', 0),
                    'search_type': 'text_only'
                })
            
            # Search KB3: Head and Neck Radiation Therapy sections (text-only)
            kb3_results_search = await self.search_client.search(
                search_text=query,
                top=2,
                filter="source eq 'kb3_content'",
                select=['question', 'answer', 'category', 'combined_text', 'question_number']
            )
            
            kb3_results = []
            async for result in kb3_results_search:
                kb3_results.append({
                    'source': 'KB3_Markdown',
                    'section_headers': result.get('question', ''),
                    'content': result.get('answer', ''),
                    'category': result.get('category', ''),
                    'combined_text': result.get('combined_text', ''),
                    'score': result.get('@search.score', 0),
                    'search_type': 'text_only'
                })
            
            # Combine results
            all_results = kb1_results + kb2_results + kb3_results
            
            print(f"📊 Text fallback: {len(kb1_results)} KB1 + {len(kb2_results)} KB2 + {len(kb3_results)} KB3 = {len(all_results)} total")
            
            if all_results:
                # Build context similar to vector search
                context_text = ""
                qa_context = []
                md_context = []
                
                for result in all_results:
                    if result['source'] == 'KB1_QA':
                        qa_context.append(f"Q{result['question_number']}: {result['question']}\\nA: {result['answer']}")
                    elif result['source'] in ['KB2_Markdown', 'KB3_Markdown']:
                        kb_label = result['source'].replace('_Markdown', '')
                        md_context.append(f"{kb_label} Section: {result['section_headers']}\\nContent: {result['content']}")
                
                # Combine Q&A and markdown contexts
                context_parts = []
                if qa_context:
                    context_parts.append("=== Q&A KNOWLEDGE BASE (KB1) ===\\n" + "\\n\\n".join(qa_context))
                if md_context:
                    context_parts.append("=== RADIATION THERAPY GUIDES (KB2 & KB3) ===\\n" + "\\n\\n".join(md_context))
                
                context_text = "\\n\\n".join(context_parts)
                return context_text
            else:
                return "Knowledge base search did not return results. I'll provide a general oncology response based on my training."
            
        except Exception as e:
            print(f"❌ Text search fallback error: {e}")
            self._logger.error(f"Text search fallback error: {e}")
            return "Knowledge base search unavailable, providing general response based on training data."
    
    async def _send_response(self, message_context: ByoebMessageContext, response: str):
        """Send response via Qikchat using proper channel service."""
        try:
            # Use channel service instead of client directly
            from byoeb.services.channel.qikchat import QikchatService
            channel_service = QikchatService()
            
            # Update message context for response
            message_context.message_context.message_english_text = response
            
            # Safely update additional_info if reply_context exists
            if message_context.reply_context and hasattr(message_context.reply_context, 'additional_info'):
                if not message_context.reply_context.additional_info:
                    message_context.reply_context.additional_info = {}
                message_context.reply_context.additional_info["response_sent"] = True
            else:
                self._logger.warning("reply_context or additional_info not available for response metadata")
            
            # Prepare requests using the channel service
            requests = channel_service.prepare_requests(message_context)
            
            # Send the response using send_requests method
            responses, message_ids = await channel_service.send_requests(requests)
            self._logger.info(f"Response sent successfully via Qikchat. Message IDs: {message_ids}")
            
        except Exception as e:
            self._logger.error(f"Error sending response: {e}")
    
    async def _send_fallback_response(self, message_context: ByoebMessageContext):
        """Send a fallback response when processing fails."""
        try:
            fallback_message = "I apologize, but I'm having trouble processing your question right now. Please try again later or contact your healthcare provider for assistance."
            await self._send_response(message_context, fallback_message)
        except Exception as e:
            self._logger.error(f"Error sending fallback response: {e}")
    