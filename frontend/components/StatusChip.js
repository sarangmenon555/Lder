const TONES = {
  fine: "ok",
  completed: "ok",
  unwell: "warn",
  warning: "warn",
  needs_help: "bad",
  critical: "bad",
  missed: "bad",
  confused: "info",
  awaiting_reply: "info",
  info: "info",
  unclear: "mute",
  cancelled: "mute",
};

const LABELS = {
  fine: "Doing well",
  unwell: "Unwell",
  needs_help: "Needs help",
  confused: "Confused",
  unclear: "Unclear",
  awaiting_reply: "Waiting for a reply",
  missed: "Missed",
  completed: "Replied",
  critical: "Urgent",
  warning: "Follow up",
  info: "Update",
  cancelled: "Cancelled",
};

export function toneOf(value) {
  return TONES[value] || "mute";
}

export default function StatusChip({ value, label }) {
  const tone = toneOf(value);
  return <span className={`chip chip-dot chip-${tone}`}>{label || LABELS[value] || value}</span>;
}
