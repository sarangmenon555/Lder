import lexicon from "./data/lexicon.json" with { type: "json" };

const CHILLU = {
  "ൺ": "ണ്",
  "ൻ": "ന്",
  "ർ": "ര്",
  "ൽ": "ല്",
  "ൾ": "ള്",
  "ൿ": "ക്",
};
const CHILLU_RE = /[ൺ-ൿ]/g;
const DROP_RE = /[\p{P}\p{Z}\p{S}\p{C}]/gu;
const NEGATION_WINDOW = 14;
const STRICT_GAP = 3;

export function normalize(text) {
  return String(text || "")
    .normalize("NFC")
    .toLowerCase()
    .replace(CHILLU_RE, (c) => CHILLU[c])
    .replace(DROP_RE, "");
}

const NEGATION = lexicon.negation;
const IGNORE = lexicon.ignore;
const FILLERS = lexicon.fillers;
const MEDICINE = lexicon.medicine;

function negated(squashed, end) {
  const window = squashed.slice(end, end + NEGATION_WINDOW);
  return NEGATION.some((token) => window.includes(token));
}

function negatedStrict(squashed, end) {
  let rest = squashed.slice(end);
  for (const filler of FILLERS) {
    if (rest.startsWith(filler)) {
      rest = rest.slice(filler.length);
      break;
    }
  }
  for (const token of NEGATION) {
    const position = rest.indexOf(token);
    if (position >= 0 && position <= STRICT_GAP) return true;
  }
  return false;
}

function carriesNegation(word) {
  return NEGATION.some((token) => word.includes(token));
}

function matches(squashed, words, strict) {
  const test = strict ? negatedStrict : negated;
  for (const word of words) {
    const self = carriesNegation(word);
    let start = 0;
    for (;;) {
      const index = squashed.indexOf(word, start);
      if (index < 0) break;
      if (self || !test(squashed, index + word.length)) return true;
      start = index + 1;
    }
  }
  return false;
}

function scan(squashed, table, strict = false) {
  return Object.entries(table)
    .filter(([, words]) => matches(squashed, words, strict))
    .map(([category]) => category);
}

function medicine(squashed) {
  if (!MEDICINE.mention.some((t) => squashed.includes(t))) return "unknown";
  if (MEDICINE.no.some((t) => squashed.includes(t))) return "no";
  if (MEDICINE.yes.some((t) => squashed.includes(t))) return "yes";
  return "unknown";
}

export function analyze(text) {
  let squashed = normalize(text);
  for (const phrase of IGNORE) squashed = squashed.split(phrase).join("");
  const critical = scan(squashed, lexicon.critical, true);
  const concern = scan(squashed, lexicon.concern);
  const mild = scan(squashed, lexicon.mild);
  return { critical, concern, mild, medicine: medicine(squashed), hits: [...critical, ...concern, ...mild] };
}
