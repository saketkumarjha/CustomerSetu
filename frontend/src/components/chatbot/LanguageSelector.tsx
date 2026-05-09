import React from "react";

const LANGUAGES = [
  "English",
  "Hindi",
  "Telugu",
  "Marathi",
  "Gujarati",
  "Bengali",
  "Kannada",
  "Tamil",
  "Malayalam",
  "Urdu",
  "Punjabi",
  "Oriya",
  "Konkani",
  "Assamese",
  "Bhojpuri",
  "Maithili",
  "Nepali",
  "Sindhi",
  "Kashmiri",
  "Khasi",
  "Tulu",
  "Santhali",
];

interface LanguageSelectorProps {
  onSelect: (lang: string) => void;
}

const LanguageSelector: React.FC<LanguageSelectorProps> = ({ onSelect }) => (
  <div>
    <div className="mb-2 text-gray-700">
      Please choose your preferred language to communicate
    </div>
    <div className="flex flex-wrap gap-2">
      {LANGUAGES.map((lang) => (
        <button
          key={lang}
          onClick={() => onSelect(lang)}
          className="border border-blue-400 text-blue-600 rounded-full px-3 py-1 hover:bg-blue-50 transition"
        >
          {lang}
        </button>
      ))}
    </div>
  </div>
);

export default LanguageSelector;
