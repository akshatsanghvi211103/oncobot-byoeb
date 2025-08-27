import logging
import json
from typing import List, Optional
from datetime import datetime
from byoeb_core.models.byoeb.message_context import ByoebMessageContext
from byoeb.factory.channel import ChannelClientFactory

# TRAPI imports
from openai import AsyncAzureOpenAI
from azure.identity import ChainedTokenCredential, AzureCliCredential, ManagedIdentityCredential, get_bearer_token_provider


class TRAPIMessageConsumerService:
    """Enhanced message consumer service using TRAPI (free) for LLM responses and embeddings."""
    
    def __init__(
        self, 
        config, 
        channel_client_factory: ChannelClientFactory,
        speech_translator=None,
        text_translator=None
    ):
        self._config = config
        self._logger = logging.getLogger(self.__class__.__name__)
        self._channel_client_factory = channel_client_factory
        self._speech_translator = speech_translator
        self._text_translator = text_translator
        
        # Initialize TRAPI clients
        self._setup_trapi_clients()
    
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
    
    async def consume(self, messages: list) -> List[ByoebMessageContext]:
        """Main method to consume messages - matches the interface of MessageConsumerService."""
        self._logger.info(f"TRAPIMessageConsumerService processing {len(messages)} messages")
        
        successfully_processed_messages = []
        
        for message in messages:
            try:
                # Parse the message
                json_message = json.loads(message)
                byoeb_message = ByoebMessageContext.model_validate(json_message)
                
                # Process the message
                await self.process_message(byoeb_message)
                successfully_processed_messages.append(byoeb_message)
                
            except Exception as e:
                self._logger.error(f"Error processing message: {e}")
                # Continue with other messages
        
        self._logger.info(f"Successfully processed {len(successfully_processed_messages)} messages")
        return successfully_processed_messages
    
    async def process_message(self, message_context: ByoebMessageContext):
        """Process a single message using TRAPI LLM."""
        try:
            user_id = ""
            if message_context.user:
                user_id = message_context.user.user_id if message_context.user.user_id else "unknown"
            else:
                self._logger.warning("No user object in message context")
            
            print(f"Processing message from {user_id}")
            
            # For oncology bot, use enhanced RAG with LLM
            if message_context.channel_type == "qikchat":
                await self._process_oncology_query_with_llm(message_context)
            else:
                print(f"Unsupported channel type: {message_context.channel_type}")
                
        except Exception as e:
            self._logger.error(f"Error processing message: {e}")
    
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
    
    async def _search_knowledge_base(self, user_question: str, kb1_limit: int = 3, kb2_kb3_limit: int = 4) -> List[dict]:
        """Search all knowledge bases with structured limits: 3 from KB1, 2 each from KB2 and KB3."""
        try:
            from azure.identity import AzureCliCredential
            from azure.search.documents import SearchClient
            from azure.search.documents.models import VectorizedQuery
            
            # print(f"=== HYBRID SEARCH ACROSS ALL KNOWLEDGE BASES FOR: {user_question} ===")
            
            # Setup Azure Search credentials
            credential = AzureCliCredential()
            search_endpoint = "https://byoeb-search.search.windows.net"
            search_client = SearchClient(
                endpoint=search_endpoint,
                index_name='oncobot_index',
                credential=credential
            )
            
            # Get query embedding using TRAPI
            try:
                query_embedding = await self._get_embedding(user_question)
                print("=== SUCCESSFULLY GENERATED QUERY EMBEDDING ===")
            except Exception as e:
                print(f"=== EMBEDDING ERROR, FALLING BACK TO TEXT SEARCH: {e} ===")
                return await self._text_search_fallback(search_client, user_question, kb1_limit, kb2_kb3_limit)
            
            # Create vectorized query for pure vector search (100% semantic similarity)
            vector_query = VectorizedQuery(
                vector=query_embedding,
                k_nearest_neighbors=10,  # Increased for better semantic matching
                fields="text_vector_3072",
                weight=1.0  # Full weight for vector search (100% semantic)
            )
            
            all_results = []
            
            # Search KB1: Q&A pairs with pure vector search (100% semantic similarity) - get top 3
            print("=== SEARCHING KB1: Q&A PAIRS (TOP 3) - 100% VECTOR SEARCH ===")
            qa_results = search_client.search(
                search_text=None,  # No text search component - pure vector search
                vector_queries=[vector_query],
                top=kb1_limit,  # Exactly 3 results
                filter="source eq 'oncobot_knowledge_base'",
                select=['question', 'answer', 'category', 'combined_text', 'question_number']
            )
            
            kb1_results = []
            for result in qa_results:
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
            
            # Search KB2: Radiation Therapy Guide sections with pure vector search (100% semantic similarity)
            print("=== SEARCHING KB2: RADIATION THERAPY GUIDE SECTIONS - 100% VECTOR SEARCH ===")
            kb2_search = search_client.search(
                search_text=None,  # No text search component - pure vector search
                vector_queries=[vector_query],
                top=2,  # Get top 2 KB2 results
                filter="source eq 'kb2_content'",
                select=['question', 'answer', 'category', 'combined_text', 'question_number']
            )
            
            kb2_results = []
            for result in kb2_search:
                kb2_results.append({
                    'source': 'KB2_Markdown',
                    'section_headers': result.get('question', ''),
                    'content': result.get('answer', ''),
                    'category': result.get('category', ''),
                    'combined_text': result.get('combined_text', ''),
                    'score': result.get('@search.score', 0),
                    'search_type': 'vector'
                })
            
            # Search KB3: Head and Neck Radiation Therapy sections with pure vector search (100% semantic similarity)
            print("=== SEARCHING KB3: HEAD AND NECK RADIATION THERAPY SECTIONS - 100% VECTOR SEARCH ===")
            kb3_search = search_client.search(
                search_text=None,  # No text search component - pure vector search
                vector_queries=[vector_query],
                top=2,  # Get top 2 KB3 results
                filter="source eq 'kb3_content'",
                select=['question', 'answer', 'category', 'combined_text', 'question_number']
            )
            
            kb3_results = []
            for result in kb3_search:
                kb3_results.append({
                    'source': 'KB3_Markdown',
                    'section_headers': result.get('question', ''),
                    'content': result.get('answer', ''),
                    'category': result.get('category', ''),
                    'combined_text': result.get('combined_text', ''),
                    'score': result.get('@search.score', 0),
                    'search_type': 'vector'
                })
            
            # Combine all results: 3 KB1 + markdown sections = total
            all_results = kb1_results + kb2_results + kb3_results
            markdown_total = len(kb2_results) + len(kb3_results)
            
            print(f"=== SEARCH RESULTS: {len(kb1_results)} Q&A + {markdown_total} Markdown = {len(all_results)} total ===")
            
            for i, result in enumerate(all_results):
                if result['source'] == 'KB1_QA':
                    print(f"{i+1}. 🔍V Q{result['question_number']}: {result['question'][:50]}... (Score: {result['score']:.3f})")
                elif result['source'] == 'KB2_Markdown':
                    print(f"{i+1}. 🔍V Markdown: {result['section_headers'][:50]}... (Score: {result['score']:.3f})")
                elif result['source'] == 'KB3_Markdown':
                    print(f"{i+1}. 🔍V Markdown: {result['section_headers'][:50]}... (Score: {result['score']:.3f})")
            
            return all_results
                
        except Exception as e:
            print(f"=== VECTOR SEARCH ERROR: {e} ===")
            print("=== FALLING BACK TO TEXT SEARCH ===")
            # Fallback to text-only search
            return await self._text_search_fallback(search_client, user_question, kb1_limit, kb2_kb3_limit)
    
    async def _text_search_fallback(self, search_client, user_question: str, kb1_limit: int, kb2_kb3_limit: int) -> List[dict]:
        """Fallback to text-only search with structured limits."""
        try:
            all_results = []
            
            # Search KB1: Q&A pairs (text-only) - exactly 3
            qa_results = search_client.search(
                search_text=user_question,
                top=kb1_limit,
                filter="source eq 'oncobot_knowledge_base'",
                select=['question', 'answer', 'category', 'combined_text', 'question_number']
            )
            
            kb1_results = []
            for result in qa_results:
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
            kb2_results_search = search_client.search(
                search_text=user_question,
                top=2,
                filter="source eq 'kb2_content'",
                select=['question', 'answer', 'category', 'combined_text', 'question_number']
            )
            
            kb2_results = []
            for result in kb2_results_search:
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
            kb3_results_search = search_client.search(
                search_text=user_question,
                top=2,
                filter="source eq 'kb3_content'",
                select=['question', 'answer', 'category', 'combined_text', 'question_number']
            )
            
            kb3_results = []
            for result in kb3_results_search:
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
            
            print(f"=== TEXT FALLBACK: {len(kb1_results)} KB1 + {len(kb2_results)} KB2 + {len(kb3_results)} KB3 = {len(all_results)} total ===")
            return all_results
            
        except Exception as e:
            print(f"=== TEXT FALLBACK ERROR: {e} ===")
            return []
    
    def _parse_structured_response(self, response_text: str) -> tuple[str, str]:
        """Parse the structured XML response to extract answer and query type."""
        import re
        
        # print(f"=== PARSING RESPONSE (First 200 chars): {response_text[:200]}... ===")
        
        # Try multiple patterns for more robust parsing
        response_patterns = [
            r"<BEGIN RESPONSE>(.*?)<END RESPONSE>",
            r"<RESPONSE>(.*?)</RESPONSE>", 
            r"Response:\s*(.*?)(?=Query Type:|<BEGIN QUERY TYPE>|$)",
            r"Answer:\s*(.*?)(?=Query Type:|<BEGIN QUERY TYPE>|$)",
            r"(?:^|\n)(.*?)(?=<BEGIN QUERY TYPE>|Query Type:|$)"  # Fallback: everything before query type
        ]
        
        query_type_patterns = [
            r"<BEGIN QUERY TYPE>(.*?)<END QUERY TYPE>",
            r"<QUERY TYPE>(.*?)</QUERY TYPE>",
            r"Query Type:\s*([^\n\r]*)",
            r"Type:\s*([^\n\r]*)",
            r"Classification:\s*([^\n\r]*)"
        ]

        # Extract the response
        answer = None
        for pattern in response_patterns:
            response_match = re.search(pattern, response_text, re.DOTALL | re.IGNORECASE)
            if response_match:
                answer = response_match.group(1).strip()
                print(f"=== FOUND ANSWER WITH PATTERN: {pattern} ===")
                break

        # Extract the query type
        query_type = None
        for pattern in query_type_patterns:
            query_type_match = re.search(pattern, response_text, re.DOTALL | re.IGNORECASE)
            if query_type_match:
                query_type = query_type_match.group(1).strip().lower()
                print(f"=== FOUND QUERY TYPE WITH PATTERN: {pattern} ===")
                break
        
        # Fallback if parsing fails - use the full response
        if answer is None or len(answer.strip()) == 0:
            print("=== WARNING: Failed to parse structured response, using intelligent fallback ===")
            
            # Try to extract meaningful content by removing XML tags
            cleaned_response = re.sub(r'<[^>]+>', '', response_text)
            cleaned_response = cleaned_response.strip()
            
            # If we have content after cleaning XML tags, use it
            if len(cleaned_response) > 10:  # Reasonable length check
                # Remove query type mentions from the end
                cleaned_response = re.sub(r'(?:Query Type:|Type:|Classification:).*$', '', cleaned_response, flags=re.IGNORECASE | re.DOTALL)
                answer = cleaned_response.strip()
            else:
                # Last resort - split by lines and take meaningful content
                lines = response_text.split('\n')
                meaningful_lines = []
                for line in lines:
                    line = line.strip()
                    # Skip XML tags, empty lines, and system instructions
                    if line and not line.startswith('<') and not line.endswith('>') and 'Query Type' not in line:
                        meaningful_lines.append(line)
                
                if meaningful_lines:
                    answer = ' '.join(meaningful_lines)
                else:
                    answer = "I apologize, but I encountered an issue generating a proper response. Please rephrase your question or consult with your healthcare provider."
        
        # Clean up the answer
        if answer:
            # Remove any remaining XML artifacts
            answer = re.sub(r'<[^>]*>', '', answer)
            # Remove multiple spaces and newlines
            answer = re.sub(r'\s+', ' ', answer)
            answer = answer.strip()
        
        # Validate and clean query type
        if query_type is None:
            print("=== WARNING: Failed to parse query type, defaulting to 'medical' ===")
            query_type = "medical"
        else:
            # Ensure query type is one of the valid options
            valid_types = ['small-talk', 'medical', 'logistical']
            if query_type not in valid_types:
                # Try to match partially
                if 'small' in query_type or 'talk' in query_type:
                    query_type = 'small-talk'
                elif 'medical' in query_type or 'health' in query_type:
                    query_type = 'medical'
                elif 'logistic' in query_type or 'appointment' in query_type:
                    query_type = 'logistical'
                else:
                    query_type = 'medical'  # Default fallback
        
        print(f"=== FINAL PARSED - Answer: {answer[:30]}..., Query Type: {query_type} ===")
        return answer, query_type
    
    async def _generate_llm_response(self, user_question: str, context_results: List[dict]) -> str:
        """Generate response using O3 model with retrieved context from all knowledge bases."""
        try:
            # Build context from retrieved results (KB1, KB2, KB3)
            context_text = ""
            if context_results:
                qa_context = []
                md_context = []
                
                for result in context_results:
                    search_indicator = "🔍H" if result.get('search_type') == 'hybrid' else "🔍T"
                    
                    if result['source'] == 'KB1_QA':
                        qa_context.append(f"{search_indicator} Q{result['question_number']}: {result['question']}\\nA: {result['answer']}")
                    elif result['source'] in ['KB2_Markdown', 'KB3_Markdown']:
                        kb_label = result['source'].replace('_Markdown', '')
                        md_context.append(f"{search_indicator} {kb_label} Section: {result['section_headers']}\\nContent: {result['content']}")
                
                # Combine Q&A and markdown contexts
                context_parts = []
                if qa_context:
                    context_parts.append("=== Q&A KNOWLEDGE BASE (KB1) ===\\n" + "\\n\\n".join(qa_context))
                if md_context:
                    context_parts.append("=== RADIATION THERAPY GUIDES (KB2 & KB3) ===\\n" + "\\n\\n".join(md_context))
                
                context_text = "\\n\\n".join(context_parts)
            
            # Create the prompt for O3 with structured format
            system_prompt = """You are an expert oncology assistant helping cancer patients. Your purpose is to answer patients with any oncology-related queries they might have.

You have access to three knowledge bases:
- KB1: Q&A pairs covering general oncology topics
- KB2 & KB3: Detailed radiation therapy treatment guides and procedures

Guidelines for answering:
- Prioritize information from the knowledge base context when available
- If the query can be truthfully answered using the context, provide a comprehensive and compassionate response
- Combine information from multiple sources (Q&A pairs and treatment guides) when relevant, but need not mention the specific sources
- If the context doesn't contain sufficient information, say "I do not have specific information about this in my knowledge base. Please consult with your healthcare provider for accurate guidance."
- Be empathetic and supportive in all responses.
- Keep questions short and focused (2-5 sentences max) after combining all context in a concise, complete and coherent manner.
- Always recommend consulting with healthcare providers for specific medical advice and treatment decisions
- One exception: if the query is a greeting, acknowledgement, or gratitude, respond appropriately without requiring knowledge base context

Query Classification:
In addition to answering, classify the query as one of these 3 categories:
- "small-talk": greetings, acknowledgements, gratitude (e.g., "Hello", "Thank you", "Got it")
- "medical": oncology-related medical questions about symptoms, treatments, side effects, etc.
- "logistical": practical questions about appointments, procedures, hospital processes, etc.

<BEGIN RESPONSE>
Your comprehensive and compassionate response here
<END RESPONSE>

<BEGIN QUERY TYPE>
medical
<END QUERY TYPE>

Replace "medical" with the appropriate query type (small-talk, medical, or logistical). Ensure the query_type belongs only to the 3 categories mentioned.

IMPORTANT: Start your response immediately with <BEGIN RESPONSE> and end with <END QUERY TYPE>. Do not include any other text."""
            
            user_prompt = f"""The following knowledge base context has been retrieved from multiple sources to help answer your question:

KNOWLEDGE BASE CONTEXT:
{context_text}

You are asked the following question:
{user_question}

Please provide a response following the XML structure specified in the system prompt. Use information from both Q&A pairs and treatment guides when relevant.
"""
            
            print(f"=== GENERATING ENHANCED LLM RESPONSE WITH O3 TRAPI ===")
            
            # Use O3 TRAPI with retry logic
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    the_messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                    print(f"=== TRAPI O3 ATTEMPT {attempt + 1}/{max_retries} ===")
                    response = await self.o3_client.chat.completions.create(
                        model="o3_2025-04-16",
                        messages=the_messages,
                        max_completion_tokens=1000  # Increased for more comprehensive responses
                    )
                    
                    raw_response = response.choices[0].message.content
                    
                    # Check if response is None or empty
                    if not raw_response or len(raw_response.strip()) == 0:
                        print(f"=== ERROR: TRAPI O3 returned empty response on attempt {attempt + 1} ===")
                        print(f"=== RESPONSE OBJECT: {response} ===")
                        print(f"=== CHOICES: {response.choices if hasattr(response, 'choices') else 'No choices'} ===")
                        
                        if attempt < max_retries - 1:
                            print("=== RETRYING TRAPI O3 REQUEST ===")
                            continue
                        else:
                            print("=== MAX RETRIES REACHED, USING FALLBACK ===")
                            fallback_response = self._generate_context_based_fallback(context_text, user_question)
                            return fallback_response
                    
                    # Success - we have a response
                    raw_response = raw_response.strip()
                    
                    # Add debugging to see the actual response
                    print()
                    print(f"=== RAW LLM RESPONSE (First 100 chars): {raw_response[:100]}... ===")
                    print()
                    # print(f"=== RAW LLM RESPONSE (Full): {raw_response} ===")
                    
                    # Parse the structured response
                    parsed_answer, query_type = self._parse_structured_response(raw_response)
                    break  # Success, exit retry loop
                    
                except Exception as trapi_error:
                    print(f"=== TRAPI O3 REQUEST ERROR ON ATTEMPT {attempt + 1}: {trapi_error} ===")
                    if attempt < max_retries - 1:
                        print("=== RETRYING TRAPI O3 REQUEST ===")
                        continue
                    else:
                        print("=== MAX RETRIES REACHED, USING FALLBACK ===")
                        fallback_response = self._generate_context_based_fallback(context_text, user_question)
                        return fallback_response
            
            # print(f"=== ENHANCED PARSED ANSWER: {parsed_answer[:100]}... ===")
            print(f"=== QUERY TYPE: {query_type} ===")
            
            return parsed_answer
            
        except Exception as e:
            print(f"=== ENHANCED LLM GENERATION ERROR: {e} ===")
            # Generate context-based fallback when TRAPI fails
            fallback_response = self._generate_context_based_fallback(context_text, user_question)
            return fallback_response
    
    def _generate_context_based_fallback(self, context_text: str, user_question: str) -> str:
        """Generate a fallback response based on available context when LLM fails."""
        print("=== GENERATING CONTEXT-BASED FALLBACK RESPONSE ===")
        
        if not context_text or len(context_text.strip()) == 0:
            return "I apologize, but I'm currently experiencing technical difficulties. Please consult with your healthcare provider for accurate guidance."
        
        # Simple context extraction for basic responses
        context_lines = context_text.split('\n')
        relevant_info = []
        
        for line in context_lines:
            line = line.strip()
            if len(line) > 20 and any(keyword in line.lower() for keyword in ['answer:', 'treatment', 'patient', 'cancer', 'radiation', 'therapy']):
                # Clean and add relevant lines
                cleaned_line = line.replace('Answer:', '').replace('Question:', '').strip()
                if len(cleaned_line) > 10:
                    relevant_info.append(cleaned_line)
        
        if relevant_info:
            # Create a basic response from context
            context_summary = ' '.join(relevant_info[:3])  # Use first 3 relevant pieces
            response = f"Based on the available information: {context_summary[:300]}..."
            
            # Add standard medical disclaimer
            response += " Please consult with your healthcare provider for personalized medical advice and treatment decisions."
            
            print(f"=== FALLBACK RESPONSE GENERATED: {response[:100]}... ===")
            return response
        else:
            return "I found some information in the knowledge base, but I'm unable to process it properly at the moment. Please consult with your healthcare provider for accurate guidance."
    
    async def _process_voice_message(self, message_context: ByoebMessageContext) -> Optional[str]:
        """Convert voice message to text using the configured speech translator."""
        if not self._speech_translator:
            self._logger.warning("No speech translator configured for voice processing")
            return None
            
        try:
            # Get media ID from voice message - check multiple possible locations
            media_id = None
            
            # Check media_info first
            if (message_context.message_context and 
                message_context.message_context.media_info and 
                hasattr(message_context.message_context.media_info, 'media_id')):
                media_id = message_context.message_context.media_info.media_id
                # print(f"=== FOUND MEDIA ID IN media_info: {media_id} ===")
            
            # Check additional_info if media_info didn't work
            elif (message_context.message_context and 
                  hasattr(message_context.message_context, 'additional_info') and
                  message_context.message_context.additional_info):
                # Check for various possible keys in additional_info
                additional_info = message_context.message_context.additional_info
                
                # First try to get audio data structure for Qikchat
                if isinstance(additional_info, dict):
                    audio_data = additional_info.get('audio', {})
                    if audio_data and isinstance(audio_data, dict):
                        media_id = audio_data.get('id') or audio_data.get('url')
                        if media_id:
                            print(f"=== FOUND MEDIA ID IN additional_info.audio: {media_id} ===")
                
                # If that didn't work, check for direct keys
                if not media_id:
                    for key in ['media_id', 'id', 'file_id', 'audio_id']:
                        if key in additional_info:
                            media_id = additional_info[key]
                            print(f"=== FOUND MEDIA ID IN additional_info[{key}]: {media_id} ===")
                            break
            
            if not media_id:
                # Try using message_id as media_id (fallback for Qikchat)
                if (message_context.message_context and 
                    hasattr(message_context.message_context, 'message_id') and 
                    message_context.message_context.message_id):
                    media_id = message_context.message_context.message_id
                    print(f"=== USING MESSAGE_ID AS MEDIA_ID: {media_id} ===")
                    
            if not media_id:
                print("=== NO MEDIA ID FOUND - CHECKING ALL MESSAGE ATTRIBUTES ===")
                # Print all available attributes for debugging
                if message_context.message_context:
                    print(f"Available message_context attributes: {dir(message_context.message_context)}")
                    for attr in dir(message_context.message_context):
                        if not attr.startswith('_'):
                            value = getattr(message_context.message_context, attr, None)
                            print(f"  {attr}: {value}")
                self._logger.warning("No media_id found in voice message")
                return None
                
            channel_type = message_context.channel_type
            user_language = message_context.user.user_language if message_context.user else "en"
            
            # print(f"=== PROCESSING VOICE MESSAGE: media_id={media_id}, language={user_language} ===")
            
            # Download audio from channel - handle different channel types
            if channel_type == "qikchat":
                # Qikchat can provide media as either ID or URL
                # Check if media_id is actually a URL (starts with http)
                if media_id and (media_id.startswith('http://') or media_id.startswith('https://')):
                    print(f"=== DOWNLOADING AUDIO FROM URL: {media_id} ===")
                    # Download directly from URL
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        try:
                            async with session.get(media_id) as response:
                                if response.status == 200:
                                    audio_data = await response.read()
                                    print(f"=== AUDIO SIZE: {len(audio_data)} bytes ===")
                                else:
                                    print(f"=== ERROR DOWNLOADING FROM URL, STATUS: {response.status} ===")
                                    return None
                        except Exception as url_error:
                            print(f"=== ERROR DOWNLOADING FROM URL: {url_error} ===")
                            return None
                else:
                    print(f"=== DOWNLOADING AUDIO VIA QIKCHAT API: {media_id} ===")
                    # Try Qikchat API download (this may not work for Manipal server)
                    from byoeb.services.channel.qikchat import QikchatService
                    qikchat_service = QikchatService()
                    audio_data = await qikchat_service.download_media(media_id, "audio/ogg")
                    if not audio_data:
                        print(f"=== ERROR DOWNLOADING AUDIO FROM QIKCHAT API ===")
                        return None
                
                # Create a simple data object with the audio bytes
                class AudioData:
                    def __init__(self, data, mime_type="audio/ogg"):
                        self.data = data
                        self.mime_type = mime_type
                
                audio_message = AudioData(audio_data)
                err = None
            else:
                # WhatsApp or other channels use adownload_media
                channel_client = await self._channel_client_factory.get(channel_type)
                _, audio_message, err = await channel_client.adownload_media(media_id)
                
                if err:
                    print(f"=== ERROR DOWNLOADING AUDIO: {err} ===")
                    return None
            
            # Convert OGG to WAV if needed
            try:
                from byoeb_core.convertor.audio_convertor import ogg_opus_to_wav_bytes
                audio_message_wav = ogg_opus_to_wav_bytes(audio_message.data)
                # print(f"=== AUDIO CONVERTED TO WAV ===")
            except Exception as convert_error:
                print(f"=== AUDIO CONVERSION ERROR: {convert_error} ===")
                # If conversion fails, try using original audio data (OGG format)
                audio_message_wav = audio_message.data
                print(f"=== USING ORIGINAL OGG AUDIO DATA ===")
            
            # Speech to text using the injected speech translator
            try:
                print(f"=== STARTING SPEECH-TO-TEXT CONVERSION ===")
                audio_to_text = await self._speech_translator.aspeech_to_text(audio_message_wav, user_language)
                print(f"=== SPEECH TO TEXT RESULT: {audio_to_text} ===")
            except Exception as speech_error:
                print(f"=== SPEECH-TO-TEXT ERROR: {speech_error} ===")
                print(f"=== FALLING BACK TO DEMO MODE ===")
                # For demo purposes, return a placeholder text
                audio_to_text = "I sent you a voice message - speech-to-text processing is temporarily unavailable."
            
            # Translate to English if needed and text translator is available
            if user_language != "en" and self._text_translator:
                try:
                    translated_text = await self._text_translator.atranslate_text(
                        input_text=audio_to_text,
                        source_language=user_language,
                        target_language="en"
                    )
                    print(f"=== TRANSLATED TO ENGLISH: {translated_text} ===")
                    return translated_text
                except Exception as translate_error:
                    print(f"=== TRANSLATION ERROR: {translate_error} ===")
                    # Return original text if translation fails
                    return audio_to_text
            else:
                return audio_to_text
                
        except Exception as e:
            self._logger.error(f"Voice processing error: {e}")
            print(f"=== VOICE PROCESSING ERROR: {e} ===")
            return None

    async def _process_oncology_query_with_llm(self, message_context: ByoebMessageContext):
        """Process oncology query using enhanced RAG with TRAPI LLM."""
        try:
            # Extract user question and ID
            user_question = ""
            user_id = ""
            
            # # Debug: Print message structure to understand what we're receiving
            # print(f"=== DEBUG MESSAGE STRUCTURE ===")
            # if message_context.message_context:
            #     print(f"Message type: {getattr(message_context.message_context, 'message_type', 'None')}")
            #     print(f"Message source text: {getattr(message_context.message_context, 'message_source_text', 'None')}")
            #     print(f"Message english text: {getattr(message_context.message_context, 'message_english_text', 'None')}")
            #     print(f"Media info: {getattr(message_context.message_context, 'media_info', 'None')}")
            #     if hasattr(message_context.message_context, 'media_info') and message_context.message_context.media_info:
            #         print(f"Media ID: {getattr(message_context.message_context.media_info, 'media_id', 'None')}")
            #     # Check additional info for media ID
            #     if hasattr(message_context.message_context, 'additional_info'):
            #         additional_info = message_context.message_context.additional_info
            #         print(f"Additional info: {additional_info}")
            #         print(f"Additional info type: {type(additional_info)}")
            #         # If it's a dict, check for audio data
            #         if isinstance(additional_info, dict):
            #             audio_data = additional_info.get('audio', {})
            #             print(f"Audio data from additional_info: {audio_data}")
            #             if audio_data and isinstance(audio_data, dict):
            #                 media_id_from_audio = audio_data.get('id') or audio_data.get('url')
            #                 print(f"Media ID from audio data: {media_id_from_audio}")
                
            #     # Print all available attributes for complete debugging
            #     print(f"=== ALL MESSAGE_CONTEXT ATTRIBUTES ===")
            #     for attr in dir(message_context.message_context):
            #         if not attr.startswith('_'):
            #             value = getattr(message_context.message_context, attr, None)
            #             print(f"  {attr}: {value}")
                
            #     # Check if there's an original message or raw data
            #     if hasattr(message_context, '_original_message'):
            #         print(f"Original message: {getattr(message_context, '_original_message', None)}")
            #     print(f"=== ALL USER ATTRIBUTES ===")
            #     if message_context.user:
            #         for attr in dir(message_context.user):
            #             if not attr.startswith('_'):
            #                 value = getattr(message_context.user, attr, None)
            #                 print(f"  {attr}: {value}")
            #     print(f"=== ALL MESSAGE_CONTEXT ATTRIBUTES ===")
            #     for attr in dir(message_context):
            #         if not attr.startswith('_'):
            #             value = getattr(message_context, attr, None)
            #             print(f"  {attr}: {value}")
            # else:
            #     print("No message_context found")
            # print(f"=== END DEBUG ===")
            
            # Check if this is a voice message and process it first
            # Modified condition: check for regular_audio type regardless of media_info
            if (message_context.message_context and 
                message_context.message_context.message_type == "regular_audio"):
                print("=== DETECTED VOICE MESSAGE ===")
                user_question = await self._process_voice_message(message_context)
                if user_question:
                    print(f"=== VOICE CONVERTED TO TEXT: {user_question} ===")
                else:
                    print("=== VOICE PROCESSING FAILED ===")
                    return  # Exit if voice processing fails
            elif message_context.message_context and message_context.message_context.message_english_text:
                user_question = message_context.message_context.message_english_text
            elif message_context.message_context and message_context.message_context.message_source_text:
                user_question = message_context.message_context.message_source_text
            
            if message_context.user:
                if hasattr(message_context.user, 'user_id') and message_context.user.user_id:
                    user_id = message_context.user.user_id
                elif hasattr(message_context.user, 'phone_number_id') and message_context.user.phone_number_id:
                    user_id = message_context.user.phone_number_id
                elif hasattr(message_context.user, 'phone_number') and message_context.user.phone_number:
                    user_id = message_context.user.phone_number
            
            if not user_question or not user_id:
                self._logger.warning(f"Missing question or user ID: question='{user_question}', user_id='{user_id}'")
                return
            
            print(f"=== ENHANCED ONCOLOGY RAG QUERY: {user_question} ===")
            
            # Step 1: Search all knowledge bases with structured limits (3 KB1 + 2 KB2 + 2 KB3)
            context_results = await self._search_knowledge_base(user_question, kb1_limit=3, kb2_kb3_limit=4)
            
            # Step 2: Generate response using LLM with retrieved context from all KBs
            if context_results:
                response_text = await self._generate_llm_response(user_question, context_results)
            else:
                # Generate response without context (LLM will handle appropriately)
                response_text = await self._generate_llm_response(user_question, [])
            
            
            print(f"=== FINAL RESPONSE TO {user_id} ===")
            print(f"Response: {response_text}")
            
            print(f"=== MESSAGE SENDING DISABLED TO SAVE COSTS ===")
            return
        
            # Send response using Qikchat (endpoint fixed to api.qikchat.in)
            channel_client = await self._channel_client_factory.get(message_context.channel_type)
            
            formatted_user_id = f"+{user_id}" if not user_id.startswith('+') else user_id
            
            message_data = {
                "to_contact": formatted_user_id,
                "type": "text",
                "text": {
                    "body": response_text
                }
            }
            
            try:
                response = await channel_client.send_message(message_data)
                print(f"Sent enhanced oncology response to {formatted_user_id}, response: {response}")
            except Exception as send_error:
                print(f"Error sending message: {send_error}")
                if formatted_user_id.startswith('+'):
                    print("Retrying without + prefix...")
                    message_data["to_contact"] = user_id
                    response = await channel_client.send_message(message_data)
                    print(f"Retry successful, response: {response}")
                else:
                    raise
            
        except Exception as e:
            self._logger.error(f"Error processing enhanced oncology query: {e}")
            # Send error response if needed
            if user_id:
                try:
                    channel_client = await self._channel_client_factory.get(message_context.channel_type)
                    error_message_data = {
                        "to_contact": user_id,
                        "type": "text",
                        "text": {
                            "body": "I'm sorry, I encountered an error processing your oncology question. Please try again later or consult with your healthcare provider."
                        }
                    }
                    await channel_client.send_message(error_message_data)
                    print(f"Sent error message to {user_id}")
                        
                except Exception as send_error:
                    self._logger.error(f"Error sending error response: {send_error}")
    
    async def process_messages(self, messages: List[ByoebMessageContext]):
        """Process multiple messages."""
        self._logger.info(f"Processing {len(messages)} messages")
        
        for message_context in messages:
            await self.process_message(message_context)
