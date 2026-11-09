import { modelChain } from "./config.js";

const BUDGET_CODES = new Set(["budget_exceeded", "user_blocked", "end_user_limit_reached", "insufficient_funds"]);
const RETRYABLE = new Set([408, 409, 429, 500, 502, 503, 504]);

export class OtariError extends Error {
  constructor(message, code = "", status = 0, kind = "error") {
    super(message);
    this.code = code;
    this.status = status;
    this.kind = kind;
  }
}

export function enabled(s) {
  return Boolean(s.otariApiKey);
}

export function elderUser(s, elderId) {
  if (elderId === null || elderId === undefined) return null;
  return `${s.otariUserPrefix}${elderId}`;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function errorParts(response) {
  let code = response.headers.get("Otari-Error-Code") || "";
  let detail = "";
  let text = "";
  try {
    text = await response.text();
  } catch {
    text = "";
  }
  let body = null;
  try {
    body = JSON.parse(text);
  } catch {
    body = null;
  }
  if (body && typeof body === "object") {
    code = code || String(body.code || "");
    let raw = body.detail;
    if ((raw === undefined || raw === null) && body.error && typeof body.error === "object") {
      raw = body.error.message;
      code = code || String(body.error.code || "");
    }
    detail = typeof raw === "string" ? raw : raw ? JSON.stringify(raw) : "";
  }
  if (!detail) detail = text.slice(0, 300);
  return [code, detail];
}

async function classifyError(response) {
  const [code, detail] = await errorParts(response);
  const lowered = `${code} ${detail}`.toLowerCase();
  let kind = "error";
  if (BUDGET_CODES.has(code) || lowered.includes("budget")) kind = "budget";
  else if (lowered.includes("guardrail") || lowered.includes("prompt_injection") || lowered.includes("prompt injection")) kind = "guardrail";
  else if (RETRYABLE.has(response.status)) kind = "retryable";
  return new OtariError(`Otari error ${response.status} ${code}: ${detail}`.trim(), code, response.status, kind);
}

function truthyHeader(value) {
  if (value === null || value === undefined) return false;
  return !["", "0", "false", "none", "no"].includes(String(value).trim().toLowerCase());
}

function metaFrom(response, body, requested, tried) {
  const h = response.headers;
  let attempts = parseInt(h.get("Otari-Attempt-Count") || "1", 10);
  if (!Number.isFinite(attempts)) attempts = 1;
  let cost = null;
  const usage = body && typeof body === "object" ? body.usage : null;
  if (usage && usage.cost_usd !== undefined && usage.cost_usd !== null) {
    const n = Number(usage.cost_usd);
    cost = Number.isFinite(n) ? n : null;
  }
  const model = h.get("Otari-Model") || (body && body.model) || requested;
  return {
    requested_model: requested,
    model: String(model),
    provider: h.get("Otari-Provider") || "",
    request_id: h.get("Otari-Request-ID") || "",
    attempts,
    fallback: truthyHeader(h.get("Otari-Fallback")) || attempts > 1 || tried.length > 1,
    cost_usd: cost,
    models_tried: [...tried],
  };
}

export async function send(url, headers, payload, timeoutSeconds) {
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(timeoutSeconds * 1000),
  });
}

export const hooks = { send, sleep };

export async function chat(s, { models, messages, user, tags, maxTokens = 800, temperature = 0, jsonMode = false, extra, idempotencyKey }) {
  if (!s.otariApiKey) throw new OtariError("OTARI_API_KEY is not configured", "", 0, "config");
  if (!models || !models.length) throw new OtariError("No model is configured", "", 0, "config");
  const url = s.otariBaseUrl.replace(/\/$/, "") + "/chat/completions";
  const headers = { Authorization: `Bearer ${s.otariApiKey}` };
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
  const tried = [];
  let lastError = null;
  let json = jsonMode;
  for (const model of models) {
    tried.push(model);
    const payload = { model, messages, temperature, max_tokens: maxTokens };
    if (json) payload.response_format = { type: "json_object" };
    if (user) payload.user = user;
    if (tags) {
      payload.metadata = Object.fromEntries(
        Object.entries(tags)
          .slice(0, 16)
          .map(([k, v]) => [String(k).slice(0, 64), String(v).slice(0, 512)]),
      );
    }
    if (extra) Object.assign(payload, extra);
    for (let attempt = 0; attempt < 2; attempt++) {
      let response;
      try {
        response = await hooks.send(url, headers, payload, s.otariTimeoutSeconds);
      } catch (err) {
        lastError = new OtariError(`network error: ${err.message || err}`, "", 0, "retryable");
        await hooks.sleep(1000 * (1 + attempt));
        continue;
      }
      if (response.status < 400) {
        let body;
        let content;
        try {
          body = await response.json();
          content = body.choices[0].message.content || "";
        } catch (err) {
          lastError = new OtariError(`unexpected response shape: ${err.message}`, "", 0, "error");
          break;
        }
        return [content, metaFrom(response, body, models[0], tried)];
      }
      const error = await classifyError(response);
      if (error.kind === "budget" || error.kind === "guardrail") throw error;
      if (json && response.status === 400 && error.message.toLowerCase().includes("response_format")) {
        json = false;
        delete payload.response_format;
        lastError = error;
        continue;
      }
      lastError = error;
      if (error.kind === "retryable") {
        const wait = parseFloat(response.headers.get("retry-after") || "");
        const delay = Number.isFinite(wait) ? Math.min(wait, 6) : 1 + attempt;
        await hooks.sleep(delay * 1000);
        continue;
      }
      break;
    }
  }
  throw lastError || new OtariError("Otari request failed");
}

export function extractJson(content) {
  const start = content.indexOf("{");
  const end = content.lastIndexOf("}");
  if (start < 0 || end < start) throw new OtariError("Model returned no JSON object", "", 0, "parse");
  try {
    return JSON.parse(content.slice(start, end + 1));
  } catch (err) {
    throw new OtariError(`Model returned invalid JSON: ${err.message}`, "", 0, "parse");
  }
}

export { modelChain };
