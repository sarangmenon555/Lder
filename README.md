Lder: daily voice check-ins for elderly parents

worker/     Cloudflare Worker (JavaScript, D1 database, cron). The main deployment. See worker/DEPLOY.md.
frontend/   Next.js dashboard and the elder's simulator page, built to static files and served by the Worker.
backend/    The original Python (FastAPI) version with the same features. Kept as a fallback host with render.yaml.

Otari features used: routing and fallbacks (three named policies), MCP (family questions), several open-weight models in distinct roles, guardrails, per-user budgets. Setup steps for the Otari dashboard are in backend/docs/OTARI.md.
