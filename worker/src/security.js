const enc = new TextEncoder();
let hmacCache = { secret: null, key: null };

function b64url(bytes) {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromB64url(text) {
  const padded = text.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (text.length % 4)) % 4);
  return atob(padded);
}

async function hmacKey(secret) {
  if (hmacCache.secret === secret) return hmacCache.key;
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
  hmacCache = { secret, key };
  return key;
}

async function sign(secret, payload) {
  const key = await hmacKey(secret);
  return b64url(new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(payload))));
}

export function safeEqual(a, b) {
  const x = enc.encode(String(a));
  const y = enc.encode(String(b));
  let diff = x.length ^ y.length;
  const n = Math.max(x.length, y.length);
  for (let i = 0; i < n; i++) diff |= (x[i] || 0) ^ (y[i] || 0);
  return diff === 0;
}

function encodePayload(body) {
  return b64url(enc.encode(JSON.stringify(body)));
}

async function open(secret, token) {
  const parts = String(token || "").split(".");
  if (parts.length < 2) return null;
  const payload = parts[0];
  const signature = parts.slice(1).join(".");
  if (!safeEqual(signature, await sign(secret, payload))) return null;
  try {
    return JSON.parse(new TextDecoder().decode(Uint8Array.from(fromB64url(payload), (c) => c.charCodeAt(0))));
  } catch {
    return null;
  }
}

export async function createToken(s) {
  const exp = Math.floor(Date.now() / 1000) + s.tokenTtlHours * 3600;
  const payload = encodePayload({ exp });
  return `${payload}.${await sign(s.secretKey, payload)}`;
}

export async function verifyToken(s, token) {
  const data = await open(s.secretKey, token);
  if (!data || "scope" in data) return false;
  return Number(data.exp || 0) > Date.now() / 1000;
}

export async function createScopedToken(s, elderId, ttlSeconds) {
  const payload = encodePayload({ scope: "mcp", elder: Number(elderId), exp: Math.floor(Date.now() / 1000) + ttlSeconds });
  return `${payload}.${await sign(s.secretKey, payload)}`;
}

export async function verifyScopedToken(s, token) {
  const data = await open(s.secretKey, token);
  if (!data || data.scope !== "mcp" || Number(data.exp || 0) <= Date.now() / 1000) return null;
  return Number(data.elder);
}

export function checkPassword(s, candidate) {
  return safeEqual(candidate || "", s.adminPassword);
}

export async function hmacHex(secret, bodyBytes) {
  const key = await hmacKey(secret);
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", key, bodyBytes));
  return Array.from(sig, (b) => b.toString(16).padStart(2, "0")).join("");
}

export async function sha256Hex(text) {
  const d = new Uint8Array(await crypto.subtle.digest("SHA-256", enc.encode(text)));
  return Array.from(d, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function randomToken(bytes = 24) {
  return b64url(crypto.getRandomValues(new Uint8Array(bytes)));
}
