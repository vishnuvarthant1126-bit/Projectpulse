# Deploying the public demo

The public demo is **read-only**: it runs with `PUBLIC_DEMO=true`, so only the fictional
sample project is available, and uploads, edits and deletes are blocked by the API. Never deploy
without `PUBLIC_DEMO=true`, because the app has no login.

The setup has two parts:

- **API**: the FastAPI app on Render (free), built from `backend/Dockerfile` using `render.yaml`.
- **Web app**: the Next.js frontend on Vercel (free). It proxies `/api/*` to the Render API.

No API keys are needed. Suggested questions use the labelled precomputed answers, and other
questions return retrieved evidence.

## 1. Push to GitHub

1. Create an **empty** public repository at github.com named `projectpulse`, with no README,
   licence or .gitignore.
2. On Windows, double-click `publish-to-github.bat`, or run:

   ```bash
   git init -b main
   git remote add origin https://github.com/vishnuvarthant1126-bit/projectpulse.git
   git add -A && git commit -m "ProjectPulse" && git push -u origin main
   ```

The CI workflow (`.github/workflows/ci.yml`) runs the backend tests, lint and the frontend build
on every push.

## 2. Deploy the API on Render

1. Go to dashboard.render.com, then **New → Blueprint**, and connect the `projectpulse` repo.
2. Render reads `render.yaml`, which creates a free Docker web service named `projectpulse-api`
   in Singapore with `PUBLIC_DEMO=true`. Click **Apply**.
3. The first build takes a few minutes, because it installs Python packages and downloads the
   ~90 MB embedding model.
4. When it's live, open `https://<your-service>.onrender.com/api/health`. It should return
   `{"status":"ok"}`. Copy the service URL.

Free-tier notes:

- The service sleeps after 15 minutes of inactivity and takes about a minute to wake up. The web
  app shows "Waking up the demo server…" and retries automatically.
- The disk isn't persistent, which is fine here because the sample project is rebuilt at startup.
- The API uses about 350 MB of memory. This was measured locally with the sample project loaded
  and after 9 questions.

## 3. Deploy the web app on Vercel

1. Go to vercel.com, then **Add New → Project**, and import the `projectpulse` repo.
2. Set **Root Directory** to `frontend`. The framework is detected as Next.js.
3. Add these environment variables:

   | Name | Value |
   |---|---|
   | `BACKEND_URL` | `https://<your-service>.onrender.com` (no trailing slash) |
   | `NEXT_PUBLIC_REPO_URL` | `https://github.com/vishnuvarthant1126-bit/projectpulse` |

4. Click **Deploy**. Open the URL, click **Try sample project**, and ask a suggested question.

## 4. Link it

- Add the Vercel URL to the README (the "Live demo" line) and to the GitHub repo's
  **About → Website** field.
- Add a card to your portfolio that links to the demo and the source.

## Optional: live AI answers

Set `LLM_PROVIDER`, `LLM_MODEL` and `LLM_API_KEY` (plus `LLM_BASE_URL` for Gemini or other
OpenAI-compatible servers) in the Render service's **Environment** tab. For a free option, use a
Google AI Studio key with `LLM_PROVIDER=openai`,
`LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai` and
`LLM_MODEL=gemini-3.8-flash`, and set `ASK_RATE_GLOBAL_PER_MIN=10` to stay within free-tier limits. Visitors would then
use your key. The demo rate-limits questions (10 per visitor per minute and 120 per minute
overall, set with `ASK_RATE_PER_CLIENT_PER_MIN` and `ASK_RATE_GLOBAL_PER_MIN`), but you should
also set a spending limit with your provider.
