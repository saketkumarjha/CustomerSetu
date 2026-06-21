import React, { useState } from "react";
import LanguageSelector from "./LanguageSelector";
import RuleBasedChatbot from "./RuleBasedChatbot";

interface ChatbotWindowProps {
  onClose: () => void;
}

const ChatbotWindow: React.FC<ChatbotWindowProps> = ({ onClose }) => {
  const [language, setLanguage] = useState<string | null>(null);

  return (
    <div
      className="fixed bottom-20 right-4 z-50 flex flex-col rounded-2xl shadow-2xl overflow-hidden"
      style={{
        width: 360,
        height: 560,
        background: "#ffffff",
        border: "1px solid #e2e8f0",
        animation: "slideInUp 0.2s ease-out",
      }}
    >
      {/* ── Header ── */}
      <div
        className="flex items-center justify-between px-4 py-3 flex-shrink-0"
        style={{
          background: "linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%)",
        }}
      >
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center text-lg">
            🏦
          </div>
          <div>
            <div className="text-white font-semibold text-sm leading-tight">
              CustomerSetu
            </div>
            <div className="text-blue-200 text-xs leading-tight">
              Union Bank of India · AI Help
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {language && (
            <button
              onClick={() => setLanguage(null)}
              title="Change language"
              className="text-blue-200 hover:text-white text-xs px-2 py-1 rounded-full border border-blue-400 hover:border-white transition"
            >
              🌐 {language}
            </button>
          )}
          <button
            onClick={onClose}
            className="text-blue-200 hover:text-white w-7 h-7 flex items-center justify-center rounded-full hover:bg-white/20 transition text-lg leading-none"
            aria-label="Close"
          >
            ×
          </button>
        </div>
      </div>

      {/* ── Body ── */}
      <div className="flex-1 flex flex-col min-h-0">
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
