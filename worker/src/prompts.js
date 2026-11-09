import PROMPTS from "./data/prompts.json" with { type: "json" };
import AUDIO from "./data/audio_manifest.json" with { type: "json" };
import { DEFAULT_LANGUAGE, normalizeCode } from "./languages.js";

export { PROMPTS };

export function promptKey(kind, attempt) {
  if (attempt > 1) return "retry";
  return kind === "evening" ? "evening" : "morning";
}

export function textFor(key, language) {
  const p = PROMPTS[key];
  return p.texts[normalizeCode(language)] || p.texts[DEFAULT_LANGUAGE];
}

export function audioFilename(key, language) {
  const code = normalizeCode(language);
  const base = PROMPTS[key].file;
  return code === DEFAULT_LANGUAGE ? `${base}.mp3` : `${base}.${code}.mp3`;
}

export function audioPath(key, language) {
  const name = audioFilename(key, language);
  return AUDIO.includes(name) ? `/static/prompts/${name}` : null;
}

export function audioUrl(origin, key, language) {
  const path = audioPath(key, language);
  return path ? origin.replace(/\/$/, "") + path : null;
}
