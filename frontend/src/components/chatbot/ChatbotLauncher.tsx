import React from "react";

interface ChatbotLauncherProps {
  onClick: () => void;
}

const ChatbotLauncher: React.FC<ChatbotLauncherProps> = ({ onClick }) => (
  <button
    onClick={onClick}
    aria-label="Open CustomerSetu AI Chatbot"
    className="fixed bottom-6 right-6 z-50 flex items-center justify-center transition-transform hover:scale-105 active:scale-95"
    style={{
      width: 56,
      height: 56,
      borderRadius: "50%",
      background: "linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%)",
      boxShadow: "0 4px 20px rgba(37,99,235,0.45)",
      border: "none",
      cursor: "pointer",
    }}
  >
    {/* Chat bubble icon */}
    <svg
      width="26"
      height="26"
      viewBox="0 0 24 24"
      fill="none"
      stroke="white"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>

    {/* Online dot */}
    <span
      style={{
        position: "absolute",
        top: 4,
        right: 4,
        width: 10,
        height: 10,
        borderRadius: "50%",
        background: "#22c55e",
        border: "2px solid white",
      }}
    />
  </button>
);

export default ChatbotLauncher;
