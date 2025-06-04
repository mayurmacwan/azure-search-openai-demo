import { useState } from 'react';
import './App.css';
import Chat from './Chat';
import { Chat24Regular, Settings24Regular, AddSquare24Regular } from "@fluentui/react-icons";

function App() {
  const handleNewChat = () => {
    // Reset all chat state
    setMessages([]);
    setActiveDocument(null);
  };

  const [messages, setMessages] = useState<Array<{ id: string; text: string; sender: 'user' | 'ai' }>>([]);
  const [activeDocument, setActiveDocument] = useState<string | null>(null);

  return (
    <div className="app-container">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-logo">QR</div>
          <h1>Qualrisk AI</h1>
        </div>
        <div className="sidebar-content">
          <button className="new-chat-button" onClick={handleNewChat}>
            <AddSquare24Regular style={{ marginRight: '8px' }}/>
            <span>New Chat</span>
          </button>
          <div className="recent-chats">
            <h2>RECENT CHATS</h2>
            {/* Recent chats will go here */}
          </div>
        </div>
        <div className="sidebar-footer">
          <button className="settings-button">
            <Settings24Regular style={{ marginRight: '10px', color: 'rgba(255, 255, 255, 0.7)' }} />
            <span>Settings</span>
          </button>
        </div>
      </aside>
      <main className="main-content">
        <Chat 
          messages={messages}
          setMessages={setMessages}
          activeDocument={activeDocument}
          setActiveDocument={setActiveDocument}
        />
      </main>
    </div>
  );
}

export default App;
