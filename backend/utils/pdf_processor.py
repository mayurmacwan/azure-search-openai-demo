import PyPDF2
import logging
import tempfile
import uuid
import os
from typing import Dict, List, Any

class PDFProcessor:
    def __init__(self):
        # In-memory storage for document content
        self.documents: Dict[str, Dict[str, Any]] = {}
    
    def process_pdf(self, pdf_bytes, filename):
        """Process a PDF file and extract its text content."""
        try:
            # Create a temporary file to save the PDF
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_bytes)
                temp_path = temp_file.name
            
            # Extract text from the PDF
            pdf_text = self._extract_text_from_pdf(temp_path)
            
            # Clean up the temporary file
            os.unlink(temp_path)
            
            if not pdf_text:
                logging.warning(f"No text extracted from PDF: {filename}")
                return None
            
            # Generate a unique ID for this document
            doc_id = str(uuid.uuid4())
            
            # Store the document content in memory
            self.documents[doc_id] = {
                "filename": filename,
                "content": pdf_text,
                "pages": len(pdf_text)
            }
            
            return {
                "doc_id": doc_id,
                "filename": filename,
                "num_chunks": len(pdf_text)
            }
            
        except Exception as e:
            logging.error(f"Error processing PDF: {e}")
            raise
    
    def _extract_text_from_pdf(self, pdf_path):
        """Extract text from a PDF file, returning a list of pages."""
        try:
            pdf_pages = []
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page_num in range(len(reader.pages)):
                    page = reader.pages[page_num]
                    text = page.extract_text()
                    if text.strip():  # Only add non-empty pages
                        pdf_pages.append({
                            "page_num": page_num + 1,
                            "text": text
                        })
            return pdf_pages
        except Exception as e:
            logging.error(f"Error extracting text from PDF: {e}")
            return []
    
    def get_document_content(self, doc_id):
        """Get the content of a document by ID."""
        return self.documents.get(doc_id)
