import hashlib
import byoeb.services.chat.constants as constants
import re
import byoeb.utils.utils as utils
import random
import uuid
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
from typing import List, Dict, Any
from byoeb.chat_app.configuration.config import bot_config, app_config
from byoeb.models.message_category import MessageCategory
from byoeb_core.models.vector_stores.chunk import Chunk, Chunk_metadata
from byoeb_core.models.vector_stores.azure.azure_search import AzureSearchNode
from byoeb_core.models.byoeb.message_context import (
    ByoebMessageContext,
    MessageContext,
    ReplyContext,
    MessageTypes
)
from byoeb_integrations.vector_stores.azure_vector_search.azure_vector_search import AzureVectorSearchType
from byoeb_core.models.byoeb.user import User
from byoeb.services.chat.message_handlers.base import Handler

class ByoebUserGenerateResponse(Handler):
    EXPERT_PENDING_EMOJI = app_config["channel"]["reaction"]["expert"]["pending"]
    USER_PENDING_EMOJI = app_config["channel"]["reaction"]["user"]["pending"]
    _expert_user_types = bot_config["expert"]
    _regular_user_type = bot_config["regular"]["user_type"]

    async def __aretrieve_chunks(
        self,
        text,
        k
    ) -> List[Chunk]:
        """
        Retrieve chunks from all 3 knowledge bases:
        - KB1: Q&A pairs (source='oncobot_knowledge_base') - 3 results
        - KB2 & KB3: Markdown sections (source='markdown_knowledge_base') - 4 results
        Total: 7 results combining all knowledge bases
        """
        from byoeb.chat_app.configuration.dependency_setup import vector_store
        start_time = datetime.now().timestamp()
        
        # Get all chunks from multiple knowledge bases
        all_chunks = await self.__retrieve_from_all_knowledge_bases(vector_store, text)
        
        end_time = datetime.now().timestamp()
        utils.log_to_text_file(f"Retrieved chunks in {end_time - start_time} seconds")
        
        # Print KB context for debugging
        print(f"\n=== KB CONTEXT RETRIEVED ({len(all_chunks)} chunks) ===")
        print(f"Query: {text}")
        for i, chunk in enumerate(all_chunks):
            print(f"Chunk {i+1}:")
            # Print source safely
            source = "Unknown"
            if hasattr(chunk, 'metadata') and chunk.metadata:
                source = chunk.metadata.source or "Unknown"
                if hasattr(chunk.metadata, 'additional_metadata') and chunk.metadata.additional_metadata:
                    question = chunk.metadata.additional_metadata.get('question', '')
                    if question:
                        print(f"  Question: {question}")
            print(f"  Source: {source}")
            
            # Print content safely
            if hasattr(chunk, 'text') and chunk.text:
                print(f"  Content: {chunk.text[:200]}...")
            print("  ---")
        print("=== END KB CONTEXT ===\n")
        
        return all_chunks

    async def __retrieve_from_all_knowledge_bases(self, vector_store, query_text):
        """
        Retrieve from all knowledge bases with specific distribution:
        - 3 from Q&A pairs (KB1)
        - 4 from markdown sections (KB2 & KB3)
        """
        all_chunks = []
        
        try:
            # Get the Azure Search client directly for filtered searches
            search_client = vector_store.search_client
            embedding_function = vector_store._AzureVectorSearchStore__embedding_function
            
            # Get query embedding
            query_embedding = await embedding_function.aget_text_embedding(query_text)
            
            from azure.search.documents.models import VectorizedQuery
            vector_query = VectorizedQuery(
                vector=query_embedding,
                k_nearest_neighbors=10,
                fields="text_vector_3072"
            )
            
            # Search KB1: Q&A pairs (3 results)
            qa_results = search_client.search(
                search_text=query_text,
                vector_queries=[vector_query],
                top=3,
                filter="source eq 'oncobot_knowledge_base'",
                select=['id', 'combined_text', 'source', 'question', 'answer']
            )
            
            # Convert Q&A results to chunks
            for result in qa_results:
                chunk = self.__convert_search_result_to_chunk(result)
                if chunk:
                    all_chunks.append(chunk)
            
            # Search KB2 & KB3: Markdown sections (4 results)
            md_results = search_client.search(
                search_text=query_text,
                vector_queries=[vector_query],
                top=4,
                filter="source eq 'markdown_knowledge_base'",
                select=['id', 'combined_text', 'source', 'question', 'answer']
            )
            
            # Convert markdown results to chunks
            for result in md_results:
                chunk = self.__convert_search_result_to_chunk(result)
                if chunk:
                    all_chunks.append(chunk)
                    
        except Exception as e:
            # Fallback to original method if filtering fails
            utils.log_to_text_file(f"Error in multi-KB search: {e}, falling back to original search")
            all_chunks = await vector_store.aretrieve_top_k_chunks(
                query_text,
                7,  # Default to 7 total results
                search_type=AzureVectorSearchType.DENSE.value,
                select=["id", "combined_text", "source", "question", "answer"],
                vector_field="text_vector_3072"
            )
        
        return all_chunks

    def __convert_search_result_to_chunk(self, result):
        """Convert Azure Search result to Chunk object"""
        try:
            chunk = Chunk(
                chunk_id=result.get("id"),
                text=result.get("combined_text") or result.get("answer") or "",
                metadata=Chunk_metadata(
                    source=result.get("source"),
                    creation_timestamp=None,
                    update_timestamp=None,
                    additional_metadata={
                        "question": result.get("question"),
                        "answer": result.get("answer"),
                        "category": result.get("category")
                    }
                ),
                related_questions={}
            )
            return chunk
        except Exception as e:
            utils.log_to_text_file(f"Error converting search result to chunk: {e}")
            return None
        
    def __augment(
        self,
        system_prompt,
        user_prompt
    ):
        augmented_prompts = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return augmented_prompts
    
    def __get_expert_additional_info(
        self,
        texts: List[str],
        emoji = None,
        status = None
    ):
        additional_info = {
            constants.EMOJI: emoji,
            constants.VERIFICATION_STATUS: status,
            "button_titles": bot_config["template_messages"]["expert"]["verification"]["button_titles"],
            "template_name": bot_config["channel_templates"]["expert"]["verification"],
            "template_language": "en",  # Explicitly use string, not object
            "template_parameters": texts
        }
        print(f"🔧 Expert additional_info template_language: {additional_info['template_language']} (type: {type(additional_info['template_language'])})")
        return additional_info
    
    def __get_expert_number_and_type(
        self,
        experts: Dict[str, List[Any]],
        query_type = "medical"
    ):
        expert_type = self._expert_user_types.get(query_type)
        if experts is None:
            return None
        if expert_type not in experts:
            return None
        return experts[expert_type][0], expert_type
    
    def __create_read_reciept_message(
        self,
        message: ByoebMessageContext,
    ) -> ByoebMessageContext:
        read_reciept_message = ByoebMessageContext(
            channel_type=message.channel_type,
            message_category=MessageCategory.READ_RECEIPT.value,
            message_context=MessageContext(
                message_id=message.message_context.message_id,
            )
        )
        return read_reciept_message
    
    async def __create_user_message(
        self,
        message: ByoebMessageContext,
        response_text: str,
        related_questions: List[str] = None,
        emoji = None,
        status = None,
    ) -> ByoebMessageContext:
        from byoeb.chat_app.configuration.dependency_setup import text_translator
        from byoeb.chat_app.configuration.dependency_setup import speech_translator
        user_language = message.user.user_language
        status_info = {
            constants.EMOJI: emoji,
            constants.VERIFICATION_STATUS: status,
        }
        # Always define message_source_text and interactive_list_additional_info
        message_source_text = await text_translator.atranslate_text(
            input_text=response_text,
            source_language="en",
            target_language=user_language
        )
        
        # Simplified to text-only responses
        print(f"� Creating user response message...")
        
        # Set up interactive list if we have related questions
        interactive_list_additional_info = {}
        if related_questions and len(related_questions) > 0:
            print(f"🔗 Adding {len(related_questions)} follow-up questions to interactive list")
            # Get description from bot config
            description = bot_config["template_messages"]["user"]["follow_up_questions_description"].get(user_language, "Related questions")
            interactive_list_additional_info = {
                constants.DESCRIPTION: description,
                constants.ROW_TEXTS: related_questions,
                "has_follow_up_questions": True
            }
        
        user_message = None
        follow_up_message = None
        
        # Create appropriate message type based on whether we have follow-up questions
        # Create appropriate message type based on whether we have follow-up questions
        if related_questions and len(related_questions) > 0:
            user_message = ByoebMessageContext(
                channel_type=message.channel_type,
                message_category=MessageCategory.BOT_TO_USER_RESPONSE.value,
                user=User(
                    user_id=message.user.user_id,
                    user_language=user_language,
                    user_type=self._regular_user_type,
                    phone_number_id=message.user.phone_number_id,
                    last_conversations=message.user.last_conversations
                ),
                message_context=MessageContext(
                    message_id=str(uuid.uuid4()),  # Generate unique message ID
                    message_type=MessageTypes.INTERACTIVE_LIST.value,
                    message_source_text=message_source_text,  # Use full message for body
                    message_english_text=response_text,
                    additional_info={
                        **status_info,
                        **interactive_list_additional_info
                    }
                ),
                reply_context=ReplyContext(
                    reply_id=message.message_context.message_id,
                    reply_type=message.message_context.message_type,
                    reply_english_text=message.message_context.message_english_text,
                    reply_source_text=message.message_context.message_source_text,
                    media_info=message.message_context.media_info
                ),
                incoming_timestamp=message.incoming_timestamp,
            )
        
        # Default case: create regular text message if no specific type was created
        if user_message is None:
            print(f"💬 Creating regular text message")
            user_message = ByoebMessageContext(
                channel_type=message.channel_type,
                message_category=MessageCategory.BOT_TO_USER_RESPONSE.value,
                user=User(
                    user_id=message.user.user_id,
                    user_language=user_language,
                    user_type=self._regular_user_type,
                    phone_number_id=message.user.phone_number_id,
                    last_conversations=message.user.last_conversations
                ),
                message_context=MessageContext(
                    message_id=str(uuid.uuid4()),  # Generate unique message ID
                    message_type=MessageTypes.REGULAR_TEXT.value,
                    message_source_text=message_source_text,
                    message_english_text=response_text,
                    additional_info=status_info
                ),
                reply_context=ReplyContext(
                    reply_id=message.message_context.message_id,
                    reply_type=message.message_context.message_type,
                    reply_english_text=message.message_context.message_english_text,
                    reply_source_text=message.message_context.message_source_text,
                    media_info=message.message_context.media_info
                ),
                incoming_timestamp=message.incoming_timestamp,
            )
            # Preserve _is_new_user flag if present
            if hasattr(message, "_is_new_user"):
                setattr(user_message, "_is_new_user", getattr(message, "_is_new_user"))
        #     user_message = ByoebMessageContext(
        #         channel_type=message.channel_type,
        #         message_category=MessageCategory.BOT_TO_USER_RESPONSE.value,
        #         user=User(
        #             user_id=message.user.user_id,
        #             user_language=user_language,
        #             user_type=self._regular_user_type,
        #             phone_number_id=message.user.phone_number_id,
        #             last_conversations=message.user.last_conversations
        #         ),
        #         message_context=MessageContext(
        #             message_type=MessageTypes.INTERACTIVE_LIST.value,
        #             message_source_text=message_source_text,
        #             message_english_text=response_text,
        #             additional_info={
        #                 **status_info,
        #                 **interactive_list_additional_info
        #             }
        #         ),
        #         reply_context=ReplyContext(
        #             reply_id=message.message_context.message_id,
        #             reply_type=message.message_context.message_type,
        #             reply_english_text=message.message_context.message_english_text,
        #             reply_source_text=message.message_context.message_source_text,
        #             media_info=message.message_context.media_info
        #         ),
        #         incoming_timestamp=message.incoming_timestamp,
        #     )
        
        # Preserve _is_new_user flag if present
        if hasattr(message, "_is_new_user"):
            setattr(user_message, "_is_new_user", getattr(message, "_is_new_user"))
            if follow_up_message:
                setattr(follow_up_message, "_is_new_user", getattr(message, "_is_new_user"))
        
        # For now, return only the primary message to avoid breaking the chain
        # TODO: Implement proper multi-message handling in the future
        if follow_up_message:
            print(f"🎵➡️📋 Note: Follow-up message generated but will be sent separately")
            # For now, combine the audio response with follow-up text in the same message
            # This maintains compatibility with the existing message chain
            user_message.message_context.additional_info["has_follow_up_questions"] = True
            user_message.message_context.additional_info[constants.ROW_TEXTS] = interactive_list_additional_info.get(constants.ROW_TEXTS, [])
        
        print(f"💬 Returning message: {user_message.message_context.message_type}")
        return user_message
    
    def __create_expert_verification_message(
        self,
        message: ByoebMessageContext,
        response_text: str,
        query_type = "medical",
        emoji = None,
        status = None,
    ) -> ByoebMessageContext:
        
        expert_result = self.__get_expert_number_and_type(message.user.experts, query_type)
        if expert_result is None:
            # Create a default expert when no experts are configured
            expert_phone_number_id = "919739811075"  # Full phone number with country code
            expert_type = "medical"
            print(f"👨‍⚕️ Using default expert: {expert_phone_number_id} ({expert_type})")
        else:
            expert_phone_number_id, expert_type = expert_result
            print(f"👨‍⚕️ Using configured expert: {expert_phone_number_id} ({expert_type})")
            
        expert_user_id = hashlib.md5(expert_phone_number_id.encode()).hexdigest()
        print(f"🆔 Generated expert user_id: {expert_user_id} from phone: {expert_phone_number_id}")
        verification_question_template = bot_config["template_messages"]["expert"]["verification"]["Question"]
        verification_bot_answer_template = bot_config["template_messages"]["expert"]["verification"]["Bot_Answer"]
        verification_question = verification_question_template.replace(
            "<QUESTION>",
            message.message_context.message_english_text
        )
        verification_bot_answer = verification_bot_answer_template.replace(
            "<ANSWER>",
            response_text
        )
        verification_footer_message = bot_config["template_messages"]["expert"]["verification"]["footer"]
        additional_info = self.__get_expert_additional_info(
            [verification_question, verification_bot_answer],
            emoji,
            status
        )
        expert_message = verification_question + "\n" + verification_bot_answer + "\n" + verification_footer_message
        new_expert_verification_message = ByoebMessageContext(
            channel_type=message.channel_type,
            message_category=MessageCategory.BOT_TO_EXPERT_VERIFICATION.value,
            user=User(
                user_id=expert_user_id,
                user_type=expert_type,
                user_language='en',
                phone_number_id=expert_phone_number_id
            ),
            message_context=MessageContext(
                message_id=str(uuid.uuid4()),  # Generate unique message ID
                message_type=MessageTypes.INTERACTIVE_BUTTON.value,
                message_source_text=expert_message,
                message_english_text=expert_message,
                additional_info=additional_info
            ),
            incoming_timestamp=message.incoming_timestamp,
        )
        return new_expert_verification_message
    
    @retry(
        stop=stop_after_attempt(3),  # Retry up to 3 times
        wait=wait_exponential(multiplier=1, max=10),  # Exponential backoff with a max wait time of 10 seconds
    )
    async def agenerate_answer(
        self,
        question,
        retrieved_chunks: List[Chunk],
    ):
        from byoeb.chat_app.configuration.dependency_setup import llm_client
        def parse_response(response_text):
            if not response_text:
                return None
                
            # Regular expressions to extract the response and relevance
            response_pattern = r"<BEGIN RESPONSE>(.*?)<END RESPONSE>"
            query_type_pattern = r"<BEGIN QUERY TYPE>(.*?)<END QUERY TYPE>"

            # Extract the response
            response_match = re.search(response_pattern, response_text, re.DOTALL)
            response = response_match.group(1).strip() if response_match else None

            # Extract the relevance
            query_type_match = re.search(query_type_pattern, response_text, re.DOTALL)
            query_type = query_type_match.group(1).strip() if query_type_match else None
            
            # If both patterns failed, return None instead of (None, None)
            if response is None and query_type is None:
                return None
                
            return response, query_type
        
        chunks_list = [chunk.text for chunk in retrieved_chunks]
        system_prompt = bot_config["llm_response"]["answer_prompts"]["system_prompt"]
        template_user_prompt = bot_config["llm_response"]["answer_prompts"]["user_prompt"]
        
        # Replace placeholders with actual values
        chunks = "\n\n".join(chunks_list)  # Better formatting for chunks
        
        # # Debug logging - check template placeholders
        # print(f"\n=== LLM PROMPT DEBUG ===")
        # print(f"Template user prompt: {template_user_prompt}")
        # print(f"Question: {question}")
        # print(f"Chunks (first 200 chars): {chunks[:200]}...")
        
        # Fix placeholder replacement to match template
        user_prompt = template_user_prompt.replace("{context_text}", chunks).replace("{user_question}", question)
        
        # print(f"Final user prompt: {user_prompt}")
        # print(f"System prompt: {system_prompt[:200]}...")
        # print("=== END LLM PROMPT DEBUG ===\n")
        
        augmented_prompts = self.__augment(system_prompt, user_prompt)
        
        # # Log the full prompts being sent to LLM
        # print(f"\n=== FULL LLM INPUT ===")
        # for i, prompt in enumerate(augmented_prompts):
        #     print(f"Message {i+1} ({prompt['role']}):")
        #     print(f"  Content: {prompt['content'][:300]}{'...' if len(prompt['content']) > 300 else ''}")
        # print("=== END FULL LLM INPUT ===\n")
        
        llm_response, response_text = await llm_client.agenerate_response(augmented_prompts)
        tokens = llm_client.get_response_tokens(llm_response)
        utils.log_to_text_file(f"Generated answer tokens: {str(tokens)}")
        
        print(f"Raw LLM response_text: {response_text}")
        
        parse_result = parse_response(response_text)
        if parse_result is None:
            print("Parse result is None, using fallback")
            answer = response_text.strip() if response_text else "I apologize, but I couldn't generate a proper response."
            query_type = "medical"  # Default fallback
        else:
            answer, query_type = parse_result
            print("Generated answer: ", answer)
            print("Query the type: ", query_type)
            if answer is None or query_type is None:
                print("Parsed values are None, using fallback")
                answer = response_text.strip() if response_text else "I apologize, but I couldn't generate a proper response."
                query_type = "medical"  # Default fallback
        return answer, query_type
    
    @retry(
        stop=stop_after_attempt(3),  # Retry up to 3 times
        wait=wait_exponential(multiplier=1, max=10),  # Exponential backoff with a max wait time of 10 seconds
    )
    async def agenerate_follow_up_questions(
        self,
        retrieved_chunks: List[Chunk],
    ):
        from byoeb.chat_app.configuration.dependency_setup import llm_client
        chunks_list = [chunk.text for chunk in retrieved_chunks]
        system_prompt = bot_config["llm_response"]["follow_up_prompts"]["system_prompt"]
        template_user_prompt = bot_config["llm_response"]["follow_up_prompts"]["user_prompt"]
        chunks = ", ".join(chunks_list)
        user_prompt = template_user_prompt.replace("<CHUNKS>", chunks)
        augmented_prompts = self.__augment(system_prompt, user_prompt)
        llm_response, response_text = await llm_client.agenerate_response(augmented_prompts)
        tokens = llm_client.get_response_tokens(llm_response)
        utils.log_to_text_file(f"Generated answer tokens: {str(tokens)}")
        next_questions = re.findall(r"<q_\d+>(.*?)</q_\d+>", response_text)
        if next_questions is None or len(next_questions) != 3:
            raise ValueError("Parsing failed, next_questions.")
        return next_questions
    
    def get_follow_up_questions(
        self,
        user_lang_code: str,
        retrieved_chunks: List[Chunk],
    ):
        random_selection = []
        for retrieved_chunk in retrieved_chunks:
            # Safely check if related_questions attribute exists
            if hasattr(retrieved_chunk, 'related_questions') and retrieved_chunk.related_questions:
                related_questions = retrieved_chunk.related_questions.get(user_lang_code)
                if related_questions is not None and len(related_questions) > 0:
                    random_selection.append(random.choice(related_questions))
        return random_selection
    
    async def __handle_message_generate_workflow(
        self,
        messages: ByoebMessageContext
    ) -> List[ByoebMessageContext]:
        message: ByoebMessageContext = messages[0].model_copy(deep=True)
        
        read_reciept_message = self.__create_read_reciept_message(message)
        message_english = message.message_context.message_english_text
        
        print(f"\n=== RESPONSE GENERATION DEBUG ===")
        print(f"📤 Processing message: '{message_english}'")
        print(f"👤 User: {message.user.phone_number_id} (language: {message.user.user_language})")
        
        print(f"🔍 Retrieving relevant chunks from knowledge base...")
        retrieved_chunks = await self.__aretrieve_chunks(message_english, k=3)
        
        answer, query_type = await self.agenerate_answer(message_english, retrieved_chunks)
        
        # Use LLM-generated follow-up questions for better results
        try:
            related_questions = await self.agenerate_follow_up_questions(retrieved_chunks)
        except Exception as e:
            # Fallback to pre-existing related questions
            related_questions = self.get_follow_up_questions(message.user.user_language, retrieved_chunks)
        byoeb_user_message = await self.__create_user_message(
            message=message,
            response_text=answer,
            emoji=self.USER_PENDING_EMOJI,
            status=constants.PENDING,
            related_questions=related_questions
        )
        print(f"✅ User message created (translated to {message.user.user_language})")
        
        print(f"👨‍⚕️ Creating expert verification message...")
        byoeb_expert_message = self.__create_expert_verification_message(
            message,
            answer,
            query_type,
            self.EXPERT_PENDING_EMOJI,
            constants.PENDING
        )
        print(f"✅ Expert verification message created")
        
        result_messages = [byoeb_user_message, byoeb_expert_message, read_reciept_message]
        print(f"🎉 Complete! Generated {len(result_messages)} messages (user response + expert verification + read receipt)")
        return result_messages
    
    async def handle(
        self,
        messages: List[ByoebMessageContext]
    ) -> Dict[str, Any]:
        if messages is None or len(messages) == 0:
            return {}
        new_messages = []
        try:
            start_time = datetime.now().timestamp()
            new_messages = await self.__handle_message_generate_workflow(messages)
            end_time = datetime.now().timestamp()
            utils.log_to_text_file(f"Generated answer and related questions in {end_time - start_time} seconds")
        except RetryError as e:
            utils.log_to_text_file(f"RetryError in generating response: {e}")
            print("RetryError in generating response: ", e)
            raise e
        except Exception as e:
            utils.log_to_text_file(f"Error in generating response: {e}")
            print("Error in generating response: ", e)
            raise e
        if self._successor:
            return await self._successor.handle(
                new_messages
            )