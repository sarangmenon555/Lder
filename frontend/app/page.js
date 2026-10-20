"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import Shell from "@/components/Shell";
import StatusChip from "@/components/StatusChip";
import AlertList from "@/components/AlertList";
import Avatar from "@/components/Avatar";
import Ring from "@/components/Ring";
import { useTz } from "@/components/Providers";
import { api } from "@/lib/api";
import { formatDateTime, localNow, zoneName } from "@/lib/time";

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

function toneFor(elder) {
  if (elder.open_alerts > 0) return "bad";
  const latest = elder.latest_checkin;
  if (!latest) return "mute";
  if (latest.status === "missed" || latest.classification === "needs_help") return "bad";
  if (["unwell", "confused", "unclear"].includes(latest.classification)) return "warn";
  if (latest.status === "awaiting_reply") return "info";
  return "ok";
}

function PersonCard({ elder, tz }) {
  const latest = elder.latest_checkin;
  return (
    <li>
      <Link href={`/elders/${elder.id}`} className={`person-card tone-${toneFor(elder)}`}>
        <Avatar name={elder.name} />
        <div className="pc-main">
          <span className="pc-name">{elder.name}</span>
          <span className="pc-sub">
            {localNow(elder.timezone)} there, {zoneName(elder.timezone)}
          </span>
          <div className="pc-status">
            {latest ? (
              <>
                <StatusChip value={latest.classification || latest.status} />
                <span className="pc-sub">{formatDateTime(latest.scheduled_at, tz)}</span>
              </>
            ) : (
              <span className="pc-sub">No check-ins yet</span>
            )}
          </div>
          <div className="pc-flags">
            {elder.open_alerts > 0 && (
              <span className="chip chip-bad">
                {elder.open_alerts} open {elder.open_alerts === 1 ? "alert" : "alerts"}
              </span>
            )}
            {!elder.consent_at && <span className="chip chip-warn">Consent needed</span>}
            {!elder.active && <span className="chip chip-mute">Paused</span>}
          </div>
        </div>
        <Ring value={elder.adherence_7d} label="Medicine, 7 days" size={78} />
      </Link>
    </li>
  );
}

export default function Dashboard() {
  const { tz } = useTz();
  const [elders, setElders] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [e, a] = await Promise.all([api.elders(), api.alerts({ acknowledged: false })]);
      setElders(e);
      setAlerts(a);
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 20000);
    return () => clearInterval(id);
  }, [load]);

  const acknowledge = async (id) => {
    await api.acknowledge(id);
    load();
  };

  const people = elders || [];
  const waiting = people.filter((e) => e.latest_checkin && e.latest_checkin.status === "awaiting_reply").length;
  const doingWell = people.filter((e) => e.latest_checkin && e.latest_checkin.classification === "fine").length;

  let headline = "Let us add the first person";
  let lede = "Add a parent or grandparent and Lder will ask how they are every day, in Malayalam.";
  if (elders && elders.length > 0) {
    if (alerts.length > 0) {
      headline = alerts.length === 1 ? "One thing needs your attention" : `${alerts.length} things need your attention`;
      lede = "Open the alerts on the right to see what was said and who has been told.";
    } else {
      headline = "Everyone is doing well";
      lede = "No open alerts. The next check-ins will arrive on their own.";
    }
  }

  return (
    <Shell>
      <section className="hero">
        <p className="hero-hello">{greeting()}</p>
        <h1>{headline}</h1>
        <p className="hero-lede">{lede}</p>
        <div className="btn-row">
          <Link href="/elders/new" className="btn btn-gold">
            Add a person
          </Link>
        </div>
      </section>

      {error && <p className="error" role="alert">{error}</p>}

      {elders && elders.length > 0 && (
        <section className="tiles" aria-label="Today at a glance">
          <div className="tile">
            <span className="tile-num">{elders.length}</span>
            <span className="tile-label">{elders.length === 1 ? "person looked after" : "people looked after"}</span>
          </div>
          <div className={`tile ${alerts.length ? "tile-bad" : "tile-ok"}`}>
            <span className="tile-num">{alerts.length}</span>
            <span className="tile-label">open {alerts.length === 1 ? "alert" : "alerts"}</span>
          </div>
          <div className="tile tile-info">
            <span className="tile-num">{waiting}</span>
            <span className="tile-label">waiting for a reply</span>
          </div>
          <div className="tile tile-ok">
            <span className="tile-num">{doingWell}</span>
            <span className="tile-label">replied that all is well</span>
          </div>
        </section>
      )}

      <div className="dash">
        <section>
          <h2>The people you look after</h2>
          {elders === null ? (
            <p className="empty-note">Loading</p>
          ) : elders.length === 0 ? (
            <div className="welcome card">
              <h3>How it works</h3>
              <ol className="how">
                <li>
                  <strong>Add a person.</strong> Their name, their check-in times and the family who should be told.
                </li>
                <li>
                  <strong>Record their consent.</strong> Check-ins only start once they have agreed.
                </li>
                <li>
                  <strong>Send them their link.</strong> They listen to a question in Malayalam and answer by voice.
                </li>
              </ol>
              <Link href="/elders/new" className="btn btn-primary">
                Add the first person
              </Link>
            </div>
          ) : (
            <ul className="people">
              {elders.map((elder) => (
                <PersonCard key={elder.id} elder={elder} tz={tz} />
              ))}
            </ul>
          )}
        </section>
        <aside className="attention card">
          <h2>Needs attention</h2>
          <AlertList alerts={alerts} onAck={acknowledge} tz={tz} empty="Nothing needs attention. All quiet." />
        </aside>
      </div>
    </Shell>
  );
}
