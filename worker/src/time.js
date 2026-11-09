const formatters = new Map();

function fmt(tz, options, key) {
  const id = tz + "|" + key;
  let f = formatters.get(id);
  if (!f) {
    f = new Intl.DateTimeFormat("en-US", { timeZone: tz, hourCycle: "h23", ...options });
    formatters.set(id, f);
  }
  return f;
}

const PARTS = { year: "numeric", month: "numeric", day: "numeric", hour: "numeric", minute: "numeric", second: "numeric" };

export function validZone(name) {
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: name });
    return true;
  } catch {
    return false;
  }
}

export function zoneOrDefault(name, fallback = "Asia/Kolkata") {
  return name && validZone(name) ? name : fallback;
}

export function utcnow() {
  return new Date();
}

export function iso(date) {
  return date.toISOString();
}

export function parseDate(value) {
  return value ? new Date(value) : null;
}

export function localParts(date, tz) {
  const zone = zoneOrDefault(tz);
  const parts = fmt(zone, PARTS, "p").formatToParts(date);
  const out = {};
  for (const p of parts) if (p.type !== "literal") out[p.type] = Number(p.value);
  if (out.hour === 24) out.hour = 0;
  return out;
}

export function offsetMinutes(date, tz) {
  const p = localParts(date, tz);
  const asUtc = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second);
  return Math.round((asUtc - Math.floor(date.getTime() / 1000) * 1000) / 60000);
}

export function localToUtc(year, month, day, hour, minute, tz) {
  const guess = Date.UTC(year, month - 1, day, hour, minute, 0);
  let result = guess - offsetMinutes(new Date(guess), tz) * 60000;
  result = guess - offsetMinutes(new Date(result), tz) * 60000;
  return new Date(result);
}

export function localDateKey(date, tz) {
  const p = localParts(date, tz);
  return `${p.year}-${String(p.month).padStart(2, "0")}-${String(p.day).padStart(2, "0")}`;
}

export function addDaysToKey(key, days) {
  const [y, m, d] = key.split("-").map(Number);
  const t = new Date(Date.UTC(y, m - 1, d + days));
  return t.toISOString().slice(0, 10);
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function formatLocal(date, tz) {
  const zone = zoneOrDefault(tz);
  const p = localParts(date, zone);
  const h12 = p.hour % 12 === 0 ? 12 : p.hour % 12;
  const name = fmt(zone, { timeZoneName: "short" }, "n")
    .formatToParts(date)
    .find((x) => x.type === "timeZoneName");
  return `${String(p.day).padStart(2, "0")} ${MONTHS[p.month - 1]} ${p.year}, ${String(h12).padStart(2, "0")}:${String(p.minute).padStart(2, "0")} ${p.hour < 12 ? "AM" : "PM"} ${name ? name.value : ""}`.trim();
}

export function isoWeek(date) {
  const d = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  const day = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return [d.getUTCFullYear(), Math.ceil(((d - yearStart) / 86400000 + 1) / 7)];
}

export function pyWeekday(date) {
  return (date.getUTCDay() + 6) % 7;
}
