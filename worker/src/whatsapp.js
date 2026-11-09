import { hmacHex, safeEqual } from "./security.js";

export class WhatsAppError extends Error {}

const mediaCache = new Map();

export function enabled(s) {
  return Boolean(s.whatsappToken && s.whatsappPhoneNumberId);
}

export function normalizePhone(phone) {
  return String(phone || "").replace(/\D/g, "");
}

export function samePhone(a, b) {
  const x = normalizePhone(a);
  const y = normalizePhone(b);
  if (!x || !y) return false;
  return x.slice(-10) === y.slice(-10);
}

export function windowOpen(lastInboundAt, now) {
  return Boolean(lastInboundAt) && now.getTime() - new Date(lastInboundAt).getTime() < 24 * 3600 * 1000;
}

const base = (s) => `https://graph.facebook.com/${s.whatsappApiVersion}`;
const headers = (s) => ({ Authorization: `Bearer ${s.whatsappToken}` });

async function postMessage(s, payload) {
  if (!enabled(s)) throw new WhatsAppError("WhatsApp is not configured");
  let response;
  try {
    response = await fetch(`${base(s)}/${s.whatsappPhoneNumberId}/messages`, {
      method: "POST",
      headers: { ...headers(s), "Content-Type": "application/json" },
      body: JSON.stringify({ messaging_product: "whatsapp", ...payload }),
      signal: AbortSignal.timeout(20000),
    });
  } catch (err) {
    throw new WhatsAppError(`Network error: ${err.message || err}`);
  }
  if (response.status >= 400) {
    const text = await response.text().catch(() => "");
    throw new WhatsAppError(`WhatsApp error ${response.status}: ${text.slice(0, 300)}`);
  }
}

export function sendText(s, to, body) {
  return postMessage(s, { to: normalizePhone(to), type: "text", text: { body: body.slice(0, 3900) } });
}

export function sendTemplate(s, to) {
  return postMessage(s, {
    to: normalizePhone(to),
    type: "template",
    template: { name: s.whatsappTemplateName, language: { code: s.whatsappTemplateLanguage } },
  });
}

async function uploadAudio(app, path) {
  if (mediaCache.has(path)) return mediaCache.get(path);
  const asset = await app.env.ASSETS.fetch(new Request(new URL(path, app.origin)));
  if (!asset.ok) throw new WhatsAppError("Prompt audio file is not available");
  const form = new FormData();
  form.append("messaging_product", "whatsapp");
  form.append("type", "audio/mpeg");
  form.append("file", new Blob([await asset.arrayBuffer()], { type: "audio/mpeg" }), path.split("/").pop());
  let response;
  try {
    response = await fetch(`${base(app.s)}/${app.s.whatsappPhoneNumberId}/media`, {
      method: "POST",
      headers: headers(app.s),
      body: form,
      signal: AbortSignal.timeout(40000),
    });
  } catch (err) {
    throw new WhatsAppError(`Network error: ${err.message || err}`);
  }
  if (response.status >= 400) throw new WhatsAppError(`WhatsApp media error ${response.status}`);
  const data = await response.json();
  if (!data.id) throw new WhatsAppError("WhatsApp did not return a media id");
  mediaCache.set(path, data.id);
  return data.id;
}

export async function sendToElder(app, elder, body, audioPath, now) {
  const to = normalizePhone(elder.phone);
  if (!to) throw new WhatsAppError("Elder has no phone number");
  if (windowOpen(elder.last_inbound_at, now)) {
    await sendText(app.s, to, body);
    if (audioPath) {
      const id = await uploadAudio(app, audioPath);
      await postMessage(app.s, { to, type: "audio", audio: { id } });
    }
    return "message";
  }
  await sendTemplate(app.s, to);
  return "template";
}

export async function sendToContact(app, contact, body, now) {
  const to = normalizePhone(contact.phone);
  if (!to) throw new WhatsAppError("Contact has no phone number");
  if (windowOpen(contact.last_inbound_at, now)) {
    await sendText(app.s, to, body);
    return;
  }
  await sendTemplate(app.s, to);
  throw new WhatsAppError("Recipient window closed; template sent instead of the alert text");
}

export async function downloadMedia(s, mediaId) {
  let meta;
  let file;
  try {
    meta = await fetch(`${base(s)}/${mediaId}`, { headers: headers(s), signal: AbortSignal.timeout(20000) });
    if (meta.status >= 400) throw new WhatsAppError(`Media lookup failed ${meta.status}`);
    const info = await meta.json();
    file = await fetch(info.url, { headers: headers(s), signal: AbortSignal.timeout(60000) });
    if (file.status >= 400) throw new WhatsAppError(`Media download failed ${file.status}`);
    return [await file.arrayBuffer(), info.mime_type || "audio/ogg"];
  } catch (err) {
    if (err instanceof WhatsAppError) throw err;
    throw new WhatsAppError(`Network error: ${err.message || err}`);
  }
}

export async function verifySignature(s, rawBytes, header) {
  if (!s.whatsappAppSecret) return true;
  if (!header || !header.startsWith("sha256=")) return false;
  return safeEqual(await hmacHex(s.whatsappAppSecret, rawBytes), header.slice(7));
}

export function parseInbound(payload) {
  const messages = [];
  for (const entry of payload.entry || []) {
    for (const change of entry.changes || []) {
      const value = change.value || {};
      for (const msg of value.messages || []) {
        const sender = normalizePhone(msg.from);
        const kind = msg.type || "";
        if (kind === "audio") {
          const audio = msg.audio || {};
          messages.push({ sender, kind: "audio", text: "", media_id: audio.id || "", mime: audio.mime_type || "" });
        } else if (kind === "text") {
          messages.push({ sender, kind: "text", text: (msg.text || {}).body || "", media_id: "", mime: "" });
        } else {
          messages.push({ sender, kind: kind || "other", text: "", media_id: "", mime: "" });
        }
      }
    }
  }
  return messages;
}
