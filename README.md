# College Compass

## Setup

1. **Anthropic API key** (for the two Claude calls): sign up at
   https://console.anthropic.com, create an API key under "API Keys". A card is required to
   activate the account, but usage here is two short calls per request — trial credit covers
   a demo many times over.
2. **College Scorecard API key** (build-time only, to fetch real school data — no card
   required): sign up at https://collegescorecard.ed.gov/data/api-documentation/, a free key
   is emailed immediately.
3. Set environment variables:
   - `ANTHROPIC_API_KEY` — required at runtime.
   - `COLLEGE_SCORECARD_API_KEY` — required only when building the Docker image / running
     `refresh_data.py` (not needed at runtime — the app reads the local `scorecard.sqlite`
     built during that step).

## Run locally

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
COLLEGE_SCORECARD_API_KEY=<key> python -m scripts.refresh_data
ANTHROPIC_API_KEY=<key> uvicorn app.main:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

## Deploy (Render, free tier)

1. Push this repo to GitHub.
2. In Render, create a new Web Service, "Docker" runtime, point it at the repo.
3. Set the build-time env var `COLLEGE_SCORECARD_API_KEY` (Render supports build args for
   Docker builds) and the runtime env var `ANTHROPIC_API_KEY`.
4. Deploy. Render builds the Dockerfile (which fetches Scorecard data and bakes
   `scorecard.sqlite` into the image) and serves both the frontend and API from one URL.

To refresh the underlying Scorecard data later (e.g. next admissions cycle), trigger a new
deploy — the build step re-runs `refresh_data.py` against the then-current API.

### Known limitation: `COLLEGE_SCORECARD_API_KEY` persists in image layers

The Dockerfile passes the key in via a build `ARG` and then an `ENV`, which bakes it into
the built image's layer metadata — anyone who can pull the image can read it back with
`docker history` or `docker inspect`. The real risk is low: this is a free, rate-limited key
for a public government dataset, not a payment or production credential, and it is not
needed at runtime at all. Rotating it is a one-minute request at
https://collegescorecard.ed.gov/data/api-documentation/.

The clean fix is a BuildKit secret mount (`RUN --mount=type=secret,id=scorecard ...`), which
keeps the value out of every layer. It is not implemented here because it could not be
verified against a real Docker build in this environment; treat it as the intended follow-up
if the image is ever published anywhere non-private.
