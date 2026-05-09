import React, { useState } from "react";
import LanguageSelector from "./LanguageSelector";
import RuleBasedChatbot from "./RuleBasedChatbot";

interface ChatbotWindowProps {
  onClose: () => void;
}

const ChatbotWindow: React.FC<ChatbotWindowProps> = ({ onClose }) => {
  const [language, setLanguage] = useState<string | null>(null);

  return (
    <div className="fixed bottom-20 right-6 z-50 w-80 bg-white rounded-xl shadow-2xl flex flex-col overflow-hidden animate-slideInUp">
      <div className="flex justify-between items-center p-3 border-b">
        <span className="font-semibold">AI Chatbot</span>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-700">
          ✕
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        {!language ? (
          <LanguageSelector onSelect={setLanguage} />
        ) : (
          <RuleBasedChatbot language={language} />
        )}
      </div>
    </div>
  );
};

export default ChatbotWindow;
