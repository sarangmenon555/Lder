const PREFIX = "enc2:";
let cache = { secret: null, key: null };

function toB64(bytes) {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s);
}

function fromB64(text) {
  const s = atob(text);
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
  return out;
}

async function getKey(secret) {
  if (!secret) return null;
  if (cache.secret === secret) return cache.key;
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(secret));
  const key = await crypto.subtle.importKey("raw", digest, "AES-GCM", false, ["encrypt", "decrypt"]);
  cache = { secret, key };
  return key;
}

export async function encrypt(secret, value) {
  if (value === null || value === undefined) return null;
  const key = await getKey(secret);
  if (!key) return value;
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const data = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, new TextEncoder().encode(value));
  const joined = new Uint8Array(12 + data.byteLength);
  joined.set(iv, 0);
  joined.set(new Uint8Array(data), 12);
  return PREFIX + toB64(joined);
}

export async function decrypt(secret, value) {
  if (value === null || value === undefined) return null;
  if (!String(value).startsWith(PREFIX)) return value;
  const key = await getKey(secret);
  if (!key) return "[encrypted]";
  try {
    const joined = fromB64(value.slice(PREFIX.length));
    const data = await crypto.subtle.decrypt({ name: "AES-GCM", iv: joined.slice(0, 12) }, key, joined.slice(12));
    return new TextDecoder().decode(data);
  } catch {
    return "[unreadable]";
  }
}
