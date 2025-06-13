import React, { useState, useEffect } from 'react';
import CitationsPane from './CitationsPane';

interface ThinkingLog {
  type: string;
  [key: string]: any; // Allows for arbitrary properties on log objects
}

interface ThinkingPaneProps {
  isOpen: boolean;
  onClose: () => void;
  logs: ThinkingLog[]; // Logs for the LATEST interaction from Chat.tsx
  citations: Array<{ type: 'web' | 'document'; title: string; url?: string; }>;
  activeTab?: 'thinking' | 'citations';
  setActiveTab?: React.Dispatch<React.SetStateAction<'thinking' | 'citations'>>;
}

interface ThinkingCard {
  id: string;
  type: 'system_prompt' | 'search' | 'document' | 'tool_invocation' | 'tool_result';
  title?: string;
  content: string;
  timestamp?: string;
}

const ThinkingPane: React.FC<ThinkingPaneProps> = ({ isOpen, onClose, logs, citations, activeTab: propActiveTab, setActiveTab: propSetActiveTab }) => {
  const [localActiveTab, setLocalActiveTab] = useState<'thinking' | 'citations'>('thinking');
  
  // Use props if provided, otherwise use local state
  const activeTab = propActiveTab !== undefined ? propActiveTab : localActiveTab;
  const setActiveTab = propSetActiveTab || setLocalActiveTab;

  const [displayedSystemPrompt, setDisplayedSystemPrompt] = useState<ThinkingCard | null>(null);
  const [interactionCards, setInteractionCards] = useState<ThinkingCard[]>([]);
  const [processedLogCountForCards, setProcessedLogCountForCards] = useState(0);

  useEffect(() => {
    // Reset pane when logs are empty (e.g., new chat started in parent)
    if (logs.length === 0) {
      setDisplayedSystemPrompt(null);
      setInteractionCards([]);
      setProcessedLogCountForCards(0);
    }
  }, [logs]);
  
  // Sync local state with prop if provided
  useEffect(() => {
    if (propActiveTab !== undefined) {
      setLocalActiveTab(propActiveTab);
    }
  }, [propActiveTab]);

  useEffect(() => {
    if (!isOpen || !logs || logs.length === 0) {
      return;
    }

    // 1. Attempt to extract System Prompt if not already displayed
    // This runs only if displayedSystemPrompt is null, checking all current logs.
    if (!displayedSystemPrompt) {
      for (const log of logs) { 
        if (log.type === 'llm_start' && Array.isArray(log.prompts)) {
          const systemMessageObject = log.prompts.find(
            (p: any) => typeof p === 'object' && p !== null && p.content && (p.role === 'system' || (typeof p.type === 'string' && p.type.endsWith('SystemMessage')))
          );
          if (systemMessageObject?.content) {
            const content = typeof systemMessageObject.content === 'string' ? systemMessageObject.content : JSON.stringify(systemMessageObject.content, null, 2);
            setDisplayedSystemPrompt({
              id: `system-prompt-${Date.now()}`,
              type: 'system_prompt',
              title: 'System Prompt',
              content: content
            });
            break; 
          } else if (log.prompts.length > 0 && typeof log.prompts[0] === 'string' && log.prompts[0].toLowerCase().includes('system')) {
             setDisplayedSystemPrompt({
              id: `system-prompt-${Date.now()}`,
              type: 'system_prompt',
              title: 'System Prompt',
              content: log.prompts[0].split(/Human:|AI:/)[0].split('System:')[1]?.trim() || log.prompts[0].trim()
            });
            break;
          }
        }
      }
    }

    // 2. Process NEW logs for Search or Document cards for THIS interaction
    // Only process logs that haven't been processed yet for card generation.
    const newLogsForCards = logs.slice(processedLogCountForCards);
    if (newLogsForCards.length > 0) {
      const currentInteractionNewCards: ThinkingCard[] = [];
      for (const log of newLogsForCards) {
        // Tool invocation card (for logs like { type: 'tool' } or 'tool_start' or 'tool_invocation')
        if (log.type === 'tool' || log.type === 'tool_start' || log.type === 'tool_invocation') {
          // Try to construct a readable invocation string
          let invocationStr = '';
          if (log.type === 'tool_invocation' && log.tool) {
            invocationStr = `Invoking: ${log.tool} with ${typeof log.tool_input === 'string' ? log.tool_input : JSON.stringify(log.tool_input)}`;
          } else if (log.tool && log.input) {
            invocationStr = `Invoking: ${log.tool} with ${typeof log.input === 'string' ? log.input : JSON.stringify(log.input)}`;
          } else if (log.action && log.action.tool && log.action.tool_input) {
            invocationStr = `Invoking: ${log.action.tool} with ${typeof log.action.tool_input === 'string' ? log.action.tool_input : JSON.stringify(log.action.tool_input)}`;
          } else if (log.log) {
            invocationStr = log.log;
          } else {
            invocationStr = JSON.stringify(log, null, 2);
          }
          currentInteractionNewCards.push({
            id: `tool-invocation-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
            type: 'tool_invocation',
            title: 'Tool Invocation',
            content: invocationStr,
          });
        }
        
        // Tool result card
        if (log.type === 'tool_result') {
          currentInteractionNewCards.push({
            id: `tool-result-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
            type: 'tool_result',
            title: 'Tool Result',
            content: `Result: ${typeof log.observation === 'string' ? log.observation : JSON.stringify(log.observation)}`,
          });
        }
        // Existing logic for agent_action
        if (log.type === 'agent_action') {

          // Check if this is a search tool action
          const action = log.action;
          const toolName = action?.tool?.toLowerCase() || '';
          const toolInputContent = action?.tool_input || action?.input;
          
          if (toolName.includes('search') || toolName.includes('bing')) {
            if (toolInputContent) {
              currentInteractionNewCards.push({
                id: `search-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
                type: 'search',
                title: 'Search Tool - Query',
                content: typeof toolInputContent === 'string' ? toolInputContent : JSON.stringify(toolInputContent, null, 2),
              });

            } else {

            }
          } else if (toolName.includes('document')) { 
            if (toolInputContent) {
              currentInteractionNewCards.push({
                id: `document-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
                type: 'document',
                title: 'Document Tool - Retrieved Content',
                content: typeof toolInputContent === 'string' ? toolInputContent : JSON.stringify(toolInputContent, null, 2),
              });

            } else {

            }
          }
        }
        
        // Handle document content from direct tool result or DocumentContent tool
        if ((log.type === 'tool_result' && log.observation && typeof log.observation === 'string' && 
             (log.observation.includes('Document content:') || log.observation.includes('Page'))) || 
            (log.type === 'tool_invocation' && log.tool === 'DocumentContent')) {
          
          let documentContent = '';
          let title = 'Document Content';
          
          if (log.type === 'tool_result' && log.observation) {
            documentContent = log.observation;
          } else if (log.type === 'tool_invocation' && log.tool === 'DocumentContent') {
            title = `Document Tool - ${log.tool_input || 'Query'}`;
            documentContent = `Retrieving document content with query: ${log.tool_input || 'Unknown'}`;
          }
          
          // Check if we already have a document card with similar content to avoid duplicates
          const isDuplicate = currentInteractionNewCards.some(card => 
            card.type === 'document' && 
            card.content === documentContent
          );
          
          if (!isDuplicate && documentContent) {
            currentInteractionNewCards.push({
              id: `document-content-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
              type: 'document',
              title: title,
              content: documentContent,
            });
          }
        }
      }

      if (currentInteractionNewCards.length > 0) {
        setInteractionCards(prevCards => [...prevCards, ...currentInteractionNewCards]);
      }
      setProcessedLogCountForCards(logs.length); // Mark all current logs as processed for card generation
    }
    
  }, [logs, isOpen, displayedSystemPrompt, processedLogCountForCards]);

  if (!isOpen) return null;

  const allCardsToDisplay: ThinkingCard[] = [];
  if (displayedSystemPrompt) {
    allCardsToDisplay.push(displayedSystemPrompt);
  }
  allCardsToDisplay.push(...interactionCards);

  return (
    <div className={`thinking-pane ${isOpen ? 'open' : ''}`}>
      <div className="thinking-pane-header">
        <div className="tab-buttons">
          <button
            className={`tab-button ${activeTab === 'thinking' ? 'active' : ''}`}
            onClick={() => setActiveTab('thinking')}
          >
            Thought Process
          </button>
          <button
            className={`tab-button ${activeTab === 'citations' ? 'active' : ''}`}
            onClick={() => setActiveTab('citations')}
          >
            Citations
          </button>
        </div>
        <button onClick={onClose} className="close-button" aria-label="Close thinking pane">×</button>
      </div>
      <div className="thinking-pane-content">
        {activeTab === 'thinking' ? (
          <>
            {allCardsToDisplay.length === 0 && logs.length === 0 && (
              <div className="no-logs">No thinking logs available yet.</div>
            )}
            {allCardsToDisplay.map((card) => (
              <div key={card.id} className={`thinking-log-item thinking-${card.type}`}>
                <h4>{card.title}</h4>
                <pre>{card.content}</pre>
              </div>
            ))}
          </>
        ) : (
          <CitationsPane citations={citations} />
        )}
      </div>
    </div>
  );
};

export default ThinkingPane;
