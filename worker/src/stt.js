import * as languages from "./languages.js";

export class TranscriptionError extends Error {}

const MAX_BYTES = 20 * 1024 * 1024;
const EXT = {
  "audio/ogg": "ogg",
  "audio/opus": "ogg",
  "audio/webm": "webm",
  "video/webm": "webm",
  "audio/mp4": "m4a",
  "audio/m4a": "m4a",
  "audio/x-m4a": "m4a",
  "audio/mpeg": "mp3",
  "audio/mp3": "mp3",
  "audio/wav": "wav",
  "audio/x-wav": "wav",
  "audio/wave": "wav",
  "audio/flac": "flac",
  "audio/aac": "m4a",
};

export function extensionFor(contentType) {
  const base = String(contentType || "").split(";")[0].trim().toLowerCase();
  return [EXT[base] || "webm", base || "audio/webm"];
}

export async function transcribe(s, audio, contentType, language = null, user = null) {
  const url = (s.sttBaseUrl || s.otariBaseUrl).replace(/\/$/, "");
  const key = s.sttApiKey || s.otariApiKey;
  if (!key) throw new TranscriptionError("No speech-to-text key is configured");
  if (!audio || !audio.byteLength) throw new TranscriptionError("Empty audio");
  if (audio.byteLength > MAX_BYTES) throw new TranscriptionError("Audio is larger than 20 MB");
  const [ext, mime] = extensionFor(contentType);
  const lang = languages.normalizeCode(language || s.sttLanguage);
  const form = new FormData();
  form.append("model", s.sttModel);
  form.append("response_format", "json");
  form.append("temperature", "0");
  form.append("language", lang);
  form.append("prompt", lang === languages.normalizeCode(s.sttLanguage) && s.sttPrompt ? s.sttPrompt : languages.get(lang).stt_prompt);
  if (user) form.append("user", user);
  form.append("file", new Blob([audio], { type: mime }), `reply.${ext}`);
  let response;
  try {
    response = await fetch(url + "/audio/transcriptions", {
      method: "POST",
      headers: { Authorization: `Bearer ${key}` },
      body: form,
      signal: AbortSignal.timeout(60000),
    });
  } catch (err) {
    throw new TranscriptionError(`Network error: ${err.message || err}`);
  }
  if (response.status >= 400) {
    const text = await response.text().catch(() => "");
    throw new TranscriptionError(`Transcription error ${response.status}: ${text.slice(0, 300)}`);
  }
  try {
    return String((await response.json()).text || "").trim();
  } catch {
    throw new TranscriptionError("Unreadable transcription response");
  }
}
