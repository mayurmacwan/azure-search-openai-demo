import logging
import uuid
import os
import mimetypes
from typing import Dict, List, Any, Optional
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, DocumentContentFormat, AnalyzeResult
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential

class DocumentProcessor:
    """Process documents using Azure Document Intelligence."""
    
    def __init__(self):
        # In-memory storage for document content
        self.documents: Dict[str, Dict[str, Any]] = {}
        self.doc_client = self.get_document_client()
    
    def get_document_client(self):
        """Get Azure Document Intelligence client using Key Vault credentials."""
        try:
            # Check if we're running in Azure Functions
            is_azure_functions = os.environ.get('FUNCTIONS_WORKER_RUNTIME') is not None
            
            if is_azure_functions:
                # In Azure Functions, use managed identity
                credential = DefaultAzureCredential()
            else:
                # For local development, use Azure CLI
                credential = DefaultAzureCredential(exclude_managed_identity_credential=True)
                
            keyvault_url = f"https://{os.environ['KEY_VAULT_NAME']}.vault.azure.net"
            secret_client = SecretClient(vault_url=keyvault_url, credential=credential)
            
            endpoint = secret_client.get_secret("claims-pulse-di-endpoint").value
            key = secret_client.get_secret("claims-pulse-di-key").value
            
            return DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))
        except Exception as e:
            logging.error(f"Error getting document client: {str(e)}")
            raise

    def is_supported_format(self, filename: str) -> bool:
        """Check if the file format is supported."""
        supported_extensions = {
            '.pdf', '.jpeg', '.jpg', '.png', '.bmp', '.tiff', 
            '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt'
        }
        ext = os.path.splitext(filename)[1].lower()
        return ext in supported_extensions

    def process_document(self, doc_bytes: bytes, filename: str) -> Optional[Dict[str, Any]]:
        """Process a document using Azure Document Intelligence."""
        try:
            # Check if file format is supported
            if not self.is_supported_format(filename):
                raise ValueError(f"Unsupported file format: {filename}")
            
            # Log file details
            file_size = len(doc_bytes)
            logging.info(f"Processing file: {filename}, Size: {file_size} bytes")
            
            # Process the document using prebuilt-layout model
            poller = self.doc_client.begin_analyze_document(
                "prebuilt-layout",
                AnalyzeDocumentRequest(bytes_source=doc_bytes),
                output_content_format=DocumentContentFormat.MARKDOWN
            )
            
            result: AnalyzeResult = poller.result()
            
            # Generate a unique ID for this document
            doc_id = str(uuid.uuid4())
            
            # Store the document content in memory
            self.documents[doc_id] = {
                "filename": filename,
                "content": result.content,
                "pages": len(result.pages) if hasattr(result, 'pages') else 1
            }
            
            return {
                "doc_id": doc_id,
                "filename": filename,
                "num_chunks": len(result.pages) if hasattr(result, 'pages') else 1
            }
            
        except Exception as e:
            logging.error(f"Error processing document {filename}: {str(e)}")
            raise
    
    def get_document_content(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get the content of a document by ID."""
        return self.documents.get(doc_id)
