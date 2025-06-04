from typing import List, Dict, Any
from langchain.schema import HumanMessage, AIMessage
from langchain_openai import AzureChatOpenAI
import os

def convert_chat_history(chat_history: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Convert chat history to the format expected by Langchain."""
    result = []
    for message in chat_history:
        if message["role"] == "user":
            result.append(HumanMessage(content=message["content"]))
        elif message["role"] == "assistant":
            result.append(AIMessage(content=message["content"]))
    return result

def create_llm(callback_manager=None):
    """Create an instance of AzureChatOpenAI.
    
    Args:
        callback_manager: Optional callback manager for capturing thinking logs
    """
    return AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        temperature=0.7,
        callback_manager=callback_manager
    )

def format_document_context(document_content):
    """Format document content as context for the LLM."""
    import logging
    
    if not document_content:
        logging.error("Document content is None or empty")
        return ""
    
    logging.info(f"Document content type: {type(document_content)}")
    logging.info(f"Document content keys: {document_content.keys() if isinstance(document_content, dict) else 'Not a dict'}")
    
    # The document content should be a dict with a 'content' key that contains a list of pages
    if isinstance(document_content, dict) and "content" in document_content:
        context = "Document content:\n\n"
        for page in document_content["content"]:
            context += f"Page {page['page_num']}:\n{page['text']}\n\n"
        
        logging.info(f"Formatted context length: {len(context)}")
        return context
    else:
        logging.error(f"Unexpected document content structure: {document_content}")
        return ""
