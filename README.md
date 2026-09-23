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
2. **Vector store upload** (`vectorstore.py`) — uploads each Markdown file to
   OpenAI via `client.files.create` and attaches it to a vector store via
   `client.vector_stores.files.create`. All API calls, no UI drag-and-drop.
3. **Delta detection** (`state.py`, `main.py`) — hashes each article's
   Markdown and keeps a `state.json` of `{slug: {content_hash, openai_file_id,
   vector_store_file_id}}`. On each run:
   - new slug → **added**
   - hash changed → old file/embedding deleted, new one uploaded → **updated**
   - hash unchanged → **skipped**
   - slug no longer on the Help Center → removed from the vector store
4. **Daily job** (`Dockerfile`, `.github/workflows/daily-sync.yml`) —
   `main.py` runs once and exits 0; a GitHub Actions cron schedule
   re-invokes the container once a day.

## Chunking strategy

Uses the vector store's default chunking (`auto`), which is OpenAI's
recommended starting point for prose-like Markdown docs. Not overridden here
since the Help Center articles are short, well-structured pages rather than
long unstructured text where a custom `max_chunk_size_tokens` /
`chunk_overlap_tokens` would matter.

## Setup

```bash
cp .env.sample .env   # fill in OPENAI_API_KEY
pip install -r requirements.txt
```

## Run locally

```bash
python main.py
```

First run creates a vector store and prints its id — copy that into
`VECTOR_STORE_ID` in `.env` so subsequent runs (and the daily job) reuse the
same store instead of creating a new one each time.

## Run via Docker

```bash
docker build -t kb-sync-bot .
docker run --rm -e OPENAI_API_KEY=sk-... -e VECTOR_STORE_ID=vs_... kb-sync-bot
```

Runs once and exits `0` on success, per the assignment's contract.

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
2. Add two repo secrets (Settings → Secrets and variables → Actions), e.g.
   via the `gh` CLI **in your own terminal** (don't paste the key into a
   chat with an AI assistant):
   ```bash
   gh secret set OPENAI_API_KEY
   gh secret set VECTOR_STORE_ID
   ```
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

<!-- TODO: paste the actual repo's Actions URL here once pushed, e.g.
https://github.com/<you>/<repo>/actions/workflows/daily-sync.yml -->

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

<!-- TODO: ask the assistant "How do I add a YouTube video?" in the
Playground and attach a screenshot here showing a correct, cited answer. -->

## Notes / limitations

- The OpenAI API does not expose a per-file chunk count, so the job logs the
  vector store's `file_counts` (completed/failed/in_progress/total) as the
  closest available signal, plus per-run added/updated/skipped/removed
  counts.
- No API keys are committed; copy `.env.sample` to `.env` locally, and pass
  `OPENAI_API_KEY` as a runtime secret in whatever scheduler/host runs the
  container.
