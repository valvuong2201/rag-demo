"""Daily sync job: re-scrape the OptiSigns Help Center, detect new/updated
articles, and upload only the delta into the active AI provider's vector
store (OpenAI or Gemini -- see AI_PROVIDER in config.py).

Runs once and exits 0 -- meant to be invoked by `docker run` on a schedule
(cron / cloud scheduler), not as a long-lived process.
"""
import os
import sys
import time

import config
import scraper
import state as state_store
from providers import get_provider


def run() -> int:
    started = time.time()
    os.makedirs(config.ARTICLES_DIR, exist_ok=True)

    print(f"[sync] provider: {config.AI_PROVIDER}")
    print(f"[sync] fetching articles from {config.HELP_CENTER_URL} ...")
    articles = scraper.fetch_articles(
        config.HELP_CENTER_URL, config.LOCALE, config.MIN_ARTICLES
    )
    print(f"[sync] fetched {len(articles)} articles")

    provider = get_provider(
        config.AI_PROVIDER,
        openai_api_key=config.OPENAI_API_KEY,
        gemini_api_key=config.GEMINI_API_KEY,
        gemini_embedding_model=config.GEMINI_EMBEDDING_MODEL,
    )
    store_id = provider.get_or_create_store(config.STORE_ID, config.STORE_NAME)
    print(f"[sync] using store: {store_id}")

    prior_state = state_store.load(config.STATE_PATH)
    new_state: dict[str, state_store.ArticleState] = {}

    added = updated = skipped = 0

    for article in articles:
        file_path = os.path.join(config.ARTICLES_DIR, article.filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(article.as_file_text())

        prior = prior_state.get(article.slug)

        # A record from a different provider has no ref this provider can
        # resolve -- treat it as new rather than trying to delete a
        # nonexistent remote file.
        if prior is not None and prior.get("provider") != config.AI_PROVIDER:
            prior = None

        if prior is None:
            ref = provider.upload_article(store_id, article.filename, article.as_file_text())
            added += 1
        elif prior["content_hash"] != article.content_hash:
            ref = provider.replace_article(
                store_id, prior["external_ref"], article.filename, article.as_file_text()
            )
            updated += 1
        else:
            ref = prior["external_ref"]
            skipped += 1

        new_state[article.slug] = {
            "content_hash": article.content_hash,
            "updated_at": article.updated_at,
            "provider": config.AI_PROVIDER,
            "external_ref": ref,
        }

    # Articles that disappeared from the Help Center since the last run get
    # removed from the store too, so the assistant never cites a dead link.
    removed = 0
    for slug, prior in prior_state.items():
        if slug not in new_state and prior.get("provider") == config.AI_PROVIDER:
            provider.remove_article(store_id, prior["external_ref"])
            removed += 1

    state_store.save(config.STATE_PATH, new_state)

    counts = provider.wait_for_processing(store_id)

    elapsed = time.time() - started
    print(
        f"[sync] done in {elapsed:.1f}s -- "
        f"added={added} updated={updated} skipped={skipped} removed={removed}"
    )
    print(f"[sync] store counts: {counts}")

    return 0


if __name__ == "__main__":
    sys.exit(run())
