import React, { createContext, useContext, useState, useCallback, useRef } from "react";

interface ChatContextType {
    resetChat: () => void;
    setResetChatFunction: (fn: () => void) => void;
}

const ChatContext = createContext<ChatContextType>({
    resetChat: () => {},
    setResetChatFunction: () => {}
});

export const ChatProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    // Use useRef to store the function to prevent unnecessary re-renders
    const resetChatFunctionRef = useRef<() => void>(() => {});
    
    // Memoize the resetChat function to prevent unnecessary re-renders
    const resetChat = useCallback(() => {
        resetChatFunctionRef.current();
    }, []);

    // Memoize the setResetChatFunction to prevent unnecessary re-renders
    const setResetChatFunction = useCallback((fn: () => void) => {
        if (fn) {
            resetChatFunctionRef.current = fn;
        }
    }, []);

    // Create a stable context value object that doesn't change on re-renders
    const contextValue = React.useMemo(() => ({
        resetChat,
        setResetChatFunction
    }), [resetChat, setResetChatFunction]);

    return (
        <ChatContext.Provider value={contextValue}>
            {children}
        </ChatContext.Provider>
    );
};

export const useChatContext = () => useContext(ChatContext);
