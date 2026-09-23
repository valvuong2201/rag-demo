"""Persist per-article sync state so re-runs can detect new/updated/unchanged
articles and only touch the vector store for what actually changed."""
import json
import os
from typing import TypedDict


class ArticleState(TypedDict):
    content_hash: str
    updated_at: str
    provider: str  # "openai" | "gemini" -- which provider uploaded this ref
    external_ref: str  # opaque id, meaningful only to that provider


def load(path: str) -> dict[str, ArticleState]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save(path: str, state: dict[str, ArticleState]) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    os.replace(tmp_path, path)
