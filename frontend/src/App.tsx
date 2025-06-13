import { useState } from 'react';
import './App.css';
import Chat from './Chat';
import { Settings24Regular, AddSquare24Regular, MoreHorizontal20Regular } from "@fluentui/react-icons";

function App() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [messages, setMessages] = useState<Array<{ id: string; text: string; sender: 'user' | 'ai' }>>([]);
  const [activeDocuments, setActiveDocuments] = useState<string[]>([]);

  const handleNewChat = () => {
    // Reset all chat state
    setMessages([]);
    setActiveDocuments([]);
    // Close sidebar on mobile after new chat
    if (window.innerWidth <= 768) {
      setIsSidebarOpen(false);
    }
  };

  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen);
  };

  return (
    <div className="app-container">
      <button className="mobile-menu-button" onClick={toggleSidebar}>
        <MoreHorizontal20Regular />
      </button>
      <aside className={`sidebar ${isSidebarOpen ? 'open' : ''}`}>
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
          activeDocuments={activeDocuments}
          setActiveDocuments={setActiveDocuments}
        />
      </main>
    </div>
  );
}

export default App;
