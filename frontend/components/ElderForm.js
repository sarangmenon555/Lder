"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { ZONES } from "@/lib/time";

const CHANNELS = [
  { value: "dashboard", label: "Dashboard only" },
  { value: "email", label: "Email" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "both", label: "Email and WhatsApp" },
];

const blankContact = (priority) => ({
  id: null,
  name: "",
  email: "",
  phone: "",
  channel: "dashboard",
  priority,
  timezone: "Asia/Dubai",
});

const blankMedicine = () => ({ id: null, name: "", time_of_day: "08:00" });

function initial(elder) {
  if (!elder) {
    return {
      name: "",
      phone: "",
      timezone: "Asia/Kolkata",
      times: ["08:30", "19:00"],
      consent: false,
      active: true,
      contacts: [blankContact(1)],
      medicines: [],
    };
  }
  return {
    name: elder.name,
    phone: elder.phone,
    timezone: elder.timezone,
    times: elder.check_in_times.length ? elder.check_in_times : ["08:30"],
    consent: elder.consent_at !== null,
    active: elder.active,
    contacts: elder.contacts.map((c) => ({ ...c })),
    medicines: elder.medicines.map((m) => ({ ...m })),
  };
}

function ZoneSelect({ value, onChange }) {
  const zones = ZONES.includes(value) ? ZONES : [value, ...ZONES];
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      {zones.map((z) => (
        <option key={z} value={z}>
          {z.replace("_", " ")}
        </option>
      ))}
    </select>
  );
}

export default function ElderForm({ elder }) {
  const router = useRouter();
  const [form, setForm] = useState(() => initial(elder));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));
  const setContact = (i, patch) =>
    set({ contacts: form.contacts.map((c, idx) => (idx === i ? { ...c, ...patch } : c)) });
  const setMedicine = (i, patch) =>
    set({ medicines: form.medicines.map((m, idx) => (idx === i ? { ...m, ...patch } : m)) });
  const setTime = (i, value) => set({ times: form.times.map((t, idx) => (idx === i ? value : t)) });

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    if (!form.name.trim()) {
      setError("Enter the person's name.");
      return;
    }
    const payload = {
      name: form.name.trim(),
      phone: form.phone.replace(/\D/g, ""),
      timezone: form.timezone,
      check_in_times: form.times.filter(Boolean),
      consent: form.consent,
      active: form.active,
      contacts: form.contacts
        .filter((c) => c.name.trim())
        .map((c) => ({ ...c, name: c.name.trim(), email: c.email.trim(), priority: Number(c.priority) || 1 })),
      medicines: form.medicines.filter((m) => m.name.trim()).map((m) => ({ ...m, name: m.name.trim() })),
    };
    setBusy(true);
    try {
      const saved = elder ? await api.updateElder(elder.id, payload) : await api.createElder(payload);
      router.push(`/elders/${saved.id}`);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="form">
      <section className="form-section card">
        <h2>Who are we checking in on?</h2>
        <div className="field-grid">
          <label className="field">
            <span>Name</span>
            <input value={form.name} onChange={(e) => set({ name: e.target.value })} required />
          </label>
          <label className="field">
            <span>Their time zone</span>
            <ZoneSelect value={form.timezone} onChange={(v) => set({ timezone: v })} />
          </label>
          <label className="field field-wide">
            <span>WhatsApp number with country code</span>
            <input
              inputMode="numeric"
              placeholder="919876543210"
              value={form.phone}
              onChange={(e) => set({ phone: e.target.value })}
            />
            <small className="hint">Leave this empty to use the web link instead of WhatsApp.</small>
          </label>
        </div>
      </section>

      <section className="form-section card">
        <h2>When should we ask, and what do they take?</h2>
        <h3>Check-in times</h3>
        <p className="hint">In their own local time.</p>
        <div className="repeat">
          {form.times.map((t, i) => (
            <div key={i} className="repeat-row">
              <input type="time" value={t} onChange={(e) => setTime(i, e.target.value)} required />
              <button
                type="button"
                className="btn btn-quiet btn-small"
                onClick={() => set({ times: form.times.filter((_, idx) => idx !== i) })}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
        {form.times.length < 6 && (
          <button type="button" className="btn btn-quiet" onClick={() => set({ times: [...form.times, "13:00"] })}>
            Add another time
          </button>
        )}

        <h3>Medicines</h3>
        <p className="hint">Shown with the question when a dose is due around that time.</p>
        <div className="repeat">
          {form.medicines.map((m, i) => (
            <div key={i} className="repeat-row">
              <input
                placeholder="Medicine name"
                value={m.name}
                onChange={(e) => setMedicine(i, { name: e.target.value })}
              />
              <input type="time" value={m.time_of_day} onChange={(e) => setMedicine(i, { time_of_day: e.target.value })} />
              <button
                type="button"
                className="btn btn-quiet btn-small"
                onClick={() => set({ medicines: form.medicines.filter((_, idx) => idx !== i) })}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
        <button type="button" className="btn btn-quiet" onClick={() => set({ medicines: [...form.medicines, blankMedicine()] })}>
          Add a medicine
        </button>
      </section>

      <section className="form-section card">
        <h2>Who should be told?</h2>
        <p className="hint">
          The lowest priority number is told first. If nobody acknowledges a missed check-in, the next person is told.
        </p>
        <div className="repeat">
          {form.contacts.map((c, i) => (
            <fieldset key={i} className="contact-card">
              <legend>Contact {i + 1}</legend>
              <div className="field-grid">
                <label className="field">
                  <span>Name</span>
                  <input value={c.name} onChange={(e) => setContact(i, { name: e.target.value })} />
                </label>
                <label className="field">
                  <span>Priority</span>
                  <input
                    type="number"
                    min="1"
                    max="20"
                    value={c.priority}
                    onChange={(e) => setContact(i, { priority: e.target.value })}
                  />
                </label>
                <label className="field">
                  <span>Email</span>
                  <input type="email" value={c.email} onChange={(e) => setContact(i, { email: e.target.value })} />
                </label>
                <label className="field">
                  <span>WhatsApp number</span>
                  <input inputMode="numeric" value={c.phone} onChange={(e) => setContact(i, { phone: e.target.value })} />
                </label>
                <label className="field">
                  <span>Tell them by</span>
                  <select value={c.channel} onChange={(e) => setContact(i, { channel: e.target.value })}>
                    {CHANNELS.map((ch) => (
                      <option key={ch.value} value={ch.value}>
                        {ch.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span>Their time zone</span>
                  <ZoneSelect value={c.timezone} onChange={(v) => setContact(i, { timezone: v })} />
                </label>
              </div>
              {c.channel !== "dashboard" && (
                <p className="hint">Email and WhatsApp only work once they are set up on the server. Alerts always appear on the dashboard too.</p>
              )}
              <button
                type="button"
                className="btn btn-quiet btn-small"
                onClick={() => set({ contacts: form.contacts.filter((_, idx) => idx !== i) })}
              >
                Remove this contact
              </button>
            </fieldset>
          ))}
        </div>
        <button
          type="button"
          className="btn btn-quiet"
          onClick={() => set({ contacts: [...form.contacts, blankContact(form.contacts.length + 1)] })}
        >
          Add a contact
        </button>
      </section>

      <section className="form-section card">
        <h2>Their consent</h2>
        <label className="check">
          <input type="checkbox" checked={form.consent} onChange={(e) => set({ consent: e.target.checked })} />
          <span>
            {form.name || "This person"} has agreed to receive daily check-ins, and to have their replies shared with the
            contacts above. They can stop at any time by replying STOP or using the link on their page.
          </span>
        </label>
        {elder && (
          <label className="check">
            <input type="checkbox" checked={form.active} onChange={(e) => set({ active: e.target.checked })} />
            <span>Check-ins are switched on</span>
          </label>
        )}
        <p className="hint">Check-ins do not start until consent is recorded.</p>
      </section>

      {error && <p className="error" role="alert">{error}</p>}
      <div className="form-actions">
        <button className="btn btn-primary" disabled={busy}>
          {busy ? "Saving" : elder ? "Save changes" : "Add person"}
        </button>
        <button type="button" className="btn btn-quiet" onClick={() => router.back()}>
          Cancel
        </button>
      </div>
    </form>
  );
}
