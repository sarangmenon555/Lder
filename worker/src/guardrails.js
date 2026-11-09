const INJECTION = [
  [/ignore (all |any |the )?(previous|prior|above|earlier) (instructions|prompts|rules|messages)/i, 0.97],
  [/disregard (all |any |the )?(previous|prior|above|earlier|your) (instructions|prompts|rules)/i, 0.97],
  [/forget (all |everything |your )?(previous |prior )?(instructions|rules|prompt)/i, 0.93],
  [/(reveal|show|print|repeat|output|leak) (me )?(your |the )?(system|hidden|initial|original) (prompt|instructions|message)/i, 0.97],
  [/you are now (a |an |in )?(dan|developer mode|jailbroken|unrestricted)/i, 0.95],
  [/(act|behave|pretend) (as|like) (if )?(you (have|had) )?no (rules|restrictions|filters|guidelines)/i, 0.93],
  [/\bjailbreak\b/i, 0.85],
  [/developer mode/i, 0.8],
  [/<\/?\s*(system|assistant|tool|instructions?)\s*>/i, 0.9],
  [/\bnew (system )?instructions?\s*:/i, 0.85],
  [/(dump|export|list|show) (me )?(all|every) (the )?(elders|patients|people|users|records|check-?ins|data)/i, 0.85],
  [/(other|another|all) (elders?|patients?|people|users?|families|persons?)('s)? (data|records|check-?ins|transcripts|details)/i, 0.85],
  [/(api|secret|admin|access)[ _-]?(key|token|password)/i, 0.8],
  [/(മുമ്പത്തെ|മുൻപത്തെ|എല്ലാ) നിർദ്ദേശങ്ങൾ (അവഗണിക്കുക|മറക്കുക)/, 0.9],
  [/(पिछले|पहले के|सभी) (निर्देश|आदेश) (अनदेखा|नज़रअंदाज़|भूल)/, 0.9],
  [/(முந்தைய|எல்லா) (அறிவுறுத்தல்களை|கட்டளைகளை) (புறக்கணி|மற)/, 0.9],
  [/(మునుపటి|అన్ని) (సూచనలను|ఆదేశాలను) (విస్మరించు|మర)/, 0.9],
  [/(ಹಿಂದಿನ|ಎಲ್ಲಾ) (ಸೂಚನೆಗಳನ್ನು|ಆದೇಶಗಳನ್ನು) (ನಿರ್ಲಕ್ಷಿಸಿ|ಮರೆತುಬಿಡಿ)/, 0.9],
];

const PII = [
  ["email", /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/],
  ["aadhaar", /\b\d{4}[ -]?\d{4}[ -]?\d{4}\b/],
  ["pan", /\b[A-Z]{5}\d{4}[A-Z]\b/],
  ["card", /\b(?:\d[ -]?){13,19}\b/],
  ["phone", /(?<!\d)(?:\+?91[ -]?)?[6-9]\d{9}(?!\d)/],
];

const MAX_QUESTION_CHARS = 500;

export class Blocked extends Error {}

function normalizeText(text) {
  return String(text || "")
    .normalize("NFKC")
    .replace(/[​-‏⁠﻿]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function checkInjection(text) {
  const clean = normalizeText(text);
  let best = 0;
  for (const [pattern, score] of INJECTION) if (score > best && pattern.test(clean)) best = score;
  if (best === 0) return { valid: true, score: 0, explanation: null };
  return { valid: false, score: best, explanation: "prompt injection pattern matched" };
}

export function findPii(text) {
  return PII.filter(([, re]) => re.test(text || "")).map(([name]) => name);
}

export function redactPii(text) {
  const found = [];
  let result = text || "";
  for (const [name, re] of PII) {
    const global = new RegExp(re.source, "g");
    if (global.test(result)) {
      found.push(name);
      result = result.replace(new RegExp(re.source, "g"), `[${name} removed]`);
    }
  }
  return [result, found];
}

export function validate(profile, text) {
  if (profile === "prompt-injection" || profile === "injection") {
    const v = checkInjection(text);
    return { profile, result: v };
  }
  if (profile === "pii" || profile === "personally-identifiable-information") {
    const found = findPii(text);
    return {
      profile,
      result: { valid: found.length === 0, explanation: found.length ? "contains " + found.join(", ") : null, score: found.length ? 0.99 : 0 },
    };
  }
  return { profile, result: { valid: null, explanation: `unknown profile '${profile}'`, score: null } };
}

export function screenQuestion(question) {
  const clean = normalizeText(question).slice(0, MAX_QUESTION_CHARS);
  const verdict = checkInjection(clean);
  if (!verdict.valid) throw new Blocked(verdict.explanation || "blocked");
  return redactPii(clean);
}
