"""Common interface both AI providers implement, so main.py never branches
on which one is active -- it only talks to whatever get_provider() returns."""
from __future__ import annotations

from typing import Protocol


class Provider(Protocol):
    def get_or_create_store(self, store_id: str | None, name: str) -> str:
        """Return a store id, creating one first if store_id is falsy."""

    def upload_article(self, store_id: str, filename: str, text: str) -> str:
        """Upload one article; return an opaque ref to pass back into
        replace_article/remove_article later. Never parsed by callers."""

    def replace_article(self, store_id: str, old_ref: str, filename: str, text: str) -> str:
        """Remove the stale ref and upload the new version."""

    def remove_article(self, store_id: str, ref: str) -> None:
        """Detach and delete a previously uploaded article."""

    def wait_for_processing(self, store_id: str) -> dict:
        """Block until indexing settles; return provider-native counts for logging."""
