import LANGUAGES from "./data/languages.json" with { type: "json" };

export const DEFAULT_LANGUAGE = "ml";
export { LANGUAGES };

export function normalizeCode(code) {
  const c = String(code || "").trim().toLowerCase();
  return c in LANGUAGES ? c : DEFAULT_LANGUAGE;
}

export function get(code) {
  return LANGUAGES[normalizeCode(code)];
}
