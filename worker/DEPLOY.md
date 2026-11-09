Deploy Lder entirely on Cloudflare (free)

One Worker serves the dashboard (static files), the API (D1 database) and the scheduler (cron trigger). There is nothing to host elsewhere.

What you need: a free Cloudflare account, Node 20 or newer, and an Otari API key.

1. Build the dashboard
   cd frontend
   npm install
   npm run build
   The build calls the API on the same address as the page, so no API URL is needed.

2. Create the database
   cd ../worker
   npm install
   npx wrangler login
   npx wrangler d1 create lder
   Copy the database_id it prints into worker/wrangler.jsonc, replacing the zeros.
   npm run migrate

3. Set the secrets (each command asks you to paste the value)
   npx wrangler secret put ADMIN_PASSWORD
   npx wrangler secret put SECRET_KEY
   npx wrangler secret put ENCRYPTION_KEY
   npx wrangler secret put OTARI_API_KEY
   npx wrangler secret put GUARDRAIL_SECRET
   npx wrangler secret put CRON_SECRET
   Use long random strings for SECRET_KEY, ENCRYPTION_KEY, GUARDRAIL_SECRET and CRON_SECRET. ADMIN_PASSWORD is what you type on the login page.
   Optional: STT_BASE_URL and STT_API_KEY (use https://api.groq.com/openai/v1 and a free Groq key if Otari does not proxy audio), EMAIL_API_URL, EMAIL_API_KEY and EMAIL_FROM (Resend or Brevo free tier) for family emails, WHATSAPP_* for WhatsApp.

4. Deploy
   npm run deploy
   Wrangler prints your address, for example https://lder.yourname.workers.dev. Open it and sign in.

5. Tell the app its own address
   In worker/wrangler.jsonc set vars PUBLIC_BASE_URL and FRONTEND_BASE_URL to that address, then run npm run deploy again. PUBLIC_BASE_URL must be https for the MCP feature to be switched on. FRONTEND_BASE_URL is used for the links inside alert emails.

6. Otari dashboard
   Follow backend/docs/OTARI.md. Use https://YOUR-ADDRESS/api/guardrail as the guardrail endpoint and your GUARDRAIL_SECRET as its credential. The model names lder-classifier, lder-summary and lder-assistant are the routing policies you create there.

The scheduler
   wrangler.jsonc has a cron trigger that runs every minute. It creates due check-ins, sends retries, escalates missed check-ins and sends the weekly summary. You can also trigger it by opening https://YOUR-ADDRESS/api/internal/tick?key=YOUR_CRON_SECRET.

Local development
   Copy .dev.vars.example to .dev.vars and fill it in.
   npm run migrate:local
   npm run dev
   Tests: npm test (unit tests, then end-to-end tests that start the Worker locally with a fake Otari).

Audio prompts
   Malayalam question audio is included. Until the other four languages have audio files, the elder's page speaks the question with the phone or browser's own voice (Tamil, Telugu, Hindi and Kannada voices exist on Android and Chrome). WhatsApp prompts for those languages are sent as text only.
   To create the real audio files, run this once on a computer with internet access, then build and deploy again:
   cd backend
   pip install -r requirements.txt
   python scripts/generate_prompts.py
   The script writes the mp3 files, copies them into frontend/public/static/prompts and updates worker/src/data/audio_manifest.json.

Free limits to know about
   Workers free: 100,000 requests a day and 10 ms of CPU per request (waiting for Otari or the database does not count). D1 free: 5 GB, 5 million row reads and 100,000 row writes a day. Check Cloudflare's pricing page for current numbers.
   If a request ever exceeds the CPU limit, Cloudflare returns an error for that request only. The Python backend in backend/ and render.yaml remain in the project as a fallback host.
