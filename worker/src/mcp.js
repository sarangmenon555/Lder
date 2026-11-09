import { all } from "./db.js";
import { buildSummary } from "./checkins.js";
import { decrypt } from "./crypto.js";
import { formatLocal, parseDate } from "./time.js";

const SUPPORTED = ["2025-06-18", "2025-03-26", "2024-11-05"];
const SERVER_INFO = { name: "lder-checkins", version: "1.0.0" };

const limitSchema = (def) => ({
  type: "object",
  properties: { limit: { type: "integer", minimum: 1, maximum: 30, default: def } },
  additionalProperties: false,
});

export const TOOLS = [
  {
    name: "get_profile",
    description: "Basic profile of the person: name, language, time zone, check-in times and medicine schedule.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
  },
  {
    name: "get_recent_checkins",
    description: "Most recent check-ins with status, mood, medicine report and a short summary. Newest first.",
    inputSchema: limitSchema(10),
  },
  {
    name: "get_summary",
    description: "Statistics for the last N days: response rate, medicine adherence, mood mix, alert counts.",
    inputSchema: {
      type: "object",
      properties: { days: { type: "integer", minimum: 1, maximum: 30, default: 7 } },
      additionalProperties: false,
    },
  },
  {
    name: "get_alerts",
    description: "Recent alerts for this person with severity, reason, time and whether it was acknowledged.",
    inputSchema: limitSchema(10),
  },
];

export const TOOL_NAMES = TOOLS.map((t) => t.name);

function intArg(args, name, def, low, high) {
  let v = parseInt(args[name] ?? def, 10);
  if (!Number.isFinite(v)) v = def;
  return Math.max(low, Math.min(high, v));
}

export async function runTool(app, elder, name, args) {
  if (name === "get_profile") {
    return {
      name: elder.name,
      language: elder.language,
      timezone: elder.timezone,
      check_in_times: elder.check_in_times,
      active: elder.active,
      medicines: elder.medicines.map((m) => ({ name: m.name, time_of_day: m.time_of_day })),
    };
  }
  if (name === "get_recent_checkins") {
    const limit = intArg(args, "limit", 10, 1, 30);
    const rows = await all(app, "SELECT * FROM checkins WHERE elder_id=? ORDER BY scheduled_at DESC LIMIT ?", elder.id, limit);
    const out = [];
    for (const row of rows) {
      out.push({
        time: formatLocal(parseDate(row.responded_at || row.scheduled_at), elder.timezone),
        kind: row.kind,
        status: row.status,
        classification: row.classification,
        medicine_taken: row.medicine_taken,
        mood: row.mood,
        summary: await decrypt(app.s.encryptionKey, row.summary),
      });
    }
    return { checkins: out };
  }
  if (name === "get_summary") {
    const stats = await buildSummary(app, elder, intArg(args, "days", 7, 1, 30));
    delete stats.recent_summaries;
    return stats;
  }
  if (name === "get_alerts") {
    const limit = intArg(args, "limit", 10, 1, 30);
    const rows = await all(app, "SELECT * FROM alerts WHERE elder_id=? ORDER BY sent_at DESC LIMIT ?", elder.id, limit);
    return {
      alerts: rows.map((r) => ({
        time: formatLocal(parseDate(r.sent_at), elder.timezone),
        severity: r.severity,
        reason: r.reason,
        acknowledged: r.acknowledged_at !== null,
      })),
    };
  }
  throw new Error(name);
}

const result = (id, value) => ({ jsonrpc: "2.0", id, result: value });
const error = (id, code, message) => ({ jsonrpc: "2.0", id, error: { code, message } });

export async function handleMessage(app, elder, message) {
  if (!message || typeof message !== "object" || message.jsonrpc !== "2.0") return error(null, -32600, "Invalid request");
  const { method } = message;
  const id = message.id;
  const params = message.params || {};
  if (id === undefined || id === null) return null;
  if (method === "initialize") {
    const version = SUPPORTED.includes(params.protocolVersion) ? params.protocolVersion : SUPPORTED[0];
    return result(id, { protocolVersion: version, capabilities: { tools: { listChanged: false } }, serverInfo: SERVER_INFO });
  }
  if (method === "ping") return result(id, {});
  if (method === "tools/list") return result(id, { tools: TOOLS });
  if (method === "tools/call") {
    const args = params.arguments || {};
    if (!TOOL_NAMES.includes(params.name) || typeof args !== "object" || Array.isArray(args)) {
      return error(id, -32602, "Unknown tool or invalid arguments");
    }
    const data = await runTool(app, elder, params.name, args);
    return result(id, { content: [{ type: "text", text: JSON.stringify(data) }], isError: false });
  }
  return error(id, -32601, "Method not found");
}
