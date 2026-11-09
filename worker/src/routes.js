import * as assistant from "./assistant.js";
import * as checkinService from "./checkins.js";
import { alertFromRow, checkinFromRow, deleteElder, all, first, listElders, loadCheckin, loadElder, loadElderByToken, run, saveElder, updateCheckin } from "./db.js";
import * as guardrails from "./guardrails.js";
import { HttpError, json, readJson } from "./http.js";
import * as keywords from "./keywords.js";
import * as languages from "./languages.js";
import * as mcp from "./mcp.js";
import * as otari from "./otari.js";
import * as prompts from "./prompts.js";
import { alertOut, checkinOut, elderOut } from "./serialize.js";
import { checkPassword, createToken, safeEqual, verifyScopedToken, verifyToken } from "./security.js";
import * as stt from "./stt.js";
import { iso, utcnow } from "./time.js";
import { validateElder } from "./validate.js";
import * as whatsapp from "./whatsapp.js";

const attempts = new Map();
const WINDOW_MS = 300000;
const MAX_ATTEMPTS = 10;

async function requireAuth(app, request) {
  const header = request.headers.get("Authorization") || "";
  if (!header.startsWith("Bearer ")) throw new HttpError(401, "Not authenticated");
  if (!(await verifyToken(app.s, header.slice(7)))) throw new HttpError(401, "Invalid or expired session");
}

async function login(app, request) {
  const host = request.headers.get("CF-Connecting-IP") || "unknown";
  const now = Date.now();
  const recent = (attempts.get(host) || []).filter((t) => now - t < WINDOW_MS);
  attempts.set(host, recent);
  if (recent.length >= MAX_ATTEMPTS) throw new HttpError(429, "Too many attempts. Try again in a few minutes.");
  const body = await readJson(request);
  if (!checkPassword(app.s, String(body.password ?? ""))) {
    recent.push(now);
    throw new HttpError(401, "Incorrect password");
  }
  return json({ token: await createToken(app.s) });
}

async function needElder(app, id) {
  const elder = await loadElder(app, id);
  if (!elder) throw new HttpError(404, "Person not found");
  return elder;
}

async function listEldersRoute(app) {
  const elders = await listElders(app);
  const items = [];
  for (const elder of elders) {
    const latestRow = await first(app, "SELECT * FROM checkins WHERE elder_id=? ORDER BY scheduled_at DESC LIMIT 1", elder.id);
    const open = await first(
      app,
      "SELECT COUNT(*) AS n FROM alerts WHERE elder_id=? AND acknowledged_at IS NULL AND severity != 'info'",
      elder.id,
    );
    const summary = await checkinService.buildSummary(app, elder, 7);
    items.push({
      ...elderOut(elder),
      latest_checkin: latestRow ? checkinOut(await checkinFromRow(app, latestRow)) : null,
      open_alerts: (open && open.n) || 0,
      adherence_7d: summary.adherence_pct,
    });
  }
  return json(items);
}

async function alertsNames(app) {
  const rows = await all(app, "SELECT id, name FROM elders");
  return new Map(rows.map((r) => [r.id, r.name]));
}

async function contactName(app, id) {
  if (!id) return null;
  const row = await first(app, "SELECT name FROM contacts WHERE id=?", id);
  return row ? row.name : null;
}

async function listAlerts(app, url) {
  const ack = url.searchParams.get("acknowledged");
  const elderParam = url.searchParams.get("elder_id");
  let limit = parseInt(url.searchParams.get("limit") || "50", 10);
  if (!Number.isFinite(limit) || limit < 1 || limit > 200) throw new HttpError(422, "limit must be between 1 and 200");
  const where = [];
  const binds = [];
  if (ack === "true") where.push("acknowledged_at IS NOT NULL");
  else if (ack === "false") where.push("acknowledged_at IS NULL AND severity != 'info'");
  if (elderParam) {
    where.push("elder_id = ?");
    binds.push(Number(elderParam));
  }
  const rows = await all(
    app,
    `SELECT * FROM alerts ${where.length ? "WHERE " + where.join(" AND ") : ""} ORDER BY sent_at DESC LIMIT ?`,
    ...binds,
    limit,
  );
  const names = await alertsNames(app);
  const out = [];
  for (const row of rows) out.push(alertOut(await alertFromRow(app, row), names.get(row.elder_id), await contactName(app, row.contact_id)));
  return json(out);
}

async function acknowledgeRoute(app, id) {
  const row = await first(app, "SELECT * FROM alerts WHERE id=?", id);
  if (!row) throw new HttpError(404, "Alert not found");
  const alert = await alertFromRow(app, row);
  await checkinService.acknowledge(app, alert);
  const names = await alertsNames(app);
  return json(alertOut(alert, names.get(alert.elder_id), await contactName(app, alert.contact_id)));
}

async function triggerCheckin(app, request, elderId) {
  const elder = await needElder(app, elderId);
  const body = await readJson(request).catch(() => ({}));
  const mode = body.mode === undefined ? "normal" : body.mode;
  if (!["normal", "missed"].includes(mode)) throw new HttpError(422, "mode must be normal or missed");
  if (!elder.consent_at) throw new HttpError(400, "Record the person's consent before starting check-ins");
  let checkin;
  if (mode === "missed") checkin = await checkinService.forceMissed(app, elder);
  else {
    const now = utcnow();
    checkin = await checkinService.createCheckin(app, elder, now);
    await checkinService.sendPrompt(app, checkin, elder, now);
  }
  return json(checkinOut(checkin));
}

async function askRoute(app, request, elderId) {
  const elder = await needElder(app, elderId);
  const body = await readJson(request);
  const question = String(body.question ?? "").trim();
  if (question.length < 2 || question.length > 500) throw new HttpError(422, "Question must be 2 to 500 characters");
  try {
    return json(await assistant.ask(app, elder, question));
  } catch (err) {
    if (!(err instanceof assistant.AssistantError)) throw err;
    if (err.kind === "budget") throw new HttpError(402, "The AI usage limit for this person has been reached.");
    if (err.kind === "guardrail") throw new HttpError(400, "This question was blocked by a safety check.");
    if (err.kind === "config") throw new HttpError(503, "The AI gateway is not configured.");
    console.warn("Assistant failed:", err.message);
    throw new HttpError(502, `The assistant could not answer right now. (${String(err.message).slice(0, 240)})`);
  }
}

function promptOut(app, checkin, elder) {
  const key = prompts.promptKey(checkin.kind, checkin.attempt);
  return {
    checkin_id: checkin.id,
    text: prompts.textFor(key, elder.language),
    text_en: prompts.PROMPTS[key].text_en,
    audio_url: prompts.audioUrl(app.origin, key, elder.language),
  };
}

async function simElder(app, token) {
  const elder = await loadElderByToken(app, token);
  if (!elder) throw new HttpError(404, "This link is not valid");
  return elder;
}

async function simState(app, token) {
  const elder = await simElder(app, token);
  const open = await checkinService.findOpenCheckin(app, elder, utcnow());
  return json({
    elder_name: elder.name,
    language: languages.normalizeCode(elder.language),
    consent: elder.consent_at !== null,
    active: elder.active,
    awaiting: open && open.status === "awaiting_reply" ? promptOut(app, open, elder) : null,
  });
}

async function simStart(app, token) {
  const elder = await simElder(app, token);
  if (!elder.consent_at || !elder.active) throw new HttpError(403, "Check-ins are not enabled for this person");
  const now = utcnow();
  let open = await checkinService.findOpenCheckin(app, elder, now);
  if (!open || open.status !== "awaiting_reply") {
    open = await checkinService.createCheckin(app, elder, now, "simulator");
    await updateCheckin(app, open, { last_prompt_at: iso(now) });
  }
  return json(promptOut(app, open, elder));
}

async function simReply(app, request, token) {
  const elder = await simElder(app, token);
  if (!elder.consent_at || !elder.active) throw new HttpError(403, "Check-ins are not enabled for this person");
  let form;
  try {
    form = await request.formData();
  } catch {
    throw new HttpError(422, "Send the reply as form data");
  }
  let transcript = String(form.get("text") || "").trim();
  const audio = form.get("audio");
  if (audio && typeof audio === "object" && typeof audio.arrayBuffer === "function") {
    try {
      transcript = await stt.transcribe(app.s, await audio.arrayBuffer(), audio.type, elder.language, otari.elderUser(app.s, elder.id));
    } catch (err) {
      if (!(err instanceof stt.TranscriptionError)) throw err;
      throw new HttpError(502, `The voice message could not be transcribed (${err.message}). You can type the reply instead.`);
    }
  }
  if (!transcript) throw new HttpError(422, "No speech was detected. Please try again.");
  const now = utcnow();
  const open = await checkinService.findOpenCheckin(app, elder, now);
  const [, decision] = await checkinService.processReply(app, elder, open, transcript, "simulator");
  const key = decision.severity === "critical" ? "ack_help" : "ack_ok";
  return json({
    transcript,
    ack_text: prompts.textFor(key, elder.language),
    ack_text_en: prompts.PROMPTS[key].text_en,
    ack_audio_url: prompts.audioUrl(app.origin, key, elder.language),
    family_notified: decision.severity === "critical" || decision.severity === "warning",
  });
}

const STOP_WORDS = ["stop", "നിർത്തുക", "nirthuka", "unsubscribe"].map(keywords.normalize);

async function handleWhatsappMessage(app, message) {
  const now = utcnow();
  const s = app.s;
  const elders = await all(app, "SELECT * FROM elders");
  const elderRow = elders.find((e) => whatsapp.samePhone(e.phone, message.sender));
  const contacts = await all(app, "SELECT * FROM contacts");
  const contact = contacts.find((c) => whatsapp.samePhone(c.phone, message.sender));
  const safeSend = async (to, body) => {
    try {
      await whatsapp.sendText(s, to, body);
    } catch (err) {
      console.warn("Reply failed", String(err.message || err));
    }
  };
  if (contact) {
    await run(app, "UPDATE contacts SET last_inbound_at=? WHERE id=?", iso(now), contact.id);
    const pending = await first(app, "SELECT * FROM alerts WHERE contact_id=? AND acknowledged_at IS NULL ORDER BY sent_at DESC LIMIT 1", contact.id);
    if (pending && message.kind === "text") {
      await checkinService.acknowledge(app, await alertFromRow(app, pending));
      await safeSend(message.sender, "Thank you. The alert has been marked as acknowledged.");
    }
    if (!elderRow) return;
  }
  if (!elderRow) return;
  await run(app, "UPDATE elders SET last_inbound_at=? WHERE id=?", iso(now), elderRow.id);
  const elder = await loadElder(app, elderRow.id);
  if (message.kind === "text" && STOP_WORDS.includes(keywords.normalize(message.text))) {
    await run(app, "UPDATE elders SET active=0 WHERE id=?", elder.id);
    await safeSend(message.sender, "You will no longer receive check-ins. Your family can turn them back on.");
    return;
  }
  if (!elder.consent_at || !elder.active) return;
  elder.last_inbound_at = iso(now);
  let transcript = "";
  if (message.kind === "audio" && message.media_id) {
    try {
      const [audio, mime] = await whatsapp.downloadMedia(s, message.media_id);
      transcript = await stt.transcribe(s, audio, message.mime || mime, elder.language, otari.elderUser(s, elder.id));
    } catch (err) {
      console.warn("Could not transcribe WhatsApp audio", String(err.message || err));
      await safeSend(message.sender, prompts.textFor("unclear", elder.language));
      return;
    }
  } else if (message.kind === "text") {
    transcript = message.text.trim();
  } else return;
  if (!transcript) {
    await safeSend(message.sender, prompts.textFor("unclear", elder.language));
    return;
  }
  const open = await checkinService.findOpenCheckin(app, elder, now);
  const [, decision] = await checkinService.processReply(app, elder, open, transcript, "whatsapp");
  await checkinService.sendAck(app, elder, decision.severity === "critical" ? "ack_help" : "ack_ok", utcnow());
}

async function handleWhatsappMessages(app, messages) {
  for (const message of messages) {
    try {
      await handleWhatsappMessage(app, message);
    } catch (err) {
      console.error("Failed to handle inbound WhatsApp message", String(err.stack || err));
    }
  }
}

async function mcpRoute(app, request) {
  const header = request.headers.get("Authorization") || "";
  if (!header.startsWith("Bearer ")) throw new HttpError(401, "Not authenticated");
  const elderId = await verifyScopedToken(app.s, header.slice(7));
  if (elderId === null) throw new HttpError(401, "Invalid or expired token");
  const elder = await loadElder(app, elderId);
  if (!elder) throw new HttpError(404, "Person not found");
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "Parse error" } }, 400);
  }
  if (Array.isArray(body)) {
    const replies = [];
    for (const item of body) {
      const r = await mcp.handleMessage(app, elder, item);
      if (r !== null) replies.push(r);
    }
    return replies.length ? json(replies) : new Response(null, { status: 202 });
  }
  const reply = await mcp.handleMessage(app, elder, body);
  return reply === null ? new Response(null, { status: 202 }) : json(reply);
}

async function guardrailRoute(app, request) {
  const secret = app.s.guardrailSecret;
  if (!secret) throw new HttpError(503, "Guardrail endpoint is not configured");
  const supplied = (request.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "").trim();
  if (!safeEqual(supplied, secret)) throw new HttpError(401, "Invalid credential");
  const body = await readJson(request);
  return json(guardrails.validate(String(body.profile || "prompt-injection"), String(body.input_text || "")));
}

export async function route(app, request, ctx) {
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/+$/, "") || "/";
  const method = request.method;
  let m;

  if (path === "/health") return json({ status: "ok" });

  if (path === "/api/auth/login" && method === "POST") return login(app, request);

  if (path === "/api/internal/tick" && method === "GET") {
    const secret = app.s.cronSecret;
    if (!secret || !safeEqual(url.searchParams.get("key") || "", secret)) throw new HttpError(403, "Forbidden");
    return json(await checkinService.runTick(app));
  }

  if (path === "/api/mcp") {
    if (method === "POST") return mcpRoute(app, request);
    if (method === "GET") return new Response(null, { status: 405, headers: { Allow: "POST" } });
  }

  if ((path === "/api/guardrail" || path === "/api/guardrail/validate") && method === "POST") return guardrailRoute(app, request);

  if (path === "/api/webhook/whatsapp") {
    if (method === "GET") {
      const expected = app.s.whatsappVerifyToken;
      if (url.searchParams.get("hub.mode") === "subscribe" && expected && url.searchParams.get("hub.verify_token") === expected) {
        return new Response(url.searchParams.get("hub.challenge") || "", { headers: { "Content-Type": "text/plain" } });
      }
      throw new HttpError(403, "Verification failed");
    }
    if (method === "POST") {
      const raw = await request.arrayBuffer();
      if (!(await whatsapp.verifySignature(app.s, raw, request.headers.get("X-Hub-Signature-256")))) throw new HttpError(403, "Invalid signature");
      let payload;
      try {
        payload = JSON.parse(new TextDecoder().decode(raw));
      } catch {
        return json({ status: "ignored" });
      }
      const messages = whatsapp.parseInbound(payload);
      if (messages.length) ctx.waitUntil(handleWhatsappMessages(app, messages));
      return json({ status: "ok" });
    }
  }

  if ((m = path.match(/^\/api\/simulator\/([^/]+)(?:\/(start|reply|opt-out))?$/))) {
    const [, token, action] = m;
    if (!action && method === "GET") return simState(app, token);
    if (action === "start" && method === "POST") return simStart(app, token);
    if (action === "reply" && method === "POST") return simReply(app, request, token);
    if (action === "opt-out" && method === "POST") {
      const elder = await simElder(app, token);
      await run(app, "UPDATE elders SET active=0 WHERE id=?", elder.id);
      return json({ ok: true });
    }
  }

  if (path.startsWith("/api/")) {
    await requireAuth(app, request);

    if (path === "/api/elders") {
      if (method === "GET") return listEldersRoute(app);
      if (method === "POST") return json(elderOut(await saveElder(app, null, validateElder(await readJson(request)))), 201);
    }
    if ((m = path.match(/^\/api\/elders\/(\d+)$/))) {
      const id = Number(m[1]);
      if (method === "GET") return json(elderOut(await needElder(app, id)));
      if (method === "PUT") {
        await needElder(app, id);
        return json(elderOut(await saveElder(app, id, validateElder(await readJson(request)))));
      }
      if (method === "DELETE") {
        await needElder(app, id);
        await deleteElder(app, id);
        return json(null, 204);
      }
    }
    if ((m = path.match(/^\/api\/elders\/(\d+)\/(checkins|summary|trigger-checkin|ask)$/))) {
      const id = Number(m[1]);
      const action = m[2];
      if (action === "checkins" && method === "GET") {
        await needElder(app, id);
        const limit = parseInt(url.searchParams.get("limit") || "30", 10);
        if (!Number.isFinite(limit) || limit < 1 || limit > 200) throw new HttpError(422, "limit must be between 1 and 200");
        const rows = await all(app, "SELECT * FROM checkins WHERE elder_id=? ORDER BY scheduled_at DESC LIMIT ?", id, limit);
        const out = [];
        for (const row of rows) out.push(checkinOut(await checkinFromRow(app, row)));
        return json(out);
      }
      if (action === "summary" && method === "GET") {
        const elder = await needElder(app, id);
        const days = parseInt(url.searchParams.get("days") || "7", 10);
        if (!Number.isFinite(days) || days < 1 || days > 30) throw new HttpError(422, "days must be between 1 and 30");
        return json(await checkinService.buildSummary(app, elder, days));
      }
      if (action === "trigger-checkin" && method === "POST") return triggerCheckin(app, request, id);
      if (action === "ask" && method === "POST") return askRoute(app, request, id);
    }
    if (path === "/api/alerts" && method === "GET") return listAlerts(app, url);
    if ((m = path.match(/^\/api\/alerts\/(\d+)\/acknowledge$/)) && method === "POST") return acknowledgeRoute(app, Number(m[1]));
  }

  throw new HttpError(404, "Not found");
}

export { loadCheckin };