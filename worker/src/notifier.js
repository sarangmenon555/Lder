import { formatLocal } from "./time.js";
import * as whatsapp from "./whatsapp.js";

export class NotifierError extends Error {}

const TITLES = {
  distress: "Urgent: {name} may need help",
  missed_checkin: "Missed check-in: {name} has not replied",
  needs_follow_up: "Follow-up suggested: {name}",
  medicine_missed: "Medicine not taken: {name}",
  pattern: "Pattern noticed: {name} has seemed unwell for several check-ins",
  late_response: "Update: {name} has now replied",
};

const ACTIONS = {
  distress: "Please call {name} right away.",
  missed_checkin: "Please try calling {name} now.",
  needs_follow_up: "Please call {name} when you can.",
  medicine_missed: "Please remind {name} about the medicine.",
  pattern: "Please arrange a call or a visit.",
  late_response: "No further action is needed unless you are still concerned.",
};

const FOOTER =
  "Lder is a check-in aid, not an emergency service. If you cannot reach {name} and are worried, contact local emergency services (112 in India).";

const fill = (text, name) => text.replaceAll("{name}", name);

export function emailEnabled(s) {
  return Boolean(s.emailApiUrl && s.emailApiKey && s.emailFrom);
}

export async function sendEmail(s, to, subject, body) {
  if (!emailEnabled(s)) throw new NotifierError("Email is not configured");
  if (!to) throw new NotifierError("Contact has no email address");
  let headers;
  let payload;
  if (s.emailApiUrl.includes("brevo") || s.emailApiUrl.includes("sendinblue")) {
    headers = { "api-key": s.emailApiKey, "Content-Type": "application/json" };
    payload = { sender: { email: s.emailFrom }, to: [{ email: to }], subject, textContent: body };
  } else {
    headers = { Authorization: `Bearer ${s.emailApiKey}`, "Content-Type": "application/json" };
    payload = { from: s.emailFrom, to: [to], subject, text: body };
  }
  let response;
  try {
    response = await fetch(s.emailApiUrl, { method: "POST", headers, body: JSON.stringify(payload), signal: AbortSignal.timeout(20000) });
  } catch (err) {
    throw new NotifierError(`Email failed: ${err.message || err}`);
  }
  if (response.status >= 400) {
    const text = await response.text().catch(() => "");
    throw new NotifierError(`Email failed: ${response.status} ${text.slice(0, 200)}`);
  }
}

export function dashboardLink(app, elder) {
  const base = (app.s.frontendBaseUrl || app.origin || "").replace(/\/$/, "");
  return `${base}/elder/?id=${elder.id}`;
}

export function composeAlert(app, elder, contact, checkin, reason, when) {
  const tz = contact ? contact.timezone : elder.timezone;
  const title = fill(TITLES[reason] || "Check-in update: {name}", elder.name);
  const lines = [title, "", `Time: ${formatLocal(when, tz)}`, `Local time for ${elder.name}: ${formatLocal(when, elder.timezone)}`];
  if (checkin && checkin.summary) lines.push(`Summary: ${checkin.summary}`);
  if (checkin && checkin.transcript) {
    let excerpt = checkin.transcript.trim().replaceAll("\n", " ");
    if (excerpt.length > 240) excerpt = excerpt.slice(0, 240) + "...";
    lines.push(`What they said: "${excerpt}"`);
  }
  lines.push(
    "",
    fill(ACTIONS[reason] || "", elder.name),
    `Dashboard: ${dashboardLink(app, elder)}`,
    "To acknowledge, reply OK to this message on WhatsApp or press Acknowledge in the dashboard.",
    "",
    fill(FOOTER, elder.name),
  );
  return ["[Lder] " + title, lines.join("\n")];
}

export async function dispatchAlert(app, elder, contact, checkin, reason, now) {
  const [subject, body] = composeAlert(app, elder, contact, checkin, reason, now);
  const channels = [];
  if (contact) {
    if (contact.channel === "email" || contact.channel === "both") channels.push("email");
    if (contact.channel === "whatsapp" || contact.channel === "both") channels.push("whatsapp");
  }
  const delivered = [];
  const errors = [];
  for (const channel of channels) {
    try {
      if (channel === "email") await sendEmail(app.s, contact.email, subject, body);
      else await whatsapp.sendToContact(app, contact, subject + "\n\n" + body, now);
      delivered.push(channel);
    } catch (err) {
      errors.push(`${channel}: ${err.message || err}`);
    }
  }
  let channel;
  let ok;
  if (!channels.length) {
    channel = "dashboard";
    ok = true;
  } else {
    channel = (delivered.length ? delivered : channels).join("+");
    ok = delivered.length > 0;
  }
  return { message: body, channel, delivered: ok, error: errors.length ? errors.join("; ") : null };
}

export function composeSummary(app, elder, stats, note = null) {
  const rate = stats.response_rate;
  const adherence = stats.adherence_pct;
  const lines = [`Weekly summary for ${elder.name}`, ""];
  if (note) lines.push(note, "");
  lines.push(
    `Check-ins: ${stats.total} scheduled, ${stats.responded} answered, ${stats.missed} missed` + (rate !== null ? ` (${rate}% answered).` : "."),
    "Medicine: " + (adherence !== null ? `${adherence}% of reported doses were taken.` : "no clear reports this week."),
    `Alerts raised: ${stats.alerts_total} (urgent: ${stats.critical_alerts}).`,
  );
  const entries = Object.entries(stats.status_counts).sort(([a], [b]) => (a < b ? -1 : 1));
  if (entries.length) lines.push(`How the replies looked: ${entries.map(([k, v]) => `${k.replaceAll("_", " ")} ${v}`).join(", ")}.`);
  if (stats.recent_summaries.length) lines.push("", "Recent notes:", ...stats.recent_summaries.map((x) => `- ${x}`));
  lines.push("", `Dashboard: ${dashboardLink(app, elder)}`);
  return [`[Lder] Weekly summary for ${elder.name}`, lines.join("\n")];
}
