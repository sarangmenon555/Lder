import StatusChip, { toneOf } from "@/components/StatusChip";
import { formatDateTime } from "@/lib/time";

const MEDICINE = { yes: "Medicine taken", no: "Medicine not taken" };

export default function CheckInList({ items, tz }) {
  if (!items.length) {
    return (
      <p className="empty-note">
        No check-ins yet. Start one with the buttons above, or wait for the next scheduled time.
      </p>
    );
  }
  return (
    <ol className="timeline">
      {items.map((item) => {
        const tone = toneOf(item.classification || item.status);
        return (
          <li key={item.id} className={`tl-item tl-${tone}`}>
            <div className="tl-time">{formatDateTime(item.scheduled_at, tz)}</div>
            <div className="chips">
              <StatusChip value={item.status} />
              {item.classification && <StatusChip value={item.classification} />}
              {MEDICINE[item.medicine_taken] && (
                <span className={`chip ${item.medicine_taken === "yes" ? "chip-ok" : "chip-warn"}`}>
                  {MEDICINE[item.medicine_taken]}
                </span>
              )}
              {item.attempt > 1 && <span className="chip chip-mute">Asked {item.attempt} times</span>}
            </div>
            {item.summary && <p className="tl-summary">{item.summary}</p>}
            {item.transcript && (
              <details>
                <summary>What they said</summary>
                <p lang="ml" className="transcript">
                  {item.transcript}
                </p>
                {item.confidence !== null && item.confidence !== undefined && (
                  <p className="hint">Confidence {Math.round(item.confidence * 100)} percent</p>
                )}
                {item.classifier_error && (
                  <p className="hint">Automatic analysis was unavailable: {item.classifier_error}</p>
                )}
              </details>
            )}
          </li>
        );
      })}
    </ol>
  );
}
