import React, { useState } from "react";

interface RuleBasedChatbotProps {
  language: string;
}

interface Message {
  sender: "bot" | "user";
  text: string;
}

const greetings: Record<string, string> = {
  English: "Hello! How can I help you today?",
  Hindi: "नमस्ते! मैं आपकी कैसे मदद कर सकता हूँ?",
  Telugu: "హలో! నేను మీకు ఎలా సహాయపడగలను?",
  // ...add more translations as needed
};

const RuleBasedChatbot: React.FC<RuleBasedChatbotProps> = ({ language }) => {
  const [messages, setMessages] = useState<Message[]>([
    { sender: "bot", text: greetings[language] || greetings["English"] },
  ]);
  const [input, setInput] = useState("");

  // Simple rule-based responses
  function getBotResponse(userText: string): string {
    if (/account|service/i.test(userText)) {
      return language === "Hindi"
        ? "कृपया अपनी खाता संबंधी समस्या बताएं।"
        : "Please describe your account-related issue.";
    }
    if (/video|chat/i.test(userText)) {
      return language === "Hindi"
        ? "वीडियो चैट के लिए कृपया अपनी समस्या लिखें।"
        : "For video chat, please describe your issue.";
    }
    return language === "Hindi"
      ? "माफ़ कीजिए, कृपया अधिक जानकारी दें।"
      : "Sorry, I didn't understand. Please provide more details.";
  }

  const handleSend = () => {
    if (!input.trim()) return;
    const userMsg = { sender: "user", text: input };
    const botMsg = { sender: "bot", text: getBotResponse(input) };
    setMessages([...messages, userMsg, botMsg]);
    setInput("");
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto mb-2">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`mb-1 ${msg.sender === "bot" ? "text-left" : "text-right"}`}
          >
            <span
              className={`inline-block px-3 py-1 rounded-lg ${msg.sender === "bot" ? "bg-blue-50 text-gray-800" : "bg-blue-500 text-white"}`}
            >
              {msg.text}
            </span>
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          className="flex-1 border rounded px-2 py-1"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Type your message..."
        />
        <button
          className="bg-blue-500 text-white px-3 py-1 rounded"
          onClick={handleSend}
        >
          Send
        </button>
      </div>
    </div>
  );
};

export default RuleBasedChatbot;
