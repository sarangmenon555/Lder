const COUNT = 6;

function pick(text) {
  let h = 0;
  for (const ch of text) h = (h * 31 + ch.codePointAt(0)) >>> 0;
  return h % COUNT;
}

export default function Avatar({ name, size = "md" }) {
  const label = (name || "").trim();
  const letter = Array.from(label)[0] || "?";
  return (
    <span className={`avatar avatar-${size} av-${pick(label)}`} aria-hidden="true">
      {letter.toUpperCase()}
    </span>
  );
}
