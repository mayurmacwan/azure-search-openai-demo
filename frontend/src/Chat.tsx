import React, { useState, useRef } from 'react';
import type { FormEvent, ChangeEvent } from 'react';
import ThinkingPane from './ThinkingPane';
import { ClipboardBulletList20Regular, DocumentCopy20Regular, Lightbulb20Regular, Attach28Regular, Send28Filled, Checkmark20Regular } from '@fluentui/react-icons';
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { AnswerLoading } from './components/AnswerLoading';
import Tooltip from './components/Tooltip';

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'ai';
}

interface Document {
  doc_id: string;
  filename: string;
  num_chunks: number;
  uploaded_at: string;
}

interface ThinkingLog {
  type: string;
  [key: string]: any;
}

interface ChatProps {
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  activeDocument: string | null;
  setActiveDocument: React.Dispatch<React.SetStateAction<string | null>>;
}

const Chat: React.FC<ChatProps> = ({ messages, setMessages, activeDocument, setActiveDocument }) => {
  const [input, setInput] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploadStatus, setUploadStatus] = useState<string>('');
  const [thinkingLogs, setThinkingLogs] = useState<ThinkingLog[]>([]);
  const [isThinkingPaneOpen, setIsThinkingPaneOpen] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'thinking' | 'citations'>('thinking');
  const [citations, setCitations] = useState<Array<{ type: 'web' | 'document'; title: string; url?: string; }>>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [copied, setCopied] = useState(false);

  const handleCopy = (textToCopy: string) => {
    navigator.clipboard
      .writeText(textToCopy)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      })
      .catch(err => console.error("Failed to copy text: ", err));
  };
  
  
  const fetchDocuments = async () => {
    try {
      const response = await fetch('/api/list_documents', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      setDocuments(data.documents || []);
    } catch (error) {
      console.error('Failed to fetch documents:', error);
    }
  };
  
  // Fetch documents when component mounts
  React.useEffect(() => {
    fetchDocuments();
  }, []);
  
  // Reset thinking logs and citations when messages are cleared (new chat)
  React.useEffect(() => {
    if (messages.length === 0) {
      setThinkingLogs([]);
      setCitations([]);
      setIsThinkingPaneOpen(false);
    }
  }, [messages]);
  
  const handleFileUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    
    const file = files[0];
    const supportedTypes = [
      'application/pdf',
      'image/jpeg',
      'image/png',
      'image/bmp',
      'image/tiff',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      'application/vnd.ms-powerpoint'
    ];
    
    if (!supportedTypes.includes(file.type)) {
      setUploadStatus('Unsupported file type. Please upload PDF, JPEG, PNG, TIFF, BMP, or Office documents (DOCX, DOC, XLSX, XLS, PPTX, PPT)');
      return;
    }
    
    setIsLoading(true);
    setUploadStatus('Uploading and processing document...');
    
    try {
      // Read the file as base64
      const reader = new FileReader();
      reader.onload = async (e) => {
        if (!e.target || typeof e.target.result !== 'string') return;
        
        // Extract the base64 data (remove the data URL prefix)
        const base64Data = e.target.result.split(',')[1];
        
        // Send the file to the backend
        const response = await fetch('/api/upload_pdf', {  // Keep endpoint name for backward compatibility
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            pdf_base64: base64Data,  // Keep parameter name for backward compatibility
            filename: file.name
          }),
        });
        
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Update documents list
        await fetchDocuments();
        
        // Set the active document
        setActiveDocument(data.doc_id);
        
        // Add a system message about the uploaded document
        const systemMessage: Message = {
          id: Date.now().toString() + '-system',
          text: `Document "${file.name}" has been uploaded and processed. The AI will now use this document to answer your questions.`,
          sender: 'ai',
        };
        setMessages(prevMessages => [...prevMessages, systemMessage]);
        
        // Add document to citations
        setCitations(prev => [...prev, { type: 'document', title: file.name }]);
        
        setUploadStatus('Document uploaded successfully!');
      };
      
      reader.readAsDataURL(file);
    } catch (error) {
      console.error('Failed to upload document:', error);
      setUploadStatus(`Error: ${error instanceof Error ? error.message : 'Could not upload the document.'}`);
    } finally {
      setIsLoading(false);
      // Reset the file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };
  
  const handlePaperclipClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    
    // Clear upload status when a new prompt is submitted
    setUploadStatus('');

    const userMessage: Message = {
      id: Date.now().toString() + '-user',
      text: input,
      sender: 'user',
    };
    setMessages((prevMessages) => [...prevMessages, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // Get all previous messages to send as history
      const historyToSend = [...messages];
      
      // Prepare request body with message and history
      const requestBody: any = { 
        message: input,
        history: historyToSend
      };
      
      // Add document ID if there's an active document
      if (activeDocument) {
        requestBody.doc_id = activeDocument;
      }
      
      // Azure Functions usually serve under /api prefix by default
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      // Store thinking logs if available - append to existing logs
      if (data.thinking_logs && data.thinking_logs.length > 0) {
        setThinkingLogs(prevLogs => [...prevLogs, ...data.thinking_logs]);
        
        // Extract web citations from thinking logs
        const newWebCitations = data.thinking_logs
          .filter((log: any) => log.type === 'search_results' && Array.isArray(log.results))
          .flatMap((log: any) => {
            return log.results.map((result: any) => ({
              type: 'web' as const,
              title: result.title || 'Web Search Result',
              url: result.link
            }));
          });
        
        if (newWebCitations.length > 0) {
          setCitations(prev => [...prev, ...newWebCitations]);
        }
      }
      
      const aiMessage: Message = {
        id: Date.now().toString() + '-ai',
        text: data.message,
        sender: 'ai',
      };
      setMessages((prevMessages) => [...prevMessages, aiMessage]);
    } catch (error) {
      console.error('Failed to send message:', error);
      const errorMessage: Message = {
        id: Date.now().toString() + '-error',
        text: `Error: ${error instanceof Error ? error.message : 'Could not connect to the bot.'}`,
        sender: 'ai', // Display error as an AI message for simplicity
      };
      setMessages((prevMessages) => [...prevMessages, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const toggleThinkingPane = (tab?: 'thinking' | 'citations') => {
    setIsThinkingPaneOpen(!isThinkingPaneOpen);
    if (tab) {
      setActiveTab(tab);
    }
  };

  return (
    <div className={`chat-container ${isThinkingPaneOpen ? 'with-thinking-pane' : ''}`}>
      <div>
        {activeDocument && documents.length > 0 && (
          <div className="active-document">
            <span>Active document: </span>
            <strong>
              {documents.find(doc => doc.doc_id === activeDocument)?.filename || 'Unknown'}
            </strong>
          </div>
        )}
        {activeDocument && documents.length > 0 && (
          <div className="active-document">
            <span>Active document: </span>
            <strong>
              {documents.find(doc => doc.doc_id === activeDocument)?.filename || 'Unknown'}
            </strong>
          </div>
        )}
      </div>
      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="empty-chat-message">
            <div>QR</div>
            <h1>QualRisk AI Assistant</h1>
            <p>Ask me anything about your documents or how I can assist you with your enterprise needs.</p>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className={`message-bubble ${msg.sender}`}>
              {msg.sender === 'ai' ? (
                <div className="message-avatar">QR</div>
              ) : null}
              <div className={`message ${msg.sender}`}>
                <ReactMarkdown children={msg.text} rehypePlugins={[rehypeRaw]} remarkPlugins={[remarkGfm]} />
                {msg.sender === 'ai' ? (
                  <div className={'message-toolbar'}>
                    {copied ? (
                      <Tooltip text="Copied to clipboard">
                        <Checkmark20Regular
                          className={'message-toolbar-button'}
                          onClick={() => handleCopy(msg.text)}
                        />
                      </Tooltip>
                    ) : (
                      <Tooltip text="Copy to clipboard">
                        <DocumentCopy20Regular
                        className={'message-toolbar-button'}
                        onClick={() => handleCopy(msg.text)}
                      />
                      </Tooltip>
                    )}
                    <Tooltip text="Show thought process"> 
                      <Lightbulb20Regular
                        className={'message-toolbar-button'}
                        onClick={() => toggleThinkingPane('thinking')}
                    />
                    </Tooltip>
                    <Tooltip text="Show citations">
                    <ClipboardBulletList20Regular
                      className={'message-toolbar-button'}
                      onClick={() => toggleThinkingPane('citations')}
                    />
                    </Tooltip>
                  </div> 
                ) : null}
              </div>
            </div>
          ))
        )}
        {isLoading && <AnswerLoading />}
        {uploadStatus && <div className="upload-status">{uploadStatus}</div>}
      </div>
      <form onSubmit={handleSubmit} className="chat-input-form">
        <div className="input-container">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !(e.shiftKey || e.altKey)) {
                e.preventDefault();
                if (input.trim() && !isLoading) {
                  handleSubmit(e);
                }
              }
            }}
            placeholder="Message Qualrisk Assistant..."
            disabled={isLoading}
            rows={1}
          />
          <div className="chat-buttons">
            <Tooltip text="Upload document to AI Assistant">
              <button 
                type="button" 
                onClick={handlePaperclipClick}
                disabled={isLoading}
              >
                <Attach28Regular primaryFill="white" />
              </button>
            </Tooltip>
            <button 
              type="submit" 
              disabled={isLoading || !input.trim()}
            >
              <Send28Filled primaryFill="white" />
            </button>
          </div>
        </div>
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileUpload}
          accept=".pdf,.jpg,.jpeg,.png,.bmp,.tiff,.docx,.doc,.xlsx,.xls,.pptx,.ppt"
          style={{ display: 'none' }}
        />
      </form>
      <ThinkingPane 
        isOpen={isThinkingPaneOpen} 
        onClose={() => setIsThinkingPaneOpen(false)} 
        logs={thinkingLogs}
        citations={citations}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
      />
    </div>
  );
};

export default Chat;
