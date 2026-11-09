async function tick(env) {
  const base = String(env.API_URL || "").replace(/\/$/, "");
  const url = `${base}/api/internal/tick?key=${encodeURIComponent(env.CRON_SECRET || "")}`;
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(50000) });
    await response.arrayBuffer();
    if (!response.ok) console.log(`tick failed with status ${response.status}`);
  } catch (error) {
    console.log(`tick request failed: ${error}`);
  }
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(tick(env));
  },
  async fetch() {
    return new Response("lder cron worker", { status: 200 });
  },
};
