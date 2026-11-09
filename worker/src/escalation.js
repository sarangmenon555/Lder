import { addDaysToKey, localParts, localToUtc, localDateKey } from "./time.js";

export function planRetry(attempt, lastPromptAt, now, delays, finalWait) {
  if (attempt <= delays.length) {
    const due = lastPromptAt.getTime() + delays[attempt - 1] * 60000;
    return now.getTime() >= due ? "retry" : "wait";
  }
  const due = lastPromptAt.getTime() + finalWait * 60000;
  return now.getTime() >= due ? "miss" : "wait";
}

export function escalationDue(lastEscalationAt, now, delayMinutes) {
  if (!lastEscalationAt) return true;
  return now.getTime() >= lastEscalationAt.getTime() + delayMinutes * 60000;
}

export function pickContact(contacts, level) {
  return level >= 0 && level < contacts.length ? contacts[level] : null;
}

export function dueSlots(times, tz, now, graceMinutes) {
  const slots = [];
  const todayKey = localDateKey(now, tz);
  for (const label of times) {
    const [hour, minute] = label.split(":").map(Number);
    for (const offset of [0, -1]) {
      const key = addDaysToKey(todayKey, offset);
      const [y, m, d] = key.split("-").map(Number);
      const slot = localToUtc(y, m, d, hour, minute, tz);
      if (slot.getTime() <= now.getTime() && now.getTime() < slot.getTime() + graceMinutes * 60000) slots.push([label, slot]);
    }
  }
  return slots;
}

export { localParts };
