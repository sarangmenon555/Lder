const BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
const TOKEN_KEY = "lder_token";

export const apiBase = BASE;

export function getToken() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  window.localStorage.removeItem(TOKEN_KEY);
}

async function request(path, { method = "GET", body, form, auth = true } = {}) {
  const headers = {};
  if (auth) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  let payload;
  if (form) {
    payload = form;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(`${BASE}/api${path}`, { method, headers, body: payload });
  } catch {
    throw new Error("Cannot reach the server. Check your connection and try again.");
  }
  if (res.status === 401 && auth) {
    clearToken();
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("Your session has ended. Sign in again.");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
      else if (Array.isArray(data.detail)) detail = data.detail.map((d) => d.msg).join("; ");
    } catch {}
    throw new Error(detail || "Something went wrong");
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  login: (password) => request("/auth/login", { method: "POST", body: { password }, auth: false }),
  elders: () => request("/elders"),
  elder: (id) => request(`/elders/${id}`),
  createElder: (body) => request("/elders", { method: "POST", body }),
  updateElder: (id, body) => request(`/elders/${id}`, { method: "PUT", body }),
  deleteElder: (id) => request(`/elders/${id}`, { method: "DELETE" }),
  checkins: (id, limit = 40) => request(`/elders/${id}/checkins?limit=${limit}`),
  summary: (id, days = 14) => request(`/elders/${id}/summary?days=${days}`),
  trigger: (id, mode) => request(`/elders/${id}/trigger-checkin`, { method: "POST", body: { mode } }),
  alerts: ({ elderId, acknowledged } = {}) => {
    const q = new URLSearchParams();
    if (elderId !== undefined) q.set("elder_id", elderId);
    if (acknowledged !== undefined) q.set("acknowledged", acknowledged);
    const qs = q.toString();
    return request(`/alerts${qs ? `?${qs}` : ""}`);
  },
  acknowledge: (id) => request(`/alerts/${id}/acknowledge`, { method: "POST" }),
  simState: (token) => request(`/simulator/${token}`, { auth: false }),
  simStart: (token) => request(`/simulator/${token}/start`, { method: "POST", auth: false }),
  simReply: (token, form) => request(`/simulator/${token}/reply`, { method: "POST", form, auth: false }),
  simOptOut: (token) => request(`/simulator/${token}/opt-out`, { method: "POST", auth: false }),
};
