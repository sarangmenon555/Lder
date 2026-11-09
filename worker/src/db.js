import { decrypt, encrypt } from "./crypto.js";
import { iso, utcnow } from "./time.js";
import { randomToken } from "./security.js";

export async function first(app, sql, ...binds) {
  return app.db.prepare(sql).bind(...binds).first();
}

export async function all(app, sql, ...binds) {
  const result = await app.db.prepare(sql).bind(...binds).all();
  return result.results || [];
}

export async function run(app, sql, ...binds) {
  return app.db.prepare(sql).bind(...binds).run();
}

export function elderFromRow(row) {
  if (!row) return null;
  let times = [];
  try {
    times = JSON.parse(row.check_in_times || "[]");
  } catch {
    times = [];
  }
  return { ...row, check_in_times: times, active: Boolean(row.active), contacts: [], medicines: [] };
}

export async function hydrate(app, elder) {
  if (!elder) return null;
  const [contacts, medicines] = await app.db.batch([
    app.db.prepare("SELECT * FROM contacts WHERE elder_id = ? ORDER BY priority, id").bind(elder.id),
    app.db.prepare("SELECT * FROM medicines WHERE elder_id = ? ORDER BY time_of_day, id").bind(elder.id),
  ]);
  elder.contacts = contacts.results || [];
  elder.medicines = medicines.results || [];
  return elder;
}

export async function loadElder(app, id) {
  return hydrate(app, elderFromRow(await first(app, "SELECT * FROM elders WHERE id = ?", id)));
}

export async function loadElderByToken(app, token) {
  return hydrate(app, elderFromRow(await first(app, "SELECT * FROM elders WHERE access_token = ?", token)));
}

export async function listElders(app) {
  const [elders, contacts, medicines] = await app.db.batch([
    app.db.prepare("SELECT * FROM elders ORDER BY name"),
    app.db.prepare("SELECT * FROM contacts ORDER BY priority, id"),
    app.db.prepare("SELECT * FROM medicines ORDER BY time_of_day, id"),
  ]);
  const byElder = (rows) => {
    const map = new Map();
    for (const r of rows.results || []) {
      if (!map.has(r.elder_id)) map.set(r.elder_id, []);
      map.get(r.elder_id).push(r);
    }
    return map;
  };
  const c = byElder(contacts);
  const m = byElder(medicines);
  return (elders.results || []).map((row) => {
    const elder = elderFromRow(row);
    elder.contacts = c.get(elder.id) || [];
    elder.medicines = m.get(elder.id) || [];
    return elder;
  });
}

export async function saveElder(app, id, payload) {
  const now = iso(utcnow());
  let existing = null;
  if (id !== null) {
    existing = await loadElder(app, id);
    if (!existing) return null;
  }
  let consentAt = existing ? existing.consent_at : null;
  if (payload.consent && !consentAt) consentAt = now;
  if (!payload.consent) consentAt = null;
  const times = JSON.stringify(payload.check_in_times);
  let elderId = id;
  if (existing) {
    await run(
      app,
      "UPDATE elders SET name=?, phone=?, language=?, timezone=?, check_in_times=?, active=?, consent_at=? WHERE id=?",
      payload.name,
      payload.phone,
      payload.language,
      payload.timezone,
      times,
      payload.active ? 1 : 0,
      consentAt,
      id,
    );
  } else {
    const result = await run(
      app,
      "INSERT INTO elders (name, phone, language, timezone, check_in_times, consent_at, active, access_token, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
      payload.name,
      payload.phone,
      payload.language,
      payload.timezone,
      times,
      consentAt,
      payload.active ? 1 : 0,
      randomToken(24),
      now,
    );
    elderId = result.meta.last_row_id;
  }
  const statements = [];
  const keepContacts = new Set(existing ? existing.contacts.map((c) => c.id) : []);
  const seenContacts = new Set();
  for (const c of payload.contacts) {
    if (c.id !== null && c.id !== undefined && keepContacts.has(c.id)) {
      seenContacts.add(c.id);
      statements.push(
        app.db
          .prepare("UPDATE contacts SET name=?, email=?, phone=?, channel=?, priority=?, timezone=? WHERE id=? AND elder_id=?")
          .bind(c.name, c.email, c.phone, c.channel, c.priority, c.timezone, c.id, elderId),
      );
    } else {
      statements.push(
        app.db
          .prepare("INSERT INTO contacts (elder_id, name, email, phone, channel, priority, timezone) VALUES (?,?,?,?,?,?,?)")
          .bind(elderId, c.name, c.email, c.phone, c.channel, c.priority, c.timezone),
      );
    }
  }
  for (const oldId of keepContacts) {
    if (!seenContacts.has(oldId)) statements.push(app.db.prepare("DELETE FROM contacts WHERE id=?").bind(oldId));
  }
  const keepMeds = new Set(existing ? existing.medicines.map((m) => m.id) : []);
  const seenMeds = new Set();
  for (const m of payload.medicines) {
    if (m.id !== null && m.id !== undefined && keepMeds.has(m.id)) {
      seenMeds.add(m.id);
      statements.push(
        app.db.prepare("UPDATE medicines SET name=?, time_of_day=? WHERE id=? AND elder_id=?").bind(m.name, m.time_of_day, m.id, elderId),
      );
    } else {
      statements.push(app.db.prepare("INSERT INTO medicines (elder_id, name, time_of_day) VALUES (?,?,?)").bind(elderId, m.name, m.time_of_day));
    }
  }
  for (const oldId of keepMeds) {
    if (!seenMeds.has(oldId)) statements.push(app.db.prepare("DELETE FROM medicines WHERE id=?").bind(oldId));
  }
  if (statements.length) await app.db.batch(statements);
  return loadElder(app, elderId);
}

export async function deleteElder(app, id) {
  await app.db.batch([
    app.db.prepare("DELETE FROM alerts WHERE elder_id=?").bind(id),
    app.db.prepare("DELETE FROM checkins WHERE elder_id=?").bind(id),
    app.db.prepare("DELETE FROM summary_logs WHERE elder_id=?").bind(id),
    app.db.prepare("DELETE FROM contacts WHERE elder_id=?").bind(id),
    app.db.prepare("DELETE FROM medicines WHERE elder_id=?").bind(id),
    app.db.prepare("DELETE FROM elders WHERE id=?").bind(id),
  ]);
}

export async function checkinFromRow(app, row) {
  if (!row) return null;
  let hits = [];
  try {
    hits = JSON.parse(row.keyword_hits || "[]");
  } catch {
    hits = [];
  }
  const key = app.s.encryptionKey;
  return {
    ...row,
    escalation_active: Boolean(row.escalation_active),
    distress: Boolean(row.distress),
    keyword_hits: hits,
    gateway_fallback: row.gateway_fallback === null || row.gateway_fallback === undefined ? null : Boolean(row.gateway_fallback),
    transcript: await decrypt(key, row.transcript),
    summary: await decrypt(key, row.summary),
  };
}

export async function loadCheckin(app, id) {
  return checkinFromRow(app, await first(app, "SELECT * FROM checkins WHERE id = ?", id));
}

export async function insertCheckin(app, { elderId, scheduledAt, kind, channel }) {
  const now = iso(utcnow());
  const result = await run(
    app,
    "INSERT OR IGNORE INTO checkins (elder_id, scheduled_at, kind, channel, status, attempt, created_at) VALUES (?,?,?,?, 'awaiting_reply', 1, ?)",
    elderId,
    iso(scheduledAt),
    kind,
    channel,
    now,
  );
  if (!result.meta.changes) return null;
  return loadCheckin(app, result.meta.last_row_id);
}

const BOOLEAN_FIELDS = new Set(["escalation_active", "distress", "gateway_fallback"]);
const ENCRYPTED_FIELDS = new Set(["transcript", "summary"]);

export async function updateCheckin(app, checkin, fields) {
  const keys = Object.keys(fields);
  if (!keys.length) return checkin;
  const values = [];
  for (const k of keys) {
    let v = fields[k];
    if (BOOLEAN_FIELDS.has(k) && v !== null && v !== undefined) v = v ? 1 : 0;
    else if (k === "keyword_hits") v = JSON.stringify(v);
    else if (ENCRYPTED_FIELDS.has(k)) v = await encrypt(app.s.encryptionKey, v);
    values.push(v === undefined ? null : v);
  }
  await run(app, `UPDATE checkins SET ${keys.map((k) => `${k}=?`).join(", ")} WHERE id=?`, ...values, checkin.id);
  Object.assign(checkin, fields);
  return checkin;
}

export async function alertFromRow(app, row) {
  if (!row) return null;
  return {
    ...row,
    delivered: Boolean(row.delivered),
    message: await decrypt(app.s.encryptionKey, row.message),
  };
}

export async function insertAlert(app, a) {
  const message = await encrypt(app.s.encryptionKey, a.message || "");
  const result = await run(
    app,
    "INSERT INTO alerts (elder_id, checkin_id, contact_id, severity, reason, message, channel, delivered, error, sent_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
    a.elder_id,
    a.checkin_id ?? null,
    a.contact_id ?? null,
    a.severity,
    a.reason,
    message,
    a.channel,
    a.delivered ? 1 : 0,
    a.error ?? null,
    a.sent_at,
  );
  return { ...a, id: result.meta.last_row_id, acknowledged_at: null };
}
