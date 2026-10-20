import Link from "next/link";
import StatusChip from "@/components/StatusChip";
import { formatDateTime } from "@/lib/time";

const REASONS = {
  distress: "May need help",
  missed_checkin: "Missed check-in",
  needs_follow_up: "Follow-up suggested",
  medicine_missed: "Medicine not taken",
  pattern: "Several low days in a row",
  late_response: "Replied late",
};

export default function AlertList({ alerts, onAck, tz, showElder = true, empty }) {
  if (!alerts.length) {
    return <p className="empty-note">{empty || "Nothing needs attention right now."}</p>;
  }
  return (
    <ul className="alerts">
      {alerts.map((alert) => (
        <li key={alert.id} className={`alert-card alert-${alert.severity}${alert.acknowledged_at ? " alert-done" : ""}`}>
          <div className="alert-head">
            <strong className="alert-title">{REASONS[alert.reason] || alert.reason}</strong>
            <StatusChip value={alert.severity} />
          </div>
          {showElder && (
            <Link href={`/elders/${alert.elder_id}`} className="alert-elder">
              {alert.elder_name}
            </Link>
          )}
          <p className="alert-meta">
            {formatDateTime(alert.sent_at, tz)}
            {alert.contact_name ? `, sent to ${alert.contact_name}` : ""}
            {alert.channel ? ` by ${alert.channel.replace("+", " and ")}` : ""}
          </p>
          {!alert.delivered && alert.channel !== "dashboard" && (
            <p className="alert-error">Delivery did not go through. It is still shown here.</p>
          )}
          {alert.error && (
            <details>
              <summary>Why delivery failed</summary>
              <p className="alert-error">{alert.error}</p>
            </details>
          )}
          <details>
            <summary>Read the message</summary>
            <pre className="message">{alert.message}</pre>
          </details>
          {alert.acknowledged_at ? (
            <p className="alert-meta">Acknowledged {formatDateTime(alert.acknowledged_at, tz)}</p>
          ) : (
            onAck && (
              <button className="btn btn-primary btn-small" onClick={() => onAck(alert.id)}>
                I have seen this
              </button>
            )
          )}
        </li>
      ))}
    </ul>
  );
}
