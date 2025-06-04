import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

class DocumentStore:
    """Simple in-memory document store to keep track of uploaded documents."""
    
    def __init__(self):
        # In-memory storage for document metadata
        self.documents: List[Dict[str, Any]] = []
    
    def add_document(self, doc_id: str, filename: str, num_chunks: int) -> None:
        """Add a document to the store."""
        self.documents.append({
            "doc_id": doc_id,
            "filename": filename,
            "num_chunks": num_chunks,
            "uploaded_at": datetime.now().isoformat()
        })
        logging.info(f"Added document {filename} with ID {doc_id}")
    
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID."""
        for doc in self.documents:
            if doc["doc_id"] == doc_id:
                return doc
        return None
    
    def get_all_documents(self) -> List[Dict[str, Any]]:
        """Get all documents."""
        return self.documents
    
    def remove_document(self, doc_id: str) -> bool:
        """Remove a document by ID."""
        for i, doc in enumerate(self.documents):
            if doc["doc_id"] == doc_id:
                self.documents.pop(i)
                logging.info(f"Removed document with ID {doc_id}")
                return True
        return False
