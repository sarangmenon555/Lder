import http from "node:http";

export function startFakeOtari(port) {
  const calls = [];
  const server = http.createServer((req, res) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      const raw = Buffer.concat(chunks);
      if (req.url.endsWith("/audio/transcriptions")) {
        calls.push({ url: req.url, audio: true });
        res.setHeader("Content-Type", "application/json");
        res.end(JSON.stringify({ text: "I fell down and cannot get up" }));
        return;
      }
      const body = JSON.parse(raw.toString() || "{}");
      calls.push({ url: req.url, body, headers: req.headers });
      const system = (body.messages && body.messages[0] && body.messages[0].content) || "";
      let content;
      if (system.includes("analyze short transcripts")) {
        const user = JSON.parse(body.messages[1].content);
        const t = user.transcript.toLowerCase();
        const bad = t.includes("fell") || t.includes("help");
        content = JSON.stringify({
          status: bad ? "needs_help" : "fine",
          medicine_taken: t.includes("medicine") ? "yes" : "unknown",
          distress: bad,
          mood: bad ? "low" : "good",
          confidence: 0.9,
          summary: bad ? "They reported a fall." : "They feel fine.",
        });
      } else {
        content = "Amma has answered most check-ins this week.";
      }
      res.setHeader("Content-Type", "application/json");
      res.setHeader("Otari-Model", "Qwen/Qwen3.5-35B-A3B");
      res.setHeader("Otari-Provider", "deepinfra");
      res.setHeader("Otari-Request-ID", "req_" + calls.length);
      res.end(JSON.stringify({ model: body.model, choices: [{ message: { content } }], usage: { cost_usd: 0.0001 } }));
    });
  });
  return new Promise((resolve) => server.listen(port, "127.0.0.1", () => resolve({ server, calls })));
}
