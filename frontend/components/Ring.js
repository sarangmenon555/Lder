function autoTone(pct) {
  if (pct >= 80) return "ok";
  if (pct >= 50) return "warn";
  return "bad";
}

export default function Ring({ value, label, tone = "auto", size = 92 }) {
  const stroke = 9;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const has = value !== null && value !== undefined;
  const pct = has ? Math.max(0, Math.min(100, value)) : 0;
  const color = tone === "auto" ? autoTone(pct) : tone;
  const centre = size / 2;
  return (
    <div className="ring">
      <div className="ring-dial" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          role="img"
          aria-label={has ? `${label}: ${pct} percent` : `${label}: no data yet`}
        >
          <circle className="ring-track" cx={centre} cy={centre} r={radius} strokeWidth={stroke} fill="none" />
          {has && pct > 0 && (
            <circle
              className={`ring-fill ring-${color}`}
              cx={centre}
              cy={centre}
              r={radius}
              strokeWidth={stroke}
              fill="none"
              strokeLinecap="round"
              strokeDasharray={`${(pct / 100) * circumference} ${circumference}`}
              transform={`rotate(-90 ${centre} ${centre})`}
            />
          )}
        </svg>
        <span className="ring-value">{has ? `${pct}%` : "none"}</span>
      </div>
      <span className="ring-label">{label}</span>
    </div>
  );
}
