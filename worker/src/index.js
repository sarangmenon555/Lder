import { settings } from "./config.js";
import { HttpError, json } from "./http.js";
import { route } from "./routes.js";
import { runTick } from "./checkins.js";

function makeApp(env, origin) {
  const s = settings(env);
  return { env, db: env.DB, s, origin: origin || s.publicBaseUrl || "" };
}

function corsHeaders(env, request) {
  const allowed = String(env.CORS_ORIGINS || "")
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
  const origin = request.headers.get("Origin");
  if (!origin || !allowed.includes(origin)) return {};
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    Vary: "Origin",
  };
}

export default {
  async fetch(request, env, ctx) {
    const cors = corsHeaders(env, request);
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    const url = new URL(request.url);
    const apiLike = url.pathname.startsWith("/api/") || url.pathname === "/health";
    if (!apiLike) return env.ASSETS.fetch(request);
    let response;
    try {
      response = await route(makeApp(env, url.origin), request, ctx);
    } catch (err) {
      if (err instanceof HttpError) response = json({ detail: err.detail }, err.status);
      else {
        console.error("Unhandled error", String((err && err.stack) || err));
        response = json({ detail: "Something went wrong on the server" }, 500);
      }
    }
    const out = new Response(response.body, response);
    for (const [k, v] of Object.entries(cors)) out.headers.set(k, v);
    return out;
  },

  async scheduled(event, env, ctx) {
    const app = makeApp(env, "");
    if (!app.s.enableScheduler) return;
    ctx.waitUntil(
      runTick(app).catch((err) => console.error("Tick failed", String((err && err.stack) || err))),
    );
  },
};
