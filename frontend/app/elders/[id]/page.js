"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import Shell from "@/components/Shell";
import AlertList from "@/components/AlertList";
import CheckInList from "@/components/CheckInList";
import AdherenceBars from "@/components/AdherenceBars";
import Avatar from "@/components/Avatar";
import Ring from "@/components/Ring";
import StatusChip from "@/components/StatusChip";
import { useTz } from "@/components/Providers";
import { api } from "@/lib/api";
import { localNow, zoneName } from "@/lib/time";

export default function ElderPage() {
  const { id } = useParams();
  const router = useRouter();
  const { tz } = useTz();
  const [elder, setElder] = useState(null);
  const [summary, setSummary] = useState(null);
  const [checkins, setCheckins] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [e, s, c, a] = await Promise.all([
        api.elder(id),
        api.summary(id, 14),
        api.checkins(id, 40),
        api.alerts({ elderId: id }),
      ]);
      setElder(e);
      setSummary(s);
      setCheckins(c);
      setAlerts(a);
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }, [id]);

  useEffect(() => {
    load();
    const timer = setInterval(load, 20000);
    return () => clearInterval(timer);
  }, [load]);

  const trigger = async (mode) => {
    setBusy(true);
    setNotice("");
    try {
      await api.trigger(id, mode);
      setNotice(
        mode === "missed"
          ? "A missed check-in was recorded and the first contact was alerted."
          : "A check-in was started. Open their link to answer it."
      );
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const acknowledge = async (alertId) => {
    await api.acknowledge(alertId);
    load();
  };

  const copyLink = async () => {
    const link = `${window.location.origin}/simulator/${elder.access_token}`;
    try {
      await navigator.clipboard.writeText(link);
      setNotice("Their link was copied. Send it to them, or open it yourself to try it.");
    } catch {
      setNotice(link);
    }
  };

  const remove = async () => {
    if (!window.confirm(`Delete ${elder.name} and every check-in, transcript and alert? This cannot be undone.`)) return;
    await api.deleteElder(id);
    router.replace("/");
  };

  if (!elder) {
    return (
      <Shell>
        {error ? <p className="error" role="alert">{error}</p> : <p className="empty-note">Loading</p>}
      </Shell>
    );
  }

  const latest = checkins[0];
  const open = alerts.filter((a) => !a.acknowledged_at && a.severity !== "info");
  const recent = alerts.slice(0, 8);

  return (
    <Shell>
      <section className="banner card">
        <Avatar name={elder.name} size="lg" />
        <div className="banner-main">
          <h1>{elder.name}</h1>
          <p className="banner-line">
            It is {localNow(elder.timezone)} there ({zoneName(elder.timezone)}), and {localNow(tz)} for you ({zoneName(tz)}).
          </p>
          <div className="chips">
            {latest && <StatusChip value={latest.classification || latest.status} />}
            {!elder.consent_at && <span className="chip chip-warn">Consent needed</span>}
            {!elder.active && <span className="chip chip-mute">Paused</span>}
            <span className="chip chip-mute">
              Checks in at {elder.check_in_times.length ? elder.check_in_times.join(" and ") : "no set times"}
            </span>
          </div>
        </div>
        <div className="btn-row">
          <Link href={`/elders/${elder.id}/edit`} className="btn btn-quiet">
            Edit
          </Link>
          <button className="btn btn-quiet" onClick={copyLink}>
            Copy their link
          </button>
        </div>
      </section>

      {error && <p className="error" role="alert">{error}</p>}
      {notice && <p className="notice" role="status">{notice}</p>}
      {!elder.consent_at && (
        <p className="notice">Consent has not been recorded, so check-ins are off. Choose Edit to record it.</p>
      )}

      <section className="try card">
        <div>
          <h2>Try it now</h2>
          <p className="hint">
            Start a check-in sends today&apos;s question straight away. A missed check-in skips the waiting and alerts the first
            contact, so you can see the whole alert path in a minute.
          </p>
        </div>
        <div className="btn-row">
          <button className="btn btn-primary" disabled={busy || !elder.consent_at} onClick={() => trigger("normal")}>
            Start a check-in
          </button>
          <button className="btn btn-quiet" disabled={busy || !elder.consent_at} onClick={() => trigger("missed")}>
            Record a missed check-in
          </button>
        </div>
      </section>

      {summary && (
        <section className="vitals card" aria-label="The last two weeks in numbers">
          <Ring value={summary.response_rate} label="Check-ins answered" size={104} />
          <Ring value={summary.adherence_pct} label="Doses taken" size={104} />
          <div className="vital">
            <span className="vital-num">{summary.missed}</span>
            <span className="vital-label">missed check-ins</span>
          </div>
          <div className="vital">
            <span className="vital-num">{summary.alerts_total}</span>
            <span className="vital-label">alerts raised, {summary.critical_alerts} urgent</span>
          </div>
        </section>
      )}

      {summary && (
        <section className="card block">
          <h2>The last two weeks</h2>
          <AdherenceBars daily={summary.daily} />
        </section>
      )}

      <div className="split">
        <section className="card block">
          <h2>Check-ins</h2>
          <CheckInList items={checkins} tz={tz} />
        </section>
        <aside className="stack">
          <section className="card block">
            <h2>Open alerts</h2>
            <AlertList alerts={open} onAck={acknowledge} tz={tz} showElder={false} empty="No open alerts." />
          </section>
          <section className="card block">
            <h2>Recent alerts</h2>
            <AlertList alerts={recent} tz={tz} showElder={false} empty="No alerts have been sent yet." />
          </section>
          <section className="card block">
            <h2>Who is told</h2>
            <ul className="plain">
              {elder.contacts.length === 0 && <li className="hint">No contacts yet. Choose Edit to add family.</li>}
              {elder.contacts.map((c) => (
                <li key={c.id} className="contact-line">
                  <Avatar name={c.name} size="sm" />
                  <span>
                    <strong>{c.name}</strong>
                    <span className="hint">
                      {" "}
                      priority {c.priority}, {c.channel === "dashboard" ? "dashboard only" : c.channel === "both" ? "email and WhatsApp" : c.channel}, {zoneName(c.timezone)}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
            {elder.medicines.length > 0 && (
              <>
                <h3>Medicines</h3>
                <ul className="plain">
                  {elder.medicines.map((m) => (
                    <li key={m.id}>
                      {m.name} <span className="hint">at {m.time_of_day}</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </section>
          <section className="card block danger-zone">
            <h2>Their data</h2>
            <p className="hint">Deleting removes this person with every check-in, transcript and alert.</p>
            <button className="btn btn-danger btn-small" onClick={remove}>
              Delete this person and all their data
            </button>
          </section>
        </aside>
      </div>
    </Shell>
  );
}
