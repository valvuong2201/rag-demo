# OptiBot Mini-Clone

A small pipeline that keeps an OpenAI vector store in sync with the OptiSigns
Help Center, so an Assistant can answer support questions with cited article
URLs.

## What it does

1. **Scrape → Markdown** (`scraper.py`) — pulls articles from the Help
   Center's public Zendesk API (`/api/v2/help_center/{locale}/articles.json`),
   converts each article body to clean Markdown, and writes `articles/<slug>.md`.
   Reading the API's `body` field (not the rendered page) is what keeps
   nav/theme/ad markup out from the start.
2. **Vector store upload** (`providers/`) — uploads each Markdown file to a
   vector store via the active AI provider's API — no UI drag-and-drop.
   `AI_PROVIDER=openai` (default) or `AI_PROVIDER=gemini`, switchable by one
   env var; see AI provider, below.
3. **Delta detection** (`state.py`, `main.py`) — hashes each article's
   Markdown and keeps a `state.json` of `{slug: {content_hash, provider,
   external_ref}}`. On each run:
   - new slug → **added**
   - hash changed → old file/embedding deleted, new one uploaded → **updated**
   - hash unchanged → **skipped**
   - slug no longer on the Help Center → removed from the vector store
4. **Daily job** (`Dockerfile`, `.github/workflows/daily-sync.yml`) —
   `main.py` runs once and exits 0; a GitHub Actions cron schedule
   re-invokes the container once a day.

## AI provider

Both OpenAI and Gemini work out of the box — `providers/` defines one
`Provider` interface (`providers/base.py`) with two implementations
(`openai_provider.py`, `gemini_provider.py`); `main.py` and everything else
is written against the interface and doesn't know which one is active.
Switch with one env var:

```bash
AI_PROVIDER=openai   # needs OPENAI_API_KEY
AI_PROVIDER=gemini   # needs GEMINI_API_KEY -- free, no payment method required
                      # (get one at aistudio.google.com/apikey)
```

Each `state.json` record is tagged with the provider that created it
(`"provider": "openai" | "gemini"`), so switching providers mid-project
never tries to delete a ref the other provider owns — it just re-uploads
under the new one (a fresh store; the two aren't interchangeable mid-stream,
see `STORE_ID` resolution in `config.py`).

**Gemini specifics**: uses the Gemini API's File Search Tool
(`client.file_search_stores`), the direct equivalent of an OpenAI vector
store. Requires `google-genai>=1.48.0`, which itself requires **Python
3.10+** (verified locally: 1.47.0, the newest release that still supports
3.9, has no `file_search_stores` on the client at all). The Docker image
(`python:3.11-slim`) satisfies this already; for local dev on an older
Python, use a 3.10+ interpreter for this project's venv.

## Chunking strategy

OpenAI: the vector store's default chunking (`auto`). Gemini: File Search's
default chunker. Both are sane starting points for prose-like Markdown docs;
not overridden since Help Center articles are short, well-structured pages
rather than long unstructured text where a custom chunk size/overlap would
matter.

## Setup

```bash
cp .env.sample .env   # fill in AI_PROVIDER + that provider's API key
pip install -r requirements.txt   # needs Python 3.10+, see AI provider above
```

## Run locally

```bash
python main.py
```

First run creates a store and prints its id — copy that into `VECTOR_STORE_ID`
(OpenAI) or `GEMINI_STORE_ID` (Gemini) in `.env` so subsequent runs (and the
daily job) reuse the same store instead of creating a new one each time.

## Run via Docker

```bash
docker build -t kb-sync-bot .
docker run --rm --env-file .env \
  -e STATE_PATH=/app/data/state.json -e ARTICLES_DIR=/app/data/articles \
  -v "$PWD/data:/app/data" \
  kb-sync-bot
```

Runs once and exits `0` on success, per the assignment's contract.

**The `-v`/`data` mount matters**: `state.json` is in `.dockerignore` on
purpose (it's runtime state, not something to bake into an image), so a
plain `docker run --rm --env-file .env kb-sync-bot` with no volume starts
every container with an *empty* state and re-uploads everything as
`added=N` on every run — duplicating files in the store instead of
detecting deltas. Always mount `data/` (as above, or as the Scheduling
section's `deploy` pattern does) outside quick one-off smoke tests.

## Scheduling the daily job

Runs on **GitHub Actions** (`.github/workflows/daily-sync.yml`), on a cron
schedule, once a day at 03:00 UTC (also runnable on demand from the Actions
tab via `workflow_dispatch`).

GitHub-hosted runners are a fresh VM every run, so there's no local disk to
persist `state.json` on between invocations the way a VPS would have. The
workflow uses `actions/cache` instead: it restores the most recent run's
`data/` directory (`state.json` + `articles/`) before the container runs, and
saves a new cache entry after — giving delta detection (added/updated/
skipped) the same continuity a persistent disk would, without provisioning
one.

One-time setup:

1. Push this repo to GitHub (repo name must not contain "optisigns" — see
   Deliverables below).
2. Add the repo secrets for whichever provider `AI_PROVIDER` is set to
   (Settings → Secrets and variables → Actions), e.g. via the `gh` CLI **in
   your own terminal** (don't paste the key into a chat with an AI
   assistant):
   ```bash
   # OpenAI:
   gh secret set OPENAI_API_KEY
   gh secret set VECTOR_STORE_ID
   # Gemini instead:
   gh secret set GEMINI_API_KEY
   gh secret set GEMINI_STORE_ID
   ```
   `AI_PROVIDER` itself defaults to `openai`; to run Gemini in CI, also set
   the repo **variable** (not secret) `AI_PROVIDER=gemini` (Settings →
   Secrets and variables → Actions → Variables).
3. The workflow then runs automatically every day; trigger it manually once
   from the **Actions** tab (`Daily Sync` → `Run workflow`) to verify it end
   to end.

## Daily job logs

- **All runs / logs**: the repo's **Actions** tab → `Daily Sync` workflow —
  each run's page shows the full `added=/updated=/skipped=/removed=` line
  and vector store `file_counts` both in the raw logs and in the run's
  Summary tab.
- **Last run artifact**: each run also uploads its output as a downloadable
  artifact named `sync-log` (30-day retention), attached to that run's page.

https://github.com/valvuong2201/rag-demo/actions/workflows/daily-sync.yml

## Assistant setup (manual, one-time)

1. In the [OpenAI Playground](https://platform.openai.com/playground) (or
   Google AI Studio), create an Assistant/Agent pointed at the vector store
   created above.
2. Use this system prompt verbatim:

   ```
   You are OptiBot, the customer-support bot for OptiSigns.com.
   • Tone: helpful, factual, concise.
   • Only answer using the uploaded docs.
   • Max 5 bullet points; else link to the doc.
   • Cite up to 3 "Article URL:" lines per reply.
   ```

   (Also defined as `SYSTEM_PROMPT` in `config.py` for reference.)

## Sanity check

Asked: **"How do I add a YouTube video?"**

> OptiSigns supports streaming YouTube content using the integrated app
> feature. To display YouTube analytics or dashboards, you can use the
> YouTube Dashboard App integrated with Google Looker Studio.
>
> Article URL: https://support.optisigns.com/hc/en-us/articles/48626115821459-How-to-Use-the-YouTube-Dashboard-App
> Article URL: https://support.optisigns.com/hc/en-us/articles/29792081890323-Guide-for-Creating-Content-with-OptiSigns

Answered correctly, grounded in the uploaded docs, with real cited URLs — see
`screenshot.png` (submitted alongside this repo per the Deliverables table).

**Note on how this was run**: Google AI Studio's Playground UI does not
currently expose a way to attach an existing File Search store (only ad-hoc
file/Drive attachments for a single turn) — a real product gap, not a
shortcut taken here. Ran the identical call through the same SDK AI Studio
itself uses (`client.interactions.create(... tools=[{"type": "file_search", ...}])`)
instead. OpenAI's Playground UI does support attaching an existing vector
store directly (used earlier, then blocked by the OpenAI trial running out
of credits — see AI provider, above, for why this project runs on Gemini).

## Notes / limitations

- Neither provider's API exposes a per-file chunk count, so the job logs
  each store's own aggregate counts (OpenAI's `file_counts`, Gemini's
  `active/pending/failed_documents_count`) as the closest available signal,
  plus per-run added/updated/skipped/removed counts.
- No API keys are committed; copy `.env.sample` to `.env` locally, and pass
  the active provider's key as a runtime secret in whatever scheduler/host
  runs the container.
- The Gemini path is verified end to end against a live API key (create
  store → upload → index → delete), not just checked against the SDK's
  signatures. One real bug surfaced this way and is fixed: `File
  Search Store.pending_documents_count` is `None`, not `0`, when nothing is
  pending — a naive `== 0` check spun for the full 300s timeout on every
  call instead of returning immediately.
- Gemini's free tier rate-limits *querying* an assistant (`interactions.create`
  / `generate_content`) per model at 20 requests/day — hit this while
  sanity-checking and had to fall back across a few Flash model variants.
  This only affects asking the assistant questions; the daily sync job's
  own upload/index calls are a separate quota and unaffected.
