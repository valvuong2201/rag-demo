"""Programmatic (API-only, no UI drag-and-drop) upload of Markdown files into
an OpenAI vector store."""
from __future__ import annotations

import io

from openai import OpenAI


def get_or_create_vector_store(client: OpenAI, vector_store_id: str | None, name: str) -> str:
    if vector_store_id:
        client.vector_stores.retrieve(vector_store_id)  # raises if it doesn't exist
        return vector_store_id
    store = client.vector_stores.create(name=name)
    return store.id


def upload_article(client: OpenAI, vector_store_id: str, filename: str, text: str) -> tuple[str, str]:
    """Upload one Markdown file and attach it to the vector store.

    Returns (openai_file_id, vector_store_file_id).
    """
    file_obj = client.files.create(
        file=(filename, io.BytesIO(text.encode("utf-8"))),
        purpose="assistants",
    )
    vs_file = client.vector_stores.files.create(
        vector_store_id=vector_store_id,
        file_id=file_obj.id,
    )
    return file_obj.id, vs_file.id


def replace_article(
    client: OpenAI, vector_store_id: str, old_file_id: str, filename: str, text: str
) -> tuple[str, str]:
    """Remove the stale file/embedding and upload the new version."""
    remove_article(client, vector_store_id, old_file_id)
    return upload_article(client, vector_store_id, filename, text)


def remove_article(client: OpenAI, vector_store_id: str, file_id: str) -> None:
    try:
        client.vector_stores.files.delete(file_id, vector_store_id=vector_store_id)
    except Exception:
        pass  # already detached from the store
    try:
        client.files.delete(file_id)
    except Exception:
        pass  # already deleted


def wait_for_processing(client: OpenAI, vector_store_id: str, timeout_s: int = 300) -> dict:
    """Poll until the store finishes indexing, then return its file_counts
    (completed/failed/in_progress/total) -- the closest thing the API exposes
    to a per-run "how much got embedded" figure; OpenAI does not expose a raw
    chunk count per file."""
    import time

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        store = client.vector_stores.retrieve(vector_store_id)
        if store.file_counts.in_progress == 0:
            return store.file_counts.model_dump()
        time.sleep(2)
    store = client.vector_stores.retrieve(vector_store_id)
    return store.file_counts.model_dump()
