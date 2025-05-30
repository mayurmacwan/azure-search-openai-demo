import logging
import os
import json
from typing import Any, Optional, Union, List, Dict
from collections.abc import AsyncGenerator as AsyncGeneratorType

from openai import AsyncOpenAI, AsyncStream
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionMessageParam,
)

from approaches.approach import ExtraInfo, DataPoints, ThoughtStep

class PureChatApproach:
    """
    An approach that sends the conversation history directly to OpenAI
    with document retrieval functionality for uploaded files.
    """

    def __init__(
        self,
        *,
        openai_client: AsyncOpenAI,
        chatgpt_model: str,
        chatgpt_deployment: Optional[str] = None,
    ):
        self.openai_client = openai_client
        self.chatgpt_model = chatgpt_model
        self.chatgpt_deployment = chatgpt_deployment
        self.include_token_usage = True
        
        # Fix the data directory path - it should be at the app level, not backend level
        # Current path: /app/backend/approaches/purechat.py
        # We need to go up 3 levels to get to /app/data
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
        print(f"Setting data directory to: {self.data_dir}")

    async def run(
        self,
        messages: list[ChatCompletionMessageParam],
        session_state: Any = None,
        context: dict[str, Any] = {},
    ) -> dict[str, Any]:
        overrides = context.get("overrides", {})
        return await self.run_without_streaming(messages, overrides, session_state)

    async def run_stream(
        self,
        messages: list[ChatCompletionMessageParam],
        session_state: Any = None,
        context: dict[str, Any] = {},
    ) -> AsyncGeneratorType[dict[str, Any], None]:
        overrides = context.get("overrides", {})
        return self.run_with_streaming(messages, overrides, session_state)

    def get_document_content(self) -> str:
        """
        Get content from all documents in the data directory
        """
        try:
            data_dir = self.data_dir
            print(f"\n\n==== DOCUMENT SEARCH ====\nLooking for documents in: {data_dir}")
            logging.info(f"Looking for documents in: {data_dir}")
            
            if not os.path.exists(data_dir):
                print(f"DATA DIRECTORY DOES NOT EXIST: {data_dir}")
                logging.warning(f"Data directory does not exist: {data_dir}")
                # Try to create the directory
                try:
                    os.makedirs(data_dir, exist_ok=True)
                    print(f"Created data directory: {data_dir}")
                except Exception as e:
                    print(f"Failed to create data directory: {str(e)}")
                return ""
            
            # List ALL files in the directory for debugging
            all_files = os.listdir(data_dir)
            print(f"ALL FILES IN DIRECTORY ({len(all_files)}): {all_files}")
            logging.info(f"All files in directory: {all_files}")
            
            # Look for TXT files first (most likely to be readable)
            txt_files = [f for f in all_files if f.endswith(".txt") and not f.startswith(".")]
            print(f"TXT FILES FOUND: {txt_files}")
            
            # If no TXT files, try all non-JSON files
            if not txt_files:
                document_files = [f for f in all_files 
                                if not f.endswith(".json") and not f.startswith(".")]
            else:
                document_files = txt_files
            
            if not document_files:
                print("NO DOCUMENT FILES FOUND")
                logging.info("No document files found in data directory")
                return ""
                
            print(f"DOCUMENT FILES TO PROCESS: {document_files}")
            logging.info(f"Found {len(document_files)} document files: {document_files}")
            
            # Read the content of all documents
            all_content = []
            for filename in document_files:
                try:
                    file_path = os.path.join(data_dir, filename)
                    print(f"READING FILE: {file_path}")
                    
                    # Handle different file types
                    file_extension = os.path.splitext(filename)[1].lower()
                    
                    # For binary files like PDFs, we'll skip them in this direct reading approach
                    if file_extension in [".pdf", ".docx", ".doc", ".pptx", ".xlsx"]:
                        print(f"Skipping binary file {filename}, looking for its extracted text instead")
                        # Look for the extracted text file (should be named with a UUID)
                        # First, try to find the metadata file for this file
                        for meta_file in [f for f in os.listdir(data_dir) if f.endswith(".json")]:
                            try:
                                meta_path = os.path.join(data_dir, meta_file)
                                with open(meta_path, "r") as mf:
                                    metadata = json.load(mf)
                                    if metadata.get("filename") == filename and "text_path" in metadata:
                                        # Found the metadata, now read the text file
                                        text_path = metadata["text_path"]
                                        print(f"Found extracted text at {text_path}")
                                        if os.path.exists(text_path):
                                            with open(text_path, "r", encoding="utf-8", errors="ignore") as tf:
                                                content = tf.read()
                                                print(f"READ {len(content)} CHARACTERS FROM EXTRACTED TEXT")
                                                print(f"CONTENT PREVIEW: {content[:200]}...")
                                                
                                                formatted_content = f"DOCUMENT: {filename}\n\n{content}\n\nEND OF DOCUMENT\n\n"
                                                all_content.append(formatted_content)
                                                logging.info(f"Read {len(content)} characters from extracted text of {filename}")
                                                break
                            except Exception as meta_error:
                                print(f"Error reading metadata file {meta_file}: {str(meta_error)}")
                    else:
                        # For text files, read directly
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                            print(f"READ {len(content)} CHARACTERS FROM {filename}")
                            print(f"CONTENT PREVIEW: {content[:200]}...")
                            
                            formatted_content = f"DOCUMENT: {filename}\n\n{content}\n\nEND OF DOCUMENT\n\n"
                            all_content.append(formatted_content)
                            logging.info(f"Read {len(content)} characters from {filename}")
                            
                    # Also look for UUID.txt files which contain extracted text
                    if not all_content:
                        print("No content found yet, looking for extracted text files")
                        txt_files = [f for f in os.listdir(data_dir) if f.endswith(".txt") and f != filename]
                        for txt_file in txt_files:
                            try:
                                txt_path = os.path.join(data_dir, txt_file)
                                with open(txt_path, "r", encoding="utf-8", errors="ignore") as tf:
                                    content = tf.read()
                                    print(f"READ {len(content)} CHARACTERS FROM {txt_file}")
                                    print(f"CONTENT PREVIEW: {content[:200]}...")
                                    
                                    formatted_content = f"DOCUMENT: {txt_file}\n\n{content}\n\nEND OF DOCUMENT\n\n"
                                    all_content.append(formatted_content)
                                    logging.info(f"Read {len(content)} characters from {txt_file}")
                            except Exception as txt_error:
                                print(f"Error reading text file {txt_file}: {str(txt_error)}")
                        if all_content:
                            print(f"Found {len(all_content)} text files with content")
                            break  # We've found content, no need to process more files
                except Exception as e:
                    error_msg = f"Error reading {filename}: {str(e)}"
                    print(f"ERROR: {error_msg}")
                    logging.error(error_msg)
            
            combined_content = "\n".join(all_content)
            print(f"TOTAL DOCUMENT CONTENT LENGTH: {len(combined_content)} characters")
            print(f"DOCUMENT CONTENT PREVIEW:\n{combined_content[:500]}...\n==== END DOCUMENT SEARCH ====\n\n")
            
            return combined_content
            
            # For each uploaded file, check if it's relevant to the query
            # In a real implementation, you would use embeddings and vector search here
            # For now, we'll just return all documents
            for file_metadata in uploaded_files:
                try:
                    # Read the extracted text file
                    text_path = file_metadata.get("text_path")
                    logging.info(f"Checking text path: {text_path}, exists: {os.path.exists(text_path) if text_path else False}")
                    
                    if text_path and os.path.exists(text_path):
                        with open(text_path, "r", encoding="utf-8", errors="ignore") as f:
                            text_content = f.read()
                            content_preview = text_content[:100] + "..." if len(text_content) > 100 else text_content
                            logging.info(f"Read {len(text_content)} characters from {text_path}. Preview: {content_preview}")
                            
                            # Add the document to relevant docs
                            relevant_docs.append({
                                "filename": file_metadata.get("filename", "Unknown file"),
                                "file_id": file_metadata.get("file_id", ""),
                                "content": text_content[:8000],  # Limit content size
                                "upload_time": file_metadata.get("upload_time", ""),
                            })
                            logging.info(f"Added document {file_metadata.get('filename')} to relevant docs")
                except Exception as doc_error:
                    logging.error(f"Error reading document {file_metadata.get('filename')}: {str(doc_error)}")
            
            logging.info(f"Returning {len(relevant_docs)} relevant documents")
            return relevant_docs
        except Exception as e:
            logging.error(f"Error retrieving documents: {str(e)}")
            return []
    
    def add_document_content_to_messages(self, messages: list[ChatCompletionMessageParam]) -> list[ChatCompletionMessageParam]:
        """
        Add document content to the system message
        """
        print("\n\n==== PREPARING MESSAGES WITH DOCUMENTS ====\n")
        
        # Get document content
        document_content = self.get_document_content()
        print(f"Document content length: {len(document_content)} characters")
        
        if not document_content:
            print("NO DOCUMENT CONTENT FOUND! Using original messages.")
            return messages  # No documents to add
        
        # Create a very explicit system message with document content
        system_content = (
            "You are a helpful assistant that answers questions based on the user's documents. "
            "\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. The following documents have been uploaded by the user and are FULLY AVAILABLE to you in this prompt.\n"
            "2. NEVER say you cannot access the documents or files. They are provided below.\n"
            "3. ALWAYS reference specific content from the documents when answering questions.\n"
            "4. Your first response should acknowledge that you can see the documents.\n"
            "\n\n"
            "DOCUMENT CONTENT BEGINS HERE:\n"
            "==============================================\n"
            f"{document_content}"
            "==============================================\n"
            "DOCUMENT CONTENT ENDS HERE\n\n"
            "Remember to use the content of these documents to answer the user's questions."
        )
        
        # Print the full system message for debugging
        print(f"SYSTEM MESSAGE LENGTH: {len(system_content)} characters")
        print(f"SYSTEM MESSAGE PREVIEW:\n{system_content[:500]}...\n")
        
        # Check if there's already a system message
        has_system_message = any(msg.get("role") == "system" for msg in messages)
        
        # Create a copy of messages to avoid modifying the original
        new_messages = list(messages)
        
        if has_system_message:
            # Replace the existing system message
            for i, msg in enumerate(new_messages):
                if msg.get("role") == "system":
                    print(f"Replacing existing system message at position {i}")
                    new_messages[i]["content"] = system_content
                    break
        else:
            # Create a new system message
            print("Adding new system message at the beginning")
            system_message = {
                "role": "system",
                "content": system_content
            }
            new_messages = [system_message] + new_messages
        
        # Print the final messages structure
        print("\nFINAL MESSAGES STRUCTURE:")
        for i, msg in enumerate(new_messages):
            print(f"Message {i}: role={msg.get('role')}, content_length={len(msg.get('content', ''))}")
        
        print("==== END PREPARING MESSAGES ====\n\n")
        return new_messages
    
    def check_response_for_document_usage(self, response_content: str, documents: List[Dict[str, Any]]) -> bool:
        """
        Check if the response appears to be using document content or is giving a generic
        'I can't access files' response
        """
        if not documents or not response_content:
            return True  # No documents to check against
            
        # Common phrases indicating the model is NOT using the documents
        rejection_phrases = [
            "I can't access", "cannot access", "don't have access", 
            "unable to access", "can't view", "cannot view",
            "don't have the ability", "not able to access",
            "I don't have direct access", "I cannot directly access",
            "I cannot open", "I can't open", "I don't have permission"
        ]
        
        # Check if any rejection phrases are in the response
        for phrase in rejection_phrases:
            if phrase.lower() in response_content.lower():
                logging.warning(f"Found rejection phrase '{phrase}' in model response")
                return False
                
        # Check if any document content appears to be referenced
        # This is a simple check - in a production system you'd want something more sophisticated
        for doc in documents:
            filename = doc.get("filename", "").lower()
            if filename and filename in response_content.lower():
                return True
                
        # If we get here, we're not sure - let's assume it's using the documents
        return True
    
    def create_fallback_response(self, documents: List[Dict[str, Any]], query: str = "") -> str:
        """
        Create a fallback response that explicitly uses document content
        """
        # Start with a clear statement that we have the documents
        response = "I have access to your uploaded documents. Here's what they contain:\n\n"
        
        # Include content from all documents
        for i, doc in enumerate(documents):
            filename = doc.get("filename", f"Document {i+1}")
            content = doc.get("content", "[No content available]")
            
            # Use more content for better context
            preview = content[:1000] + "..." if len(content) > 1000 else content
            response += f"## {filename}\n{preview}\n\n"
        
        # If there's a query, try to answer it directly
        if query and query.strip():
            response += f"\n\nRegarding your question: '{query}'\n"
            response += "Based on the documents above, I can provide this information:\n"
            
            # Simple keyword matching to find relevant parts
            query_words = set(query.lower().split())
            for doc in documents:
                content = doc.get("content", "").lower()
                filename = doc.get("filename", "")
                
                # Find sentences that might contain answers
                sentences = content.split(".")
                relevant_sentences = []
                
                for sentence in sentences:
                    words = set(sentence.split())
                    # If there's word overlap with the query
                    if words.intersection(query_words):
                        relevant_sentences.append(sentence.strip())
                
                if relevant_sentences:
                    response += f"\nFrom {filename}:\n"
                    response += ". ".join(relevant_sentences[:5]) + ".\n"
        
        response += "\nPlease let me know if you have any specific questions about these documents."
        return response
    
    async def run_without_streaming(
        self,
        messages: list[ChatCompletionMessageParam],
        overrides: dict[str, Any],
        session_state: Any = None,
    ) -> dict[str, Any]:
        temperature = overrides.get("temperature", 0.7)
        
        # Create simple data points for any documents
        data_points = DataPoints()
        
        # Create simple thoughts
        extra_info = ExtraInfo(
            data_points=data_points,
            thoughts=[
                ThoughtStep(
                    title="Document Processing",
                    description="Including document content in the conversation",
                )
            ],
        )
        
        # Add document content to messages - simple approach
        enhanced_messages = self.add_document_content_to_messages(messages)
        
        # Call OpenAI API with enhanced messages
        chat_completion_response = await self.create_chat_completion(
            messages=enhanced_messages,
            temperature=temperature,
            should_stream=False
        )
        
        content = chat_completion_response.choices[0].message.content
        role = chat_completion_response.choices[0].message.role
        
        # Update token usage if available
        if self.include_token_usage and chat_completion_response.usage:
            extra_info.thoughts[-1].update_token_usage(chat_completion_response.usage)
        
        chat_app_response = {
            "message": {"content": content, "role": role},
            "context": extra_info,
            "session_state": session_state,
        }
        return chat_app_response

    async def run_with_streaming(
        self,
        messages: list[ChatCompletionMessageParam],
        overrides: dict[str, Any],
        session_state: Any = None,
    ) -> AsyncGeneratorType[dict, None]:
        temperature = overrides.get("temperature", 0.7)
        
        # Create simple data points for any documents
        data_points = DataPoints()
        
        # Create simple thoughts
        extra_info = ExtraInfo(
            data_points=data_points,
            thoughts=[
                ThoughtStep(
                    title="Document Processing",
                    description="Including document content in the conversation",
                )
            ],
        )
        
        # Initial response with role and context
        yield {"delta": {"role": "assistant"}, "context": extra_info, "session_state": session_state}
        
        # Add document content to messages - simple approach
        enhanced_messages = self.add_document_content_to_messages(messages)
        
        # Call OpenAI API with streaming
        chat_stream = await self.create_chat_completion(
            messages=enhanced_messages,
            temperature=temperature,
            should_stream=True
        )
        
        async for event_chunk in chat_stream:
            event = event_chunk.model_dump()
            if event["choices"]:
                completion = {
                    "delta": {
                        "content": event["choices"][0]["delta"].get("content"),
                        "role": event["choices"][0]["delta"].get("role"),
                    }
                }
                yield completion
            else:
                # Final chunk with usage information
                if event_chunk.usage and extra_info.thoughts and self.include_token_usage:
                    extra_info.thoughts[-1].update_token_usage(event_chunk.usage)
                    yield {"delta": {"role": "assistant"}, "context": extra_info, "session_state": session_state}

    async def create_chat_completion(
        self,
        messages: list[ChatCompletionMessageParam],
        temperature: float = 0.7,
        should_stream: bool = False,
    ) -> Union[ChatCompletion, AsyncStream[ChatCompletionChunk]]:
        """Create a chat completion using the OpenAI API"""
        try:
            # Log the API request details
            print("\n\n==== OPENAI API REQUEST ====\n")
            print(f"Model: {self.chatgpt_deployment or self.chatgpt_model}")
            print(f"Temperature: {temperature}")
            print(f"Streaming: {should_stream}")
            print(f"Number of messages: {len(messages)}")
            
            # Print message details
            total_tokens = 0
            for i, msg in enumerate(messages):
                content_length = len(msg.get('content', ''))
                total_tokens += content_length // 4  # Rough estimate
                print(f"Message {i}: role={msg.get('role')}, content_length={content_length} chars")
            
            print(f"Estimated total tokens: ~{total_tokens}")
            print("==== END API REQUEST ====\n\n")
            
            if should_stream:
                return await self.openai_client.chat.completions.create(
                    model=self.chatgpt_deployment or self.chatgpt_model,
                    messages=messages,
                    temperature=temperature,
                    stream=True,
                )
            else:
                response = await self.openai_client.chat.completions.create(
                    model=self.chatgpt_deployment or self.chatgpt_model,
                    messages=messages,
                    temperature=temperature,
                )
                
                # Log the API response
                print("\n\n==== OPENAI API RESPONSE ====\n")
                print(f"Response model: {response.model}")
                if response.usage:
                    print(f"Tokens: prompt={response.usage.prompt_tokens}, completion={response.usage.completion_tokens}, total={response.usage.total_tokens}")
                
                content = response.choices[0].message.content
                print(f"Response content length: {len(content)} chars")
                print(f"Response preview: {content[:200]}...")
                print("==== END API RESPONSE ====\n\n")
                
                return response
        except Exception as e:
            error_msg = f"Error calling OpenAI API: {str(e)}"
            print(f"\n\nAPI ERROR: {error_msg}\n\n")
            logging.error(error_msg)
            raise
