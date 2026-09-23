"""Google Gemini File Search backed Provider -- the Gemini equivalent of an
OpenAI vector store (google-genai's file_search_stores resource).

Needs google-genai>=1.48 and Python 3.10+: the File Search Tool isn't in the
last google-genai release that still supports 3.9 (verified locally --
1.47.0, the newest 3.9-compatible build, has no file_search_stores attribute
on the client at all).
"""
from __future__ import annotations

import io
import time

from google import genai
from google.genai import types


class GeminiProvider:
    def __init__(self, api_key: str, embedding_model: str = "models/gemini-embedding-2"):
        self.client = genai.Client(api_key=api_key)
        self.embedding_model = embedding_model

    def get_or_create_store(self, store_id: str | None, name: str) -> str:
        if store_id:
            self.client.file_search_stores.get(name=store_id)  # raises if it doesn't exist
            return store_id
        store = self.client.file_search_stores.create(
            config=types.CreateFileSearchStoreConfig(
                display_name=name,
                embedding_model=self.embedding_model,
            )
        )
        return store.name

    def upload_article(self, store_id: str, filename: str, text: str) -> str:
        operation = self.client.file_search_stores.upload_to_file_search_store(
            file_search_store_name=store_id,
            file=io.BytesIO(text.encode("utf-8")),
            config=types.UploadToFileSearchStoreConfig(
                display_name=filename,
                mime_type="text/markdown",
            ),
        )
        operation = self._await_operation(operation)
        return operation.response.document_name

    def replace_article(self, store_id: str, old_ref: str, filename: str, text: str) -> str:
        self.remove_article(store_id, old_ref)
        return self.upload_article(store_id, filename, text)

    def remove_article(self, store_id: str, ref: str) -> None:
        try:
            self.client.file_search_stores.documents.delete(name=ref)
        except Exception:
            pass  # already deleted

    def wait_for_processing(self, store_id: str, timeout_s: int = 300) -> dict:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            store = self.client.file_search_stores.get(name=store_id)
            if store.pending_documents_count == 0:
                return self._counts(store)
            time.sleep(2)
        return self._counts(self.client.file_search_stores.get(name=store_id))

    def _await_operation(self, operation, timeout_s: int = 300):
        deadline = time.time() + timeout_s
        while not operation.done and time.time() < deadline:
            time.sleep(2)
            operation = self.client.operations.get(operation)
        return operation

    @staticmethod
    def _counts(store) -> dict:
        return {
            "completed": store.active_documents_count,
            "pending": store.pending_documents_count,
            "failed": store.failed_documents_count,
        }
