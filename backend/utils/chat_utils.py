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
    
    # The document content should be a dict with a 'content' key
    if isinstance(document_content, dict):
        if "content" in document_content:
            # If content is a string (from Document Intelligence), use it directly
            if isinstance(document_content["content"], str):
                return f"Document content:\n\n{document_content['content']}"
            # If content is a list (from old PDF format), format it page by page
            elif isinstance(document_content["content"], list):
                context = "Document content:\n\n"
                for page in document_content["content"]:
                    if isinstance(page, dict) and "page_num" in page and "text" in page:
                        context += f"Page {page['page_num']}:\n{page['text']}\n\n"
                    else:
                        context += f"{str(page)}\n\n"
                return context
        else:
            logging.error("Document content dict does not have 'content' key")
            return ""
    else:
        logging.error(f"Unexpected document content structure: {document_content}")
        return ""
