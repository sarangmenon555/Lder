import { LANGUAGES } from "./languages.js";
import { validZone } from "./time.js";
import { HttpError } from "./http.js";

const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/;
const CHANNELS = ["email", "whatsapp", "both", "dashboard"];

const fail = (message) => {
  throw new HttpError(422, message);
};

const digits = (v) => String(v ?? "").replace(/\D/g, "");

function text(value, label, { min = 0, max = 200, fallback = "" } = {}) {
  const v = value === undefined || value === null ? fallback : String(value);
  if (v.length < min) fail(`${label} is required`);
  if (v.length > max) fail(`${label} is too long`);
  return v;
}

function time(value, fallback) {
  const v = value === undefined || value === null ? fallback : String(value);
  if (!TIME_RE.test(v)) fail("Time must be in HH:MM format");
  return v;
}

function zone(value) {
  const v = value === undefined || value === null ? "Asia/Kolkata" : String(value);
  if (!validZone(v)) fail("Unknown time zone");
  return v;
}

export function validateContact(c) {
  if (!c || typeof c !== "object") fail("Invalid contact");
  const channel = c.channel === undefined ? "dashboard" : c.channel;
  if (!CHANNELS.includes(channel)) fail("Invalid contact channel");
  let priority = c.priority === undefined ? 1 : Number(c.priority);
  if (!Number.isInteger(priority) || priority < 1 || priority > 20) fail("Priority must be between 1 and 20");
  return {
    id: c.id === undefined || c.id === null ? null : Number(c.id),
    name: text(c.name, "Contact name", { min: 1, max: 120 }),
    email: text(c.email, "Email", { max: 200 }),
    phone: digits(c.phone),
    channel,
    priority,
    timezone: zone(c.timezone),
  };
}

export function validateMedicine(m) {
  if (!m || typeof m !== "object") fail("Invalid medicine");
  return {
    id: m.id === undefined || m.id === null ? null : Number(m.id),
    name: text(m.name, "Medicine name", { min: 1, max: 120 }),
    time_of_day: time(m.time_of_day, "08:00"),
  };
}

export function validateElder(body) {
  const code = String(body.language === undefined ? "ml" : body.language).trim().toLowerCase();
  if (!(code in LANGUAGES)) fail("Choose one of: " + Object.keys(LANGUAGES).join(", "));
  const times = [...new Set((body.check_in_times === undefined ? ["08:30", "19:00"] : body.check_in_times).map((t) => time(t, "")))].sort();
  if (times.length > 6) fail("At most 6 check-in times are allowed");
  const contacts = body.contacts === undefined ? [] : body.contacts;
  const medicines = body.medicines === undefined ? [] : body.medicines;
  if (!Array.isArray(contacts) || !Array.isArray(medicines)) fail("contacts and medicines must be lists");
  return {
    name: text(body.name, "Name", { min: 1, max: 120 }),
    phone: digits(body.phone),
    language: code,
    timezone: zone(body.timezone),
    check_in_times: times,
    consent: Boolean(body.consent),
    active: body.active === undefined ? true : Boolean(body.active),
    contacts: contacts.map(validateContact),
    medicines: medicines.map(validateMedicine),
  };
}
