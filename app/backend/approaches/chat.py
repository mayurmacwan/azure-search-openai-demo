import asyncio
from flask import current_app
import os
import logging

class ChatApproach:
    def __init__(self, openai_client):
        self.openai_client = openai_client

    async def run_assistant(self, history, stream, user_message):
        """Uses Azure OpenAI Assistants API to handle the conversation using uploaded files"""
        try:
            # Get the OpenAI client
            openai_client = self.openai_client
            
            # Get the assistant ID from app config
            assistant_id = current_app.config.get("OPENAI_ASSISTANT_ID")
            if not assistant_id:
                current_app.logger.warning("No assistant ID found in app config")
                return {
                    "choices": [{
                        "message": {
                            "content": "No assistant has been created yet. Please upload a file first."
                        }
                    }]
                }, None
            
            # Extract thread_id from history
            thread_id = None
            if isinstance(history, list) and history:
                for item in history:
                    if isinstance(item, dict) and "thread_id" in item:
                        thread_id = item.get("thread_id")
                        break
            
            if not thread_id:
                # Create a new thread
                current_app.logger.info("Creating new thread in Azure OpenAI")
                try:
                    thread = await openai_client.beta.threads.create()
                    thread_id = thread.id
                    current_app.logger.info(f"Created thread with ID: {thread_id}")
                except Exception as thread_error:
                    current_app.logger.exception(f"Error creating thread: {str(thread_error)}")
                    return {
                        "choices": [{
                            "message": {
                                "content": f"Error creating conversation thread: {str(thread_error)}"
                            }
                        }]
                    }, None
            else:
                current_app.logger.info(f"Using existing thread with ID: {thread_id}")
            
            # Add the user message to the thread
            current_app.logger.info(f"Adding message to thread: {user_message[:50]}...")
            try:
                await openai_client.beta.threads.messages.create(
                    thread_id=thread_id,
                    role="user",
                    content=user_message
                )
            except Exception as msg_error:
                current_app.logger.exception(f"Error adding message to thread: {str(msg_error)}")
                return {
                    "choices": [{
                        "message": {
                            "content": f"Error sending your message: {str(msg_error)}"
                        }
                    }]
                }, None
            
            # Run the assistant
            current_app.logger.info(f"Running assistant {assistant_id} on thread {thread_id}")
            
            # Get the model deployment name from env variables for run
            deployment_name = os.getenv("AZURE_OPENAI_CHATGPT_DEPLOYMENT")
            if not deployment_name:
                current_app.logger.warning("AZURE_OPENAI_CHATGPT_DEPLOYMENT not set for run, using gpt-4-turbo")
                deployment_name = "gpt-4-turbo"
            
            try:
                run = await openai_client.beta.threads.runs.create(
                    thread_id=thread_id,
                    assistant_id=assistant_id,
                    model=deployment_name  # Explicitly specify the model for Azure OpenAI
                )
            except Exception as run_error:
                current_app.logger.exception(f"Error starting assistant run: {str(run_error)}")
                return {
                    "choices": [{
                        "message": {
                            "content": f"Error processing your request: {str(run_error)}"
                        }
                    }]
                }, None
            
            # Poll for the completion
            current_app.logger.info(f"Waiting for run {run.id} to complete")
            try:
                max_retries = 30  # Avoid infinite loop
                retry_count = 0
                while retry_count < max_retries:
                    retry_count += 1
                    try:
                        run_status = await openai_client.beta.threads.runs.retrieve(
                            thread_id=thread_id,
                            run_id=run.id
                        )
                        current_app.logger.info(f"Run status: {run_status.status}")
                        if run_status.status == "completed":
                            break
                        elif run_status.status in ["failed", "cancelled", "expired"]:
                            error_message = f"The assistant encountered an error: {run_status.status}"
                            if hasattr(run_status, 'last_error') and run_status.last_error:
                                error_message += f" - {run_status.last_error}"
                            current_app.logger.error(error_message)
                            return {
                                "choices": [{
                                    "message": {
                                        "content": error_message
                                    }
                                }]
                            }, None
                        # Wait a short time before polling again
                        await asyncio.sleep(1)
                    except Exception as poll_error:
                        current_app.logger.warning(f"Error polling run status: {str(poll_error)}")
                        await asyncio.sleep(1)
                
                if retry_count >= max_retries:
                    return {
                        "choices": [{
                            "message": {
                                "content": "The assistant is taking too long to respond. Please try again later."
                            }
                        }]
                    }, None
            except Exception as wait_error:
                current_app.logger.exception(f"Error waiting for run completion: {str(wait_error)}")
                return {
                    "choices": [{
                        "message": {
                            "content": f"Error while waiting for response: {str(wait_error)}"
                        }
                    }]
                }, None
            
            # Get the messages from the thread
            try:
                current_app.logger.info(f"Getting messages from thread {thread_id}")
                messages = await openai_client.beta.threads.messages.list(
                    thread_id=thread_id
                )
                
                # Get the last assistant message
                assistant_messages = [msg for msg in messages.data if msg.role == "assistant"]
                if not assistant_messages:
                    current_app.logger.warning("No assistant messages found in thread")
                    return {
                        "choices": [{
                            "message": {
                                "content": "The assistant didn't provide a response."
                            }
                        }]
                    }, None
                
                # Return the first content block as the response
                assistant_message = assistant_messages[0]
                response_content = ""
                for content in assistant_message.content:
                    if content.type == "text":
                        response_content = content.text.value
                        break
                
                current_app.logger.info(f"Got response: {response_content[:50]}...")
                return {
                    "choices": [{
                        "message": {
                            "content": response_content
                        }
                    }],
                    "thread_id": thread_id
                }, None
            except Exception as msg_list_error:
                current_app.logger.exception(f"Error getting messages from thread: {str(msg_list_error)}")
                return {
                    "choices": [{
                        "message": {
                            "content": f"Error retrieving assistant response: {str(msg_list_error)}"
                        }
                    }]
                }, None
        except Exception as e:
            current_app.logger.exception(f"Error using Azure OpenAI Assistant API: {str(e)}")
            return {
                "choices": [{
                    "message": {
                        "content": f"An error occurred with Azure OpenAI: {str(e)}"
                    }
                }]
            }, None

    async def run_conversation(self, history, overrides, auth_claims):
        # Check if we have files uploaded to the assistant
        assistant_id = current_app.config.get("OPENAI_ASSISTANT_ID")
        
        # If we have an assistant (meaning files have been uploaded), use the Assistants API
        if assistant_id:
            current_app.logger.info(f"Using Azure OpenAI Assistant {assistant_id} for conversation")
            if not isinstance(history, list):
                current_app.logger.warning(f"Expected history to be a list, got {type(history)}")
                history = []
            
            # Extract user message
            user_message = ""
            if history and isinstance(history[-1], dict):
                user_message = history[-1].get("user", "")
            
            if not user_message:
                return {
                    "answer": "No question was provided. Please ask a question.",
                    "data_points": []
                }, None
                
            result, extra_info = await self.run_assistant(history, overrides.get("stream", False), user_message)
            
            # Save thread_id to history for future messages
            if result.get("thread_id") and isinstance(history, list) and history:
                if isinstance(history[-1], dict):
                    history[-1]["thread_id"] = result.get("thread_id")
                
            return {"data_points": [], "answer": result["choices"][0]["message"]["content"]}, extra_info
        
        # Otherwise, fall back to the original behavior for non-file questions
        current_app.logger.info("No Azure OpenAI Assistant available, falling back to original behavior")
        # Continue with existing code 