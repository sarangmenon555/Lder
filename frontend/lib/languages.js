export const LANGUAGES = [
  { code: "ml", name: "Malayalam", native: "മലയാളം" },
  { code: "ta", name: "Tamil", native: "தமிழ்" },
  { code: "te", name: "Telugu", native: "తెలుగు" },
  { code: "hi", name: "Hindi", native: "हिन्दी" },
  { code: "kn", name: "Kannada", native: "ಕನ್ನಡ" },
];

const TEXT = {
  ml: {
    hello: "നമസ്കാരം",
    hear: "ചോദ്യം കേൾക്കാം",
    speak: "സംസാരിക്കാൻ അമർത്തുക",
    stop: "നിർത്താൻ അമർത്തുക",
  },
  ta: {
    hello: "வணக்கம்",
    hear: "கேள்வியைக் கேளுங்கள்",
    speak: "பேச அழுத்தவும்",
    stop: "நிறுத்த அழுத்தவும்",
  },
  te: {
    hello: "నమస్కారం",
    hear: "ప్రశ్నను వినండి",
    speak: "మాట్లాడటానికి నొక్కండి",
    stop: "ఆపడానికి నొక్కండి",
  },
  hi: {
    hello: "नमस्ते",
    hear: "सवाल सुनें",
    speak: "बोलने के लिए दबाएँ",
    stop: "रोकने के लिए दबाएँ",
  },
  kn: {
    hello: "ನಮಸ್ಕಾರ",
    hear: "ಪ್ರಶ್ನೆ ಕೇಳಿ",
    speak: "ಮಾತನಾಡಲು ಒತ್ತಿ",
    stop: "ನಿಲ್ಲಿಸಲು ಒತ್ತಿ",
  },
};

export function uiText(code) {
  return TEXT[code] || TEXT.ml;
}

export function languageName(code) {
  const found = LANGUAGES.find((l) => l.code === code);
  return found ? found.name : "Malayalam";
}
