"""OpenAI vector-store backed Provider (API-only, no UI drag-and-drop)."""
from __future__ import annotations

import io
import time

from openai import OpenAI


class OpenAIProvider:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def get_or_create_store(self, store_id: str | None, name: str) -> str:
        if store_id:
            self.client.vector_stores.retrieve(store_id)  # raises if it doesn't exist
            return store_id
        return self.client.vector_stores.create(name=name).id

    def upload_article(self, store_id: str, filename: str, text: str) -> str:
        file_obj = self.client.files.create(
            file=(filename, io.BytesIO(text.encode("utf-8"))),
            purpose="assistants",
        )
        # A vector store file's id IS the underlying file's id in this API,
        # so one ref is enough to delete both sides later.
        vs_file = self.client.vector_stores.files.create(
            vector_store_id=store_id,
            file_id=file_obj.id,
        )
        return vs_file.id

    def replace_article(self, store_id: str, old_ref: str, filename: str, text: str) -> str:
        self.remove_article(store_id, old_ref)
        return self.upload_article(store_id, filename, text)

    def remove_article(self, store_id: str, ref: str) -> None:
        try:
            self.client.vector_stores.files.delete(ref, vector_store_id=store_id)
        except Exception:
            pass  # already detached from the store
        try:
            self.client.files.delete(ref)
        except Exception:
            pass  # already deleted

    def wait_for_processing(self, store_id: str, timeout_s: int = 300) -> dict:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            store = self.client.vector_stores.retrieve(store_id)
            if store.file_counts.in_progress == 0:
                return store.file_counts.model_dump()
            time.sleep(2)
        return self.client.vector_stores.retrieve(store_id).file_counts.model_dump()
