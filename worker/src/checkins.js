import * as classifier from "./classifier.js";
import { all, checkinFromRow, elderFromRow, first, hydrate, insertAlert, insertCheckin, loadCheckin, loadElder, run, updateCheckin } from "./db.js";
import { decrypt } from "./crypto.js";
import * as escalation from "./escalation.js";
import { analyze } from "./keywords.js";
import * as narrator from "./narrator.js";
import * as notifier from "./notifier.js";
import * as prompts from "./prompts.js";
import { sha256Hex } from "./security.js";
import { addDaysToKey, formatLocal, isoWeek, iso, localDateKey, localParts, parseDate, pyWeekday, utcnow } from "./time.js";
import * as whatsapp from "./whatsapp.js";

export function kindFor(elder, when) {
  return localParts(when, elder.timezone).hour < 15 ? "morning" : "evening";
}

export function dueMedicineNames(elder, when) {
  const p = localParts(when, elder.timezone);
  const minutes = p.hour * 60 + p.minute;
  const names = [];
  for (const medicine of elder.medicines) {
    const [h, m] = medicine.time_of_day.split(":").map(Number);
    const diff = Math.abs(h * 60 + m - minutes);
    if (Math.min(diff, 1440 - diff) <= 90) names.push(medicine.name);
  }
  return names;
}

export function defaultChannel(app, elder) {
  return whatsapp.enabled(app.s) && elder.phone ? "whatsapp" : "simulator";
}

export function createCheckin(app, elder, scheduledAt, channel = null, kind = null) {
  return insertCheckin(app, {
    elderId: elder.id,
    scheduledAt,
    kind: kind || kindFor(elder, scheduledAt),
    channel: channel || defaultChannel(app, elder),
  });
}

export async function sendPrompt(app, checkin, elder, now = utcnow()) {
  const key = prompts.promptKey(checkin.kind, checkin.attempt);
  let body = prompts.textFor(key, elder.language);
  const names = dueMedicineNames(elder, parseDate(checkin.scheduled_at));
  if (names.length) body += "\n\n" + names.join(", ");
  if (checkin.channel === "whatsapp" && whatsapp.enabled(app.s) && elder.phone) {
    try {
      await whatsapp.sendToElder(app, elder, body, prompts.audioPath(key, elder.language), now);
    } catch (err) {
      console.warn("Could not send prompt", elder.id, String(err.message || err));
    }
  }
  await updateCheckin(app, checkin, { last_prompt_at: iso(now) });
}

export async function sendAck(app, elder, key, now) {
  if (!(whatsapp.enabled(app.s) && elder.phone)) return;
  try {
    await whatsapp.sendToElder(app, elder, prompts.textFor(key, elder.language), prompts.audioPath(key, elder.language), now);
  } catch (err) {
    console.warn("Could not send acknowledgement", elder.id, String(err.message || err));
  }
}

export async function findOpenCheckin(app, elder, now) {
  const since = iso(new Date(now.getTime() - 6 * 3600 * 1000));
  const row = await first(
    app,
    "SELECT * FROM checkins WHERE elder_id=? AND status IN ('awaiting_reply','missed') AND created_at >= ? ORDER BY created_at DESC LIMIT 1",
    elder.id,
    since,
  );
  return row ? checkinFromRow(app, row) : null;
}

export async function makeAlert(app, elder, checkin, contact, severity, reason) {
  const now = utcnow();
  const dispatch = await notifier.dispatchAlert(app, elder, contact, checkin, reason, now);
  return insertAlert(app, {
    elder_id: elder.id,
    checkin_id: checkin ? checkin.id : null,
    contact_id: contact ? contact.id : null,
    severity,
    reason,
    message: dispatch.message,
    channel: dispatch.channel,
    delivered: dispatch.delivered,
    error: dispatch.error,
    sent_at: iso(now),
  });
}

function reasonFor(decision) {
  if (decision.severity === "critical") return "distress";
  if (["unwell", "confused", "unclear"].includes(decision.status)) return "needs_follow_up";
  return "medicine_missed";
}

export async function notifyForDecision(app, elder, checkin, decision, wasMissed) {
  const contacts = elder.contacts;
  if (decision.severity === "critical") {
    const targets = contacts.length ? contacts : [null];
    for (const contact of targets) await makeAlert(app, elder, checkin, contact, "critical", "distress");
  } else if (decision.severity === "warning") {
    await makeAlert(app, elder, checkin, contacts[0] || null, "warning", reasonFor(decision));
  } else if (wasMissed) {
    const rows = await all(app, "SELECT DISTINCT contact_id FROM alerts WHERE checkin_id=? AND contact_id IS NOT NULL", checkin.id);
    const ids = new Set(rows.map((r) => r.contact_id));
    for (const contact of contacts) if (ids.has(contact.id)) await makeAlert(app, elder, checkin, contact, "info", "late_response");
  }
}

export async function detectPattern(app, elder, checkin, now) {
  const recent = await all(
    app,
    "SELECT mood, classification FROM checkins WHERE elder_id=? AND status='completed' AND classification IS NOT NULL ORDER BY responded_at DESC LIMIT 3",
    elder.id,
  );
  if (recent.length < 3) return;
  if (!recent.every((c) => c.mood === "low" || c.classification === "unwell" || c.classification === "needs_help")) return;
  const since = iso(new Date(now.getTime() - 24 * 3600 * 1000));
  const existing = await first(app, "SELECT id FROM alerts WHERE elder_id=? AND reason='pattern' AND sent_at >= ?", elder.id, since);
  if (existing) return;
  await makeAlert(app, elder, checkin, elder.contacts[0] || null, "warning", "pattern");
}

export async function processReply(app, elder, checkin, transcript, channel) {
  const now = utcnow();
  const wasMissed = checkin !== null && checkin.status === "missed";
  if (checkin === null) checkin = await createCheckin(app, elder, now, channel, "inbound");
  if (checkin === null) checkin = await findOpenCheckin(app, elder, now);
  const kw = analyze(transcript);
  let llm = null;
  let error = null;
  if (transcript.trim()) {
    const digest = (await sha256Hex(transcript)).slice(0, 10);
    try {
      llm = await classifier.classifyWithLlm(app.s, {
        transcript,
        dueMedicines: dueMedicineNames(elder, parseDate(checkin.scheduled_at)),
        kind: checkin.kind,
        elderId: elder.id,
        idempotencyKey: `lder-classify-${checkin.id}-${digest}`,
        language: elder.language,
      });
    } catch (err) {
      if (!(err instanceof classifier.ClassifierError)) throw err;
      error = err.kind === "budget" || err.kind === "guardrail" ? `${err.kind}: ${err.message}` : err.message;
      console.warn("Classifier unavailable:", err.message);
    }
  }
  const decision = classifier.buildDecision(transcript, llm, kw, app.s.confidenceThreshold, error);
  const gateway = decision.gateway || {};
  const has = Object.keys(gateway).length > 0;
  await updateCheckin(app, checkin, {
    transcript,
    classification: decision.status,
    medicine_taken: decision.medicine_taken,
    distress: decision.distress,
    mood: decision.mood,
    confidence: decision.confidence,
    summary: decision.summary,
    keyword_hits: decision.keyword_hits,
    classifier_error: decision.error,
    model_used: gateway.model || null,
    gateway_request_id: gateway.request_id || null,
    gateway_fallback: has ? Boolean(gateway.fallback) : null,
    gateway_cost_usd: gateway.cost_usd ?? null,
    status: "completed",
    responded_at: iso(now),
    escalation_active: false,
  });
  await notifyForDecision(app, elder, checkin, decision, wasMissed);
  await detectPattern(app, elder, checkin, now);
  return [checkin, decision];
}

export async function escalateNext(app, checkin, elder, now) {
  const contacts = elder.contacts;
  if (!contacts.length) {
    await makeAlert(app, elder, checkin, null, "warning", "missed_checkin");
    await updateCheckin(app, checkin, { escalation_active: false });
    return;
  }
  const contact = escalation.pickContact(contacts, checkin.escalation_level);
  if (contact === null) {
    await updateCheckin(app, checkin, { escalation_active: false });
    return;
  }
  await makeAlert(app, elder, checkin, contact, "warning", "missed_checkin");
  const level = checkin.escalation_level + 1;
  await updateCheckin(app, checkin, {
    escalation_level: level,
    last_escalation_at: iso(now),
    escalation_active: level < contacts.length,
  });
}

export async function forceMissed(app, elder) {
  const now = utcnow();
  const checkin = await createCheckin(app, elder, now, null, kindFor(elder, now));
  await updateCheckin(app, checkin, {
    status: "missed",
    attempt: 3,
    last_prompt_at: iso(now),
    escalation_active: true,
    escalation_level: 0,
  });
  await escalateNext(app, checkin, elder, now);
  return checkin;
}

export async function acknowledge(app, alert) {
  const now = iso(utcnow());
  await run(app, "UPDATE alerts SET acknowledged_at=? WHERE id=?", now, alert.id);
  alert.acknowledged_at = now;
  if (alert.checkin_id) await run(app, "UPDATE checkins SET escalation_active=0 WHERE id=?", alert.checkin_id);
  return alert;
}

export async function buildSummary(app, elder, days = 7, now = utcnow()) {
  const tz = elder.timezone;
  const todayKey = localDateKey(now, tz);
  const daily = {};
  for (let i = 0; i < days; i++) {
    const key = addDaysToKey(todayKey, -(days - 1 - i));
    daily[key] = { date: key, yes: 0, no: 0, unknown: 0, responded: 0, missed: 0 };
  }
  const since = iso(new Date(now.getTime() - (days + 1) * 86400000));
  const rows = await all(
    app,
    "SELECT scheduled_at, status, classification, mood, medicine_taken, summary, responded_at, gateway_cost_usd, gateway_fallback, classifier_error FROM checkins WHERE elder_id=? AND scheduled_at >= ? ORDER BY scheduled_at",
    elder.id,
    since,
  );
  let total = 0;
  let responded = 0;
  let missed = 0;
  let yes = 0;
  let no = 0;
  let unknown = 0;
  const statusCounts = {};
  const moodCounts = {};
  const notes = [];
  let cost = 0;
  let fallbacks = 0;
  let blocked = 0;
  for (const row of rows) {
    const key = localDateKey(parseDate(row.scheduled_at), tz);
    const bucket = daily[key];
    if (!bucket) continue;
    total += 1;
    if (row.status === "completed") {
      responded += 1;
      bucket.responded += 1;
      cost += row.gateway_cost_usd || 0;
      if (row.gateway_fallback) fallbacks += 1;
      if ((row.classifier_error || "").startsWith("budget:") || (row.classifier_error || "").startsWith("guardrail:")) blocked += 1;
      const cls = row.classification || "unclear";
      statusCounts[cls] = (statusCounts[cls] || 0) + 1;
      if (row.mood && row.mood !== "unknown") moodCounts[row.mood] = (moodCounts[row.mood] || 0) + 1;
      if (row.medicine_taken === "yes") {
        yes += 1;
        bucket.yes += 1;
      } else if (row.medicine_taken === "no") {
        no += 1;
        bucket.no += 1;
      } else {
        unknown += 1;
        bucket.unknown += 1;
      }
      if (row.summary) notes.push({ at: row.responded_at || row.scheduled_at, summary: row.summary });
    } else if (row.status === "missed") {
      missed += 1;
      bucket.missed += 1;
    }
  }
  const recent = [];
  for (const n of notes.slice(-3)) {
    const text = await decrypt(app.s.encryptionKey, n.summary);
    recent.push(`${formatLocal(parseDate(n.at), tz)}: ${text}`);
  }
  const counts = await first(
    app,
    "SELECT SUM(CASE WHEN severity != 'info' THEN 1 ELSE 0 END) AS total, SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) AS critical FROM alerts WHERE elder_id=? AND sent_at >= ?",
    elder.id,
    since,
  );
  return {
    period_days: days,
    total,
    responded,
    missed,
    response_rate: total ? Math.round((100 * responded) / total) : null,
    medicine_yes: yes,
    medicine_no: no,
    medicine_unknown: unknown,
    adherence_pct: yes + no ? Math.round((100 * yes) / (yes + no)) : null,
    status_counts: statusCounts,
    mood_counts: moodCounts,
    alerts_total: (counts && counts.total) || 0,
    critical_alerts: (counts && counts.critical) || 0,
    daily: Object.values(daily),
    recent_summaries: recent,
    ai_cost_usd: Math.round(cost * 1e6) / 1e6,
    ai_fallbacks: fallbacks,
    ai_blocked: blocked,
  };
}

async function sendWeeklySummaries(app, now) {
  const s = app.s;
  if (pyWeekday(now) !== s.summaryWeekday || now.getUTCHours() !== s.summaryHourUtc) return;
  const [year, week] = isoWeek(now);
  const weekKey = `${year}-W${String(week).padStart(2, "0")}`;
  const rows = await all(app, "SELECT * FROM elders WHERE active=1");
  for (const row of rows) {
    const result = await run(app, "INSERT OR IGNORE INTO summary_logs (elder_id, week_key) VALUES (?,?)", row.id, weekKey);
    if (!result.meta.changes) continue;
    const elder = await hydrate(app, elderFromRow(row));
    const stats = await buildSummary(app, elder, 7, now);
    const note = await narrator.weeklyNote(s, elder.name, elder.id, stats);
    for (const contact of elder.contacts) {
      if (contact.email && (contact.channel === "email" || contact.channel === "both")) {
        const [subject, body] = notifier.composeSummary(app, elder, stats, note);
        try {
          await notifier.sendEmail(s, contact.email, subject, body);
        } catch (err) {
          console.warn("Weekly summary email failed:", String(err.message || err));
        }
      }
    }
  }
}

async function handleAwaiting(app, checkin, now) {
  const elder = await loadElder(app, checkin.elder_id);
  if (!elder || !elder.active) {
    await updateCheckin(app, checkin, { status: "cancelled" });
    return;
  }
  const action = escalation.planRetry(
    checkin.attempt,
    parseDate(checkin.last_prompt_at || checkin.created_at),
    now,
    app.s.retryDelays,
    app.s.finalWaitMinutes,
  );
  if (action === "retry") {
    await updateCheckin(app, checkin, { attempt: checkin.attempt + 1 });
    await sendPrompt(app, checkin, elder, now);
  } else if (action === "miss") {
    await updateCheckin(app, checkin, { status: "missed", escalation_active: true, escalation_level: 0 });
    await escalateNext(app, checkin, elder, now);
  }
}

async function handleEscalating(app, checkin, now) {
  const elder = await loadElder(app, checkin.elder_id);
  if (!elder) return;
  const acknowledged = await first(app, "SELECT id FROM alerts WHERE checkin_id=? AND acknowledged_at IS NOT NULL", checkin.id);
  if (acknowledged) {
    await updateCheckin(app, checkin, { escalation_active: false });
    return;
  }
  if (escalation.escalationDue(parseDate(checkin.last_escalation_at), now, app.s.escalationDelayMinutes)) {
    await escalateNext(app, checkin, elder, now);
  }
}

export async function runTick(app, now = utcnow()) {
  const s = app.s;
  let created = 0;
  const elders = await all(app, "SELECT * FROM elders WHERE active=1 AND consent_at IS NOT NULL");
  for (const row of elders) {
    const elder = elderFromRow(row);
    const slots = escalation.dueSlots(elder.check_in_times, elder.timezone, now, s.slotGraceMinutes);
    if (!slots.length) continue;
    await hydrate(app, elder);
    for (const [, slot] of slots) {
      const checkin = await createCheckin(app, elder, slot);
      if (!checkin) continue;
      created += 1;
      await sendPrompt(app, checkin, elder, now);
    }
  }
  const awaiting = await all(app, "SELECT * FROM checkins WHERE status='awaiting_reply'");
  for (const row of awaiting) await handleAwaiting(app, await checkinFromRow(app, row), now);
  const escalating = await all(app, "SELECT * FROM checkins WHERE escalation_active=1");
  for (const row of escalating) await handleEscalating(app, await checkinFromRow(app, row), now);
  await sendWeeklySummaries(app, now);
  return { skipped: false, created };
}

export { loadCheckin };
