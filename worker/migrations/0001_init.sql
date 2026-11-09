CREATE TABLE IF NOT EXISTS elders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  phone TEXT NOT NULL DEFAULT '',
  language TEXT NOT NULL DEFAULT 'ml',
  timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
  check_in_times TEXT NOT NULL DEFAULT '[]',
  consent_at TEXT,
  active INTEGER NOT NULL DEFAULT 1,
  access_token TEXT NOT NULL UNIQUE,
  last_inbound_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  elder_id INTEGER NOT NULL REFERENCES elders(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  email TEXT NOT NULL DEFAULT '',
  phone TEXT NOT NULL DEFAULT '',
  channel TEXT NOT NULL DEFAULT 'dashboard',
  priority INTEGER NOT NULL DEFAULT 1,
  timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
  last_inbound_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_contacts_elder ON contacts(elder_id);

CREATE TABLE IF NOT EXISTS medicines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  elder_id INTEGER NOT NULL REFERENCES elders(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  time_of_day TEXT NOT NULL DEFAULT '08:00'
);
CREATE INDEX IF NOT EXISTS ix_medicines_elder ON medicines(elder_id);

CREATE TABLE IF NOT EXISTS checkins (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  elder_id INTEGER NOT NULL REFERENCES elders(id) ON DELETE CASCADE,
  scheduled_at TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'morning',
  channel TEXT NOT NULL DEFAULT 'simulator',
  status TEXT NOT NULL DEFAULT 'awaiting_reply',
  attempt INTEGER NOT NULL DEFAULT 1,
  last_prompt_at TEXT,
  escalation_active INTEGER NOT NULL DEFAULT 0,
  escalation_level INTEGER NOT NULL DEFAULT 0,
  last_escalation_at TEXT,
  transcript TEXT,
  classification TEXT,
  medicine_taken TEXT,
  distress INTEGER NOT NULL DEFAULT 0,
  mood TEXT,
  confidence REAL,
  summary TEXT,
  keyword_hits TEXT NOT NULL DEFAULT '[]',
  classifier_error TEXT,
  model_used TEXT,
  gateway_request_id TEXT,
  gateway_fallback INTEGER,
  gateway_cost_usd REAL,
  responded_at TEXT,
  created_at TEXT NOT NULL,
  UNIQUE (elder_id, scheduled_at)
);
CREATE INDEX IF NOT EXISTS ix_checkins_elder ON checkins(elder_id);
CREATE INDEX IF NOT EXISTS ix_checkins_status ON checkins(status);
CREATE INDEX IF NOT EXISTS ix_checkins_escalation ON checkins(escalation_active);

CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  elder_id INTEGER NOT NULL REFERENCES elders(id) ON DELETE CASCADE,
  checkin_id INTEGER REFERENCES checkins(id) ON DELETE CASCADE,
  contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
  severity TEXT NOT NULL DEFAULT 'warning',
  reason TEXT NOT NULL DEFAULT 'needs_follow_up',
  message TEXT NOT NULL DEFAULT '',
  channel TEXT NOT NULL DEFAULT 'dashboard',
  delivered INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  sent_at TEXT NOT NULL,
  acknowledged_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_alerts_elder ON alerts(elder_id);
CREATE INDEX IF NOT EXISTS ix_alerts_checkin ON alerts(checkin_id);

CREATE TABLE IF NOT EXISTS summary_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  elder_id INTEGER NOT NULL REFERENCES elders(id) ON DELETE CASCADE,
  week_key TEXT NOT NULL,
  UNIQUE (elder_id, week_key)
);
