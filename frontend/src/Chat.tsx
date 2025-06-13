import React, { useState, useRef } from 'react';
import type { FormEvent, ChangeEvent } from 'react';
import ThinkingPane from './ThinkingPane';
import { 
  ClipboardBulletList20Regular, 
  DocumentCopy20Regular, 
  Lightbulb20Regular, 
  Attach28Regular, 
  Send28Filled, 
  Checkmark20Regular,
  ArrowDownload20Regular,
  Search24Regular
} from '@fluentui/react-icons';
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
  activeDocuments: string[];
  setActiveDocuments: React.Dispatch<React.SetStateAction<string[]>>;
}

const Chat: React.FC<ChatProps> = ({ messages, setMessages, activeDocuments, setActiveDocuments }) => {
  const [input, setInput] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploadStatus, setUploadStatus] = useState<string>('');
  const [thinkingLogs, setThinkingLogs] = useState<ThinkingLog[]>([]);
  const [isThinkingPaneOpen, setIsThinkingPaneOpen] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'thinking' | 'citations'>('thinking');
  const [citations, setCitations] = useState<Array<{ type: 'web' | 'document'; title: string; url?: string; docId?: string; }>>([]);
  const [isWebSearchEnabled, setIsWebSearchEnabled] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [copied, setCopied] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);

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
    
    setIsLoading(true);
    setUploadStatus('Uploading and processing documents...');
    
    const uploadedDocIds: string[] = [];
    const uploadErrors: string[] = [];
    
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
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
        uploadErrors.push(`${file.name}: Unsupported file type`);
        continue;
      }
      
      try {
        // Read the file as base64
        const base64Data = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = (e) => {
            if (!e.target || typeof e.target.result !== 'string') {
              reject(new Error('Failed to read file'));
              return;
            }
            resolve(e.target.result.split(',')[1]);
          };
          reader.onerror = () => reject(reader.error);
          reader.readAsDataURL(file);
        });
        
        // Send the file to the backend
        const response = await fetch('/api/upload_pdf', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            pdf_base64: base64Data,
            filename: file.name
          }),
        });
        
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        uploadedDocIds.push(data.doc_id);
        
      } catch (error) {
        console.error(`Failed to upload ${file.name}:`, error);
        uploadErrors.push(`${file.name}: ${error instanceof Error ? error.message : 'Upload failed'}`);
      }
    }
    
    // Update documents list
    await fetchDocuments();
    
    // Update active documents
    if (uploadedDocIds.length > 0) {
      setActiveDocuments(prev => [...prev, ...uploadedDocIds]);
      
      // Add a system message about the uploaded documents
      const systemMessage: Message = {
        id: Date.now().toString() + '-system',
        text: `${uploadedDocIds.length} document(s) have been uploaded and processed. The AI will now use these documents to answer your questions.${
          uploadErrors.length > 0 ? `\n\nErrors:\n${uploadErrors.join('\n')}` : ''
        }`,
        sender: 'ai',
      };
      setMessages(prevMessages => [...prevMessages, systemMessage]);
    }
    
    setUploadStatus(
      uploadedDocIds.length > 0
        ? `Successfully uploaded ${uploadedDocIds.length} document(s)${
            uploadErrors.length > 0 ? ` with ${uploadErrors.length} error(s)` : ''
          }`
        : 'No documents were uploaded successfully'
    );
    
    setIsLoading(false);
    // Reset the file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
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
    
    // Add user message to chat
    const userMessage: Message = {
      id: Date.now().toString(),
      text: input.trim(),
      sender: 'user'
    };
    setMessages(prevMessages => [...prevMessages, userMessage]);
    setInput('');
    
    setIsLoading(true);
    
    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage.text,
          history: messages,
          doc_ids: activeDocuments,  // Changed from doc_id to doc_ids
          use_web_search: isWebSearchEnabled  // Add web search flag
        }),
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      // Add AI response to chat
      const aiMessage: Message = {
        id: Date.now().toString(),
        text: data.message,
        sender: 'ai'
      };
      setMessages(prevMessages => [...prevMessages, aiMessage]);
      
      // Update thinking logs
      if (data.thinking_logs) {
        setThinkingLogs(data.thinking_logs);
        setIsThinkingPaneOpen(true);
        
        // Extract citations from thinking logs
        const newCitations: Array<{ type: 'web' | 'document'; title: string; url?: string; docId?: string }> = [];
        
        // Process thinking logs for citations
        data.thinking_logs.forEach((log: any) => {
          if (log.type === 'search_results' && log.results) {
            log.results.forEach((result: any) => {
              newCitations.push({
                type: 'web',
                title: result.title,
                url: result.url
              });
            });
          } else if (log.type === 'tool_invocation' && log.tool === 'DocumentContent') {
            // Add document citation with docId
            const docId = log.docId;
            const doc = documents.find(d => d.doc_id === docId);
            if (doc) {
              newCitations.push({
                type: 'document',
                title: doc.filename,
                docId: docId
              });
            }
          }
        });
        
        setCitations(newCitations);
      }
      
    } catch (error) {
      console.error('Error:', error);
      // Add error message to chat
      const errorMessage: Message = {
        id: Date.now().toString(),
        text: 'I apologize, but I encountered an error while processing your request. Please try again.',
        sender: 'ai'
      };
      setMessages(prevMessages => [...prevMessages, errorMessage]);
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

  const handleDownload = async () => {
    if (messages.length === 0) return;
    
    setIsDownloading(true);
    try {
      const response = await fetch('/api/download_chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          messages: messages
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      // Convert base64 to blob
      const byteCharacters = atob(data.document);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });

      // Create download link
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = `chat_conversation_${new Date().toISOString().split('T')[0]}.docx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(downloadUrl);
    } catch (error) {
      console.error('Failed to download chat:', error);
      // You might want to show an error message to the user here
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className={`chat-container ${isThinkingPaneOpen ? 'with-thinking-pane' : ''}`}>
      <div className="chat-header">
        {activeDocuments.length > 0 && documents.length > 0 && (
          <div className="active-documents">
            <span>Active documents: </span>
            <strong>
              {documents.filter(doc => activeDocuments.includes(doc.doc_id)).map(doc => doc.filename).join(', ')}
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
      
      {/* Web Search Warning */}
      {isWebSearchEnabled && (
        <div className="web-search-warning">
          <strong>⚠️ Warning - Do not enter or upload any confidential data when using web search.</strong>
        </div>
      )}
      
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
            {messages.length > 0 && (
              <Tooltip text={isDownloading ? "Downloading..." : "Download conversation"}>
                <button 
                  type="button"
                  onClick={handleDownload}
                  disabled={isDownloading}
                  className="action-button"
                  aria-label="Download conversation"
                >
                  <ArrowDownload20Regular primaryFill="white" />
                </button>
              </Tooltip>
            )}
            <Tooltip text={isWebSearchEnabled ? "Disable web search" : "Enable web search"}>
              <button 
                type="button" 
                onClick={() => setIsWebSearchEnabled(!isWebSearchEnabled)}
                disabled={isLoading}
                className={`action-button ${isWebSearchEnabled ? 'web-search-active' : ''}`}
                aria-label={isWebSearchEnabled ? "Disable web search" : "Enable web search"}
              >
                <Search24Regular primaryFill="white" />
              </button>
            </Tooltip>
            <Tooltip text="Upload document to AI Assistant">
              <button 
                type="button" 
                onClick={handlePaperclipClick}
                disabled={isLoading}
                className="action-button"
              >
                <Attach28Regular primaryFill="white" />
              </button>
            </Tooltip>
            <button 
              type="submit" 
              disabled={isLoading || !input.trim()}
              className="action-button"
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
          multiple
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
