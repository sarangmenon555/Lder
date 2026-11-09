export const contactOut = (c) => ({
  id: c.id,
  name: c.name,
  email: c.email,
  phone: c.phone,
  channel: c.channel,
  priority: c.priority,
  timezone: c.timezone,
});

export const medicineOut = (m) => ({ id: m.id, name: m.name, time_of_day: m.time_of_day });

export const elderOut = (e) => ({
  id: e.id,
  name: e.name,
  phone: e.phone,
  language: e.language,
  timezone: e.timezone,
  check_in_times: e.check_in_times,
  consent_at: e.consent_at,
  active: e.active,
  access_token: e.access_token,
  created_at: e.created_at,
  contacts: e.contacts.map(contactOut),
  medicines: e.medicines.map(medicineOut),
});

export const checkinOut = (c) => ({
  id: c.id,
  elder_id: c.elder_id,
  scheduled_at: c.scheduled_at,
  kind: c.kind,
  channel: c.channel,
  status: c.status,
  attempt: c.attempt,
  escalation_active: c.escalation_active,
  escalation_level: c.escalation_level,
  transcript: c.transcript,
  classification: c.classification,
  medicine_taken: c.medicine_taken,
  distress: c.distress,
  mood: c.mood,
  confidence: c.confidence,
  summary: c.summary,
  keyword_hits: c.keyword_hits,
  classifier_error: c.classifier_error,
  model_used: c.model_used,
  gateway_fallback: c.gateway_fallback,
  gateway_cost_usd: c.gateway_cost_usd,
  responded_at: c.responded_at,
});

export const alertOut = (a, elderName, contactName) => ({
  id: a.id,
  elder_id: a.elder_id,
  elder_name: elderName || "",
  checkin_id: a.checkin_id,
  contact_id: a.contact_id,
  contact_name: contactName || null,
  severity: a.severity,
  reason: a.reason,
  message: a.message,
  channel: a.channel,
  delivered: a.delivered,
  error: a.error,
  sent_at: a.sent_at,
  acknowledged_at: a.acknowledged_at,
});
