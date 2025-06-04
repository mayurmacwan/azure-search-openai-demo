import azure.functions as func
import logging
import json
import os
import base64

from langchain.callbacks.base import BaseCallbackHandler
from langchain.callbacks.manager import CallbackManager
from langchain.agents import initialize_agent, AgentType
from langchain_community.utilities.bing_search import BingSearchAPIWrapper
import langchain.tools as lc_tools  # Import as module to avoid scope issues
from langchain.memory import ConversationBufferMemory
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from utils.pdf_processor import DocumentProcessor
from utils.document_store import DocumentStore
from utils.chat_utils import create_llm, format_document_context

app = func.FunctionApp()
document_processor = DocumentProcessor()
document_store = DocumentStore()

# CORS headers
def add_cors_headers(response):
    """Add CORS headers to the response."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS, GET"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

# Handle CORS preflight requests
def handle_cors_preflight(req):
    """Handle CORS preflight requests."""
    if req.method == "OPTIONS":
        return func.HttpResponse(
            "",
            status_code=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS, GET",
                "Access-Control-Allow-Headers": "Content-Type",
            }
        )
    return None

@app.route(route="upload_pdf", methods=["POST", "OPTIONS"])
def upload_pdf(req: func.HttpRequest) -> func.HttpResponse:
    # Handle CORS preflight
    cors_response = handle_cors_preflight(req)
    if cors_response:
        return cors_response

    try:
        req_body = req.get_json()
    except ValueError:
        logging.error("Invalid JSON received")
        return add_cors_headers(func.HttpResponse(
            "Please pass a valid JSON object in the request body",
            status_code=400
        ))
    
    doc_base64 = req_body.get('pdf_base64')  # Keep the parameter name for backward compatibility
    filename = req_body.get('filename')
    
    if not doc_base64 or not filename:
        return add_cors_headers(func.HttpResponse(
            "Please provide both 'pdf_base64' and 'filename' in the request body",
            status_code=400
        ))
    
    try:
        # Decode the base64 document
        doc_bytes = base64.b64decode(doc_base64)
        
        # Process the document
        result = document_processor.process_document(doc_bytes, filename)
        
        if not result:
            return add_cors_headers(func.HttpResponse(
                "Failed to process document. No content extracted.",
                status_code=400
            ))
        
        # Add to document store
        document_store.add_document(result["doc_id"], result["filename"], result["num_chunks"])
        
        return add_cors_headers(func.HttpResponse(
            json.dumps({
                "success": True,
                "doc_id": result["doc_id"],
                "filename": result["filename"],
                "num_chunks": result["num_chunks"]
            }),
            mimetype="application/json"
        ))
        
    except ValueError as ve:
        logging.error(f"Validation error: {str(ve)}")
        return add_cors_headers(func.HttpResponse(
            str(ve),
            status_code=400
        ))
    except Exception as e:
        logging.error(f"Error processing document: {e}")
        return add_cors_headers(func.HttpResponse(
            f"Error processing document: {str(e)}",
            status_code=500
        ))

@app.route(route="list_documents", methods=["GET", "OPTIONS"])
def list_documents(req: func.HttpRequest) -> func.HttpResponse:
    # Handle CORS preflight
    cors_response = handle_cors_preflight(req)
    if cors_response:
        return cors_response
    
    try:
        documents = document_store.get_all_documents()
        return add_cors_headers(func.HttpResponse(
            json.dumps(documents),
            mimetype="application/json"
        ))
    except Exception as e:
        logging.error(f"Error listing documents: {e}")
        return add_cors_headers(func.HttpResponse(
            f"Error listing documents: {str(e)}",
            status_code=500
        ))

@app.route(route="chat", methods=["POST", "OPTIONS"])
def chat(req: func.HttpRequest) -> func.HttpResponse:
    # Handle CORS preflight
    cors_response = handle_cors_preflight(req)
    if cors_response:
        return cors_response

    logging.info('Python HTTP trigger function processed a request.')

    try:
        req_body = req.get_json()
    except ValueError:
        logging.error("Invalid JSON received")
        return add_cors_headers(func.HttpResponse(
             "Please pass a valid JSON object in the request body",
             status_code=400
        ))
    
    user_message = req_body.get('message')
    chat_history = req_body.get('history', [])
    doc_id = req_body.get('doc_id')
    
    # Check if we should use an agent with tools
    use_agent = True  # We'll use an agent by default to enable search capabilities

    if not user_message:
        logging.error("Message not found in request")
        return add_cors_headers(func.HttpResponse(
             "Please pass a 'message' in the request body",
             status_code=400
        ))

    try:
        # Create a callback handler to capture thinking logs
        class ThinkingLogHandler(BaseCallbackHandler):
            def __init__(self):
                self.logs = []
                
            def on_llm_start(self, serialized, prompts, **kwargs):
                self.logs.append({"type": "llm_start", "prompts": prompts})
                
            def on_llm_end(self, response, **kwargs):
                self.logs.append({"type": "llm_end", "response": response.dict()})
                
            def on_llm_error(self, error, **kwargs):
                self.logs.append({"type": "llm_error", "error": str(error)})
                
            def on_chain_start(self, serialized, inputs, **kwargs):
                self.logs.append({"type": "chain_start", "inputs": inputs})
                
            def on_chain_end(self, outputs, **kwargs):
                self.logs.append({"type": "chain_end", "outputs": outputs})
                
            def on_tool_start(self, serialized, input_str, **kwargs):
                self.logs.append({"type": "tool_start", "input": input_str})
                
            def on_tool_end(self, output, **kwargs):
                self.logs.append({"type": "tool_end", "output": output})
                
            def on_text(self, text, **kwargs):
                self.logs.append({"type": "text", "text": text})
                
            def on_agent_action(self, action, **kwargs):
                self.logs.append({"type": "agent_action", "action": action})
                
            def on_agent_finish(self, finish, **kwargs):
                self.logs.append({"type": "agent_finish", "finish": finish})
        
        # Initialize the callback handler
        thinking_logs = ThinkingLogHandler()
        callback_manager = CallbackManager([thinking_logs])
        
        # Initialize the LLM
        llm = create_llm(callback_manager=callback_manager)
        
        # Set up Bing Search as a tool
        try:
            # Initialize Bing Search
            search = BingSearchAPIWrapper(
                k=4,
                bing_subscription_key=os.getenv("BING_SUBSCRIPTION_KEY"),
                bing_search_url=os.getenv("BING_SEARCH_URL"),
                search_kwargs = {'mkt': 'en-GB', 'setLang': 'en-GB'}
            )
            
            # Create a search tool with a wrapper to handle both AI text and citations
            def search_with_results(query: str) -> tuple[str, list]:
                results = search.results(query, num_results=4)
                # Format results as plain text for AI
                formatted_results = []
                for result in results:
                    formatted_results.append(f"Title: {result['title']}\nSummary: {result['snippet']}\n")
                return '\n\n'.join(formatted_results), results

            # Wrapper to handle the tuple return and log the full results
            def search_wrapper(query: str) -> str:
                text_result, full_results = search_with_results(query)
                # Log the full results for citation purposes
                thinking_logs.logs.append({
                    "type": "search_results",
                    "results": full_results
                })
                return text_result

            search_tool = lc_tools.Tool(
                name="BingSearch",
                description="Useful for searching the web for current information. Use this when you need to find information about recent events or when you need to answer questions about current facts.",
                func=search_wrapper
            )
            
            # Log that we've set up the search tool
            thinking_logs.logs.append({"type": "tool_setup", "tool": "BingSearch"})
            
        except Exception as e:
            logging.error(f"Error setting up Bing Search: {e}")
            search_tool = None
            use_agent = False
        
        # Check if we have a document context
        document_context = ""
        if doc_id:
            logging.info(f"Attempting to retrieve document with ID: {doc_id}")
            
            # Get the document content
            document_content = document_processor.get_document_content(doc_id)
            
            if document_content:
                logging.info(f"Document content retrieved. Length: {len(document_content)} chunks")
                # Log the first few chunks safely
                if isinstance(document_content, dict) and "content" in document_content:
                    for i, chunk in enumerate(document_content["content"][:2]):
                        logging.info(f"Sample chunk {i}: {str(chunk)[:100]}...")
                else:
                    logging.info(f"Document content type: {type(document_content)}")
                    if isinstance(document_content, list) and len(document_content) > 0:
                        logging.info(f"First item type: {type(document_content[0])}")
                        logging.info(f"Sample: {str(document_content[0])[:100]}...")
                
                # Format document content as context
                document_context = format_document_context(document_content)
                logging.info(f"Document context formatted. Length: {len(document_context)} characters")
                logging.info(f"Sample context: {document_context[:200]}...")
            else:
                logging.error(f"Document {doc_id} content not found or empty")
                
                # Check if document exists in document store
                doc_info = document_store.get_document(doc_id)
                if doc_info:
                    logging.info(f"Document exists in document store: {doc_info}")
                else:
                    logging.error(f"Document {doc_id} not found in document store")
        
        # Determine the appropriate system message based on context
        if document_context:
            # If we have document context
            system_message = f"""You are an AI assistant that helps with questions about documents. 
            Use the following document content to answer the user's question. 
            If the answer is not in the document, you can search the web using the BingSearch tool.
            
            {document_context}
            """
        else:
            # If no document context, use a simple chat completion with search capability
            system_message = "You are a helpful AI assistant with the ability to search the web for current information. If you don't know the answer to a question, you can use the BingSearch tool to look it up."
            
        # Create a list of tools for the agent
        tools = []
        
        # Always add search tool if available
        if search_tool:
            tools.append(search_tool)
        
        # Create a document tool if document context is available
        if document_context:
            # Instead of creating a nested function, use a simple lambda
            try:
                # Create a tool that returns the document content
                doc_tool = lc_tools.Tool(
                    name="DocumentContent",
                    description="Useful for getting information from the uploaded document. Use this when you need to answer questions about the document content.",
                    func=lambda x: document_context  # Simple lambda that returns the document content
                )
                tools.append(doc_tool)
                logging.info("Added document tool to agent")
            except Exception as e:
                logging.error(f"Error creating document tool: {e}")
                # Continue without the document tool if there's an error
        
        # Use agent if we have any tools available
        if use_agent and tools:
            logging.info(f"Using agent with {len(tools)} tools")
            
            # Create a simpler agent with the tools
            # Use the structured OPENAI_FUNCTIONS agent type
            from langchain.agents import AgentExecutor, create_openai_functions_agent
            from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
            
            # Create a system message that instructs the agent on how to use the tools
            system_message = "You are a helpful AI assistant. "
            if document_context:
                system_message += "A document has been uploaded. Use the DocumentContent tool to access its contents when answering questions about the document. "
            if search_tool:
                system_message += "You can search the web using the BingSearch tool when you need current information. "
            
            # Create a prompt for the agent
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_message),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad")
            ])
            
            # Set up memory for the agent
            memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
            
            # Convert existing chat history to the format expected by ConversationBufferMemory
            if chat_history:
                logging.info(f"Converting {len(chat_history)} messages from chat history")
                for msg in chat_history:
                    if 'sender' in msg and 'text' in msg:
                        if msg['sender'] == 'ai':
                            memory.chat_memory.add_ai_message(msg['text'])
                        else:  # user message
                            memory.chat_memory.add_user_message(msg['text'])
                    elif 'role' in msg and 'content' in msg:
                        if msg['role'] == 'assistant':
                            memory.chat_memory.add_ai_message(msg['content'])
                        elif msg['role'] == 'user':
                            memory.chat_memory.add_user_message(msg['content'])
            
            # Create the agent
            agent = create_openai_functions_agent(llm, tools, prompt)
            agent_executor = AgentExecutor(
                agent=agent, 
                tools=tools, 
                verbose=True, 
                handle_parsing_errors=True,
                return_intermediate_steps=True,  # Make sure to return intermediate steps
                memory=memory  # Add memory to the agent executor
            )
            
            # Run the agent with the user message
            try:
                # Use the agent_executor instead of the agent directly
                response = agent_executor.invoke({
                    "input": user_message
                })
                
                # Explicitly log intermediate steps
                if "intermediate_steps" in response:
                    logging.info(f"Agent used {len(response['intermediate_steps'])} intermediate steps")
                    # Add intermediate steps to thinking logs
                    for i, step in enumerate(response["intermediate_steps"]):
                        action, observation = step
                        thinking_logs.logs.append({
                            "type": "tool_invocation",
                            "tool": action.tool,
                            "tool_input": action.tool_input,
                            "step": i
                        })
                        thinking_logs.logs.append({
                            "type": "tool_result",
                            "observation": observation,
                            "step": i
                        })
                else:
                    logging.warning("No intermediate_steps in agent response")
                
                # Extract the response text
                if isinstance(response, dict) and "output" in response:
                    response_text = response["output"]
                else:
                    response_text = str(response)
                    
                logging.info("Agent successfully generated a response")
            except Exception as e:
                logging.error(f"Error running agent: {e}")
                # Fall back to regular LLM if agent fails
                response_text = "I encountered an error while processing your request. Falling back to standard response.\n\n"
                
                # Fall back to regular chat completion
                messages = [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ]
                response = llm.invoke(messages)
                response_text += response.content
        else:
            # No tools available, use direct LLM completion
            logging.info("Using direct LLM completion (no tools available)")
            
            # Create a system message that includes document context if available
            if document_context:
                system_message = f"You are a helpful AI assistant. You have access to the following document content:\n\n{document_context}\n\nPlease use this information to answer the user's questions."
            else:
                system_message = "You are a helpful AI assistant."

            
            # Convert chat history to the format expected by the LLM
            messages = [
                {"role": "system", "content": system_message}
            ]
            
            # Add chat history - convert from frontend format to LLM format
            for msg in chat_history:
                if 'sender' in msg and 'text' in msg:
                    role = 'assistant' if msg['sender'] == 'ai' else 'user'
                    messages.append({"role": role, "content": msg['text']})
                elif 'role' in msg and 'content' in msg:
                    messages.append(msg)
            
            # Add the current user message
            messages.append({"role": "user", "content": user_message})
            
            # Get response from the LLM
            try:
                response = llm.invoke(messages)
                response_text = response.content
                logging.info("LLM successfully generated a response")
            except Exception as e:
                logging.error(f"Error getting LLM response: {e}")
                response_text = "I'm sorry, I encountered an error while processing your request."
        
        # Utility to safely serialize logs (avoid non-serializable objects)
        def safe_serialize_logs(logs):
            import copy
            import inspect
            def make_serializable(obj):
                if isinstance(obj, dict):
                    return {k: make_serializable(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [make_serializable(i) for i in obj]
                elif hasattr(obj, 'dict') and callable(getattr(obj, 'dict', None)):
                    try:
                        return obj.dict()
                    except Exception:
                        return str(obj)
                elif hasattr(obj, '__dict__'):
                    try:
                        return dict(obj.__dict__)
                    except Exception:
                        return str(obj)
                elif inspect.isfunction(obj) or inspect.ismethod(obj):
                    return str(obj)
                else:
                    try:
                        json.dumps(obj)
                        return obj
                    except Exception:
                        return str(obj)
            return [make_serializable(log) for log in logs]

        # Serialize logs safely for frontend
        safe_logs = safe_serialize_logs(thinking_logs.logs)
        logging.debug(f"Returning thinking_logs: {json.dumps(safe_logs)[:1000]}")
        return add_cors_headers(func.HttpResponse(
            json.dumps({
                "message": response_text,
                "thinking_logs": safe_logs
            }),
            mimetype="application/json"
        ))

    except Exception as e:
        logging.error(f"Error processing chat: {e}")
        return add_cors_headers(func.HttpResponse(
             f"Error processing chat: {str(e)}",
             status_code=500
        ))

