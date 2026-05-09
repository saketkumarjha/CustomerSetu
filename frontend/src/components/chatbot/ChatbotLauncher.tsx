import React from "react";

interface ChatbotLauncherProps {
  onClick: () => void;
}

const ChatbotLauncher: React.FC<ChatbotLauncherProps> = ({ onClick }) => (
  <button
    onClick={onClick}
    className="fixed bottom-6 right-6 z-50 bg-white rounded-full shadow-lg p-3 hover:scale-105 transition-transform"
    aria-label="Open AI Chatbot"
    style={{ boxShadow: "0 4px 16px rgba(0,0,0,0.15)" }}
  >
    <img
      src="/ai%20bot.jpg"
      alt="AI Chatbot"
      style={{ width: 36, height: 36, objectFit: "cover", borderRadius: "50%" }}
    />
  </button>
);

export default ChatbotLauncher;
