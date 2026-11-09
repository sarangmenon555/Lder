Deploy for free

API on Render (free web service)

1. Push the repo. In Render, create a Blueprint from render.yaml (placed at the repo root). Set the secret env vars it asks for.
2. DATABASE_URL: Render free Postgres expires after 30 days. Create a free Postgres at neon.tech and paste its connection string.
3. Email: Render blocks SMTP. Set EMAIL_API_URL and EMAIL_API_KEY (Resend or Brevo free tier) and EMAIL_FROM.
4. Set CORS_ORIGINS and FRONTEND_BASE_URL to the Cloudflare frontend URL. Set CRON_SECRET to a long random string. ADMIN_PASSWORD, SECRET_KEY, ENCRYPTION_KEY must be set.

Frontend on Cloudflare (static assets, free)

cd frontend
NEXT_PUBLIC_API_URL=https://your-api.onrender.com npm run deploy

Links use query routes: /elder/?id=1 and /simulator/?t=TOKEN.

Cron Worker (keeps the Render service awake and runs the scheduler tick)

cd backend/deploy/cron-worker
set API_URL in wrangler.jsonc
npx wrangler secret put CRON_SECRET
npx wrangler deploy

The Worker calls /api/internal/tick every minute, which wakes the sleeping Render service and runs due check-ins.

Languages

Malayalam, Tamil, Telugu, Hindi, Kannada. Prompt audio for the four new languages is synthesized on first use, or run python scripts/generate_prompts.py with network access. Translations and keyword lists for the new languages need review by native speakers.

Tests

pip install -r requirements-dev.txt
pytest
