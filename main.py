"""Daily sync job: re-scrape the OptiSigns Help Center, detect new/updated
articles, and upload only the delta into the OpenAI vector store.

Runs once and exits 0 -- meant to be invoked by `docker run` on a schedule
(cron / cloud scheduler), not as a long-lived process.
"""
import os
import sys
import time

from openai import OpenAI

import config
import scraper
import state as state_store
import vectorstore


def run() -> int:
    started = time.time()
    os.makedirs(config.ARTICLES_DIR, exist_ok=True)

    print(f"[sync] fetching articles from {config.HELP_CENTER_URL} ...")
    articles = scraper.fetch_articles(
        config.HELP_CENTER_URL, config.LOCALE, config.MIN_ARTICLES
    )
    print(f"[sync] fetched {len(articles)} articles")

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    vector_store_id = vectorstore.get_or_create_vector_store(
        client, config.VECTOR_STORE_ID, config.VECTOR_STORE_NAME
    )
    print(f"[sync] using vector store: {vector_store_id}")

    prior_state = state_store.load(config.STATE_PATH)
    new_state: dict[str, state_store.ArticleState] = {}

    added = updated = skipped = 0

    for article in articles:
        file_path = os.path.join(config.ARTICLES_DIR, article.filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(article.as_file_text())

        prior = prior_state.get(article.slug)

        if prior is None:
            file_id, vs_file_id = vectorstore.upload_article(
                client, vector_store_id, article.filename, article.as_file_text()
            )
            added += 1
        elif prior["content_hash"] != article.content_hash:
            file_id, vs_file_id = vectorstore.replace_article(
                client,
                vector_store_id,
                prior["openai_file_id"],
                article.filename,
                article.as_file_text(),
            )
            updated += 1
        else:
            file_id, vs_file_id = prior["openai_file_id"], prior["vector_store_file_id"]
            skipped += 1

        new_state[article.slug] = {
            "content_hash": article.content_hash,
            "updated_at": article.updated_at,
            "openai_file_id": file_id,
            "vector_store_file_id": vs_file_id,
        }

    # Articles that disappeared from the Help Center since the last run get
    # removed from the vector store too, so the assistant never cites a dead link.
    removed = 0
    for slug, prior in prior_state.items():
        if slug not in new_state:
            vectorstore.remove_article(client, vector_store_id, prior["openai_file_id"])
            removed += 1

    state_store.save(config.STATE_PATH, new_state)

    file_counts = vectorstore.wait_for_processing(client, vector_store_id)

    elapsed = time.time() - started
    print(
        f"[sync] done in {elapsed:.1f}s -- "
        f"added={added} updated={updated} skipped={skipped} removed={removed}"
    )
    print(f"[sync] vector store file_counts: {file_counts}")

    return 0


if __name__ == "__main__":
    sys.exit(run())
