import React, { useState } from "react";

const LANGUAGES = [
  { label: "English", flag: "🇬🇧" },
  { label: "Hindi", flag: "🇮🇳" },
  { label: "Telugu", flag: "🇮🇳" },
  { label: "Marathi", flag: "🇮🇳" },
  { label: "Bengali", flag: "🇮🇳" },
  { label: "Tamil", flag: "🇮🇳" },
  { label: "Kannada", flag: "🇮🇳" },
  { label: "Malayalam", flag: "🇮🇳" },
  { label: "Gujarati", flag: "🇮🇳" },
  { label: "Punjabi", flag: "🇮🇳" },
  { label: "Urdu", flag: "🇮🇳" },
  { label: "Odia", flag: "🇮🇳" },
  { label: "Assamese", flag: "🇮🇳" },
];

interface LanguageSelectorProps {
  onSelect: (lang: string) => void;
}

const LanguageSelector: React.FC<LanguageSelectorProps> = ({ onSelect }) => {
  const [hovered, setHovered] = useState<string | null>(null);

  return (
    <div className="flex flex-col h-full overflow-y-auto px-4 py-4">
      {/* Welcome card */}
      <div
        className="rounded-xl p-4 mb-4 text-center"
        style={{
          background: "linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%)",
        }}
      >
        <div className="text-3xl mb-2">🏦</div>
        <div className="font-semibold text-blue-800 text-sm mb-1">
          Welcome to CustomerSetu
        </div>
        <div className="text-xs text-blue-600">
          Union Bank of India's AI Complaint Guide
        </div>
      </div>

      <div className="text-center text-sm font-medium text-gray-600 mb-3">
        🌐 Choose your language
      </div>

      <div className="grid grid-cols-2 gap-2">
        {LANGUAGES.map(({ label, flag }) => (
          <button
            key={label}
            onClick={() => onSelect(label)}
            onMouseEnter={() => setHovered(label)}
            onMouseLeave={() => setHovered(null)}
            className="flex items-center gap-2 px-3 py-2.5 rounded-xl border text-sm font-medium transition-all duration-150"
            style={{
              borderColor: hovered === label ? "#2563eb" : "#e2e8f0",
              background: hovered === label ? "#eff6ff" : "#f8fafc",
              color: hovered === label ? "#1d4ed8" : "#374151",
              transform: hovered === label ? "scale(1.02)" : "scale(1)",
            }}
          >
            <span className="text-base">{flag}</span>
            <span>{label}</span>
          </button>
        ))}
      </div>

      <div className="mt-4 pt-3 border-t text-center">
        <div className="text-xs text-gray-400">
          24×7 Helpline:{" "}
          <span className="font-semibold text-gray-600">1800 22 2244</span>
        </div>
      </div>
    </div>
  );
};

export default LanguageSelector;
