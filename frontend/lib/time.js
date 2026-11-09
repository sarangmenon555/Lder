export const ZONES = [
  "Asia/Kolkata",
  "Asia/Dubai",
  "Asia/Riyadh",
  "Asia/Qatar",
  "Asia/Kuwait",
  "Asia/Muscat",
  "Asia/Bahrain",
  "Asia/Singapore",
  "Europe/London",
  "Europe/Berlin",
  "America/New_York",
  "America/Chicago",
  "America/Los_Angeles",
  "Australia/Sydney",
];

export function parseIso(iso) {
  if (!iso) return null;
  const hasZone = /Z$|[+-]\d\d:?\d\d$/.test(iso);
  return new Date(hasZone ? iso : `${iso}Z`);
}

export function formatDateTime(iso, tz) {
  const d = parseIso(iso);
  if (!d) return "";
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: tz,
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  }).format(d);
}

export function formatTime(iso, tz) {
  const d = parseIso(iso);
  if (!d) return "";
  return new Intl.DateTimeFormat("en-IN", { timeZone: tz, hour: "numeric", minute: "2-digit" }).format(d);
}

export function zoneName(tz) {
  try {
    const parts = new Intl.DateTimeFormat("en", { timeZone: tz, timeZoneName: "short" }).formatToParts(new Date());
    return parts.find((p) => p.type === "timeZoneName")?.value || tz;
  } catch {
    return tz;
  }
}

export function localNow(tz) {
  try {
    return new Intl.DateTimeFormat("en-IN", {
      timeZone: tz,
      weekday: "short",
      hour: "numeric",
      minute: "2-digit",
    }).format(new Date());
  } catch {
    return "";
  }
}

export function shortDay(dateStr) {
  const [y, m, d] = dateStr.split("-").map(Number);
  return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", timeZone: "UTC" }).format(
    new Date(Date.UTC(y, m - 1, d))
  );
}
