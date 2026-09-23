"""Pull articles from the OptiSigns Zendesk Help Center and normalize to Markdown.

Zendesk Guide exposes a public JSON API on the help-center domain itself, so we
read structured article data (title, HTML body, url, updated_at) directly
instead of scraping rendered pages -- this sidesteps nav/ad/theme markup
entirely rather than trying to strip it back out.
"""
import hashlib
import re
from dataclasses import dataclass

import requests
from markdownify import markdownify

ARTICLES_ENDPOINT = "{base}/api/v2/help_center/{locale}/articles.json"
PAGE_SIZE = 100


@dataclass
class Article:
    id: int
    slug: str
    title: str
    url: str
    updated_at: str
    markdown: str

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.markdown.encode("utf-8")).hexdigest()

    @property
    def filename(self) -> str:
        return f"{self.slug}.md"

    def as_file_text(self) -> str:
        front_matter = (
            "---\n"
            f"title: {self.title!r}\n"
            f"source_url: {self.url}\n"
            f"updated_at: {self.updated_at}\n"
            "---\n\n"
        )
        return front_matter + self.markdown


def slugify(title: str, article_id: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return f"{slug}-{article_id}"


def html_to_markdown(html: str) -> str:
    md = markdownify(html or "", heading_style="ATX", bullets="-")
    # Collapse the runs of blank lines markdownify tends to leave behind.
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    return md


def fetch_articles(base_url: str, locale: str, min_articles: int) -> list[Article]:
    """Page through the Help Center API until we've pulled at least
    ``min_articles`` published articles (or the API runs out of pages)."""
    articles: list[Article] = []
    url = ARTICLES_ENDPOINT.format(base=base_url.rstrip("/"), locale=locale)
    params = {"per_page": PAGE_SIZE}

    while url:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        params = None  # next_page already carries the query string

        for raw in payload.get("articles", []):
            if raw.get("draft"):
                continue
            markdown = html_to_markdown(raw.get("body", ""))
            articles.append(
                Article(
                    id=raw["id"],
                    slug=slugify(raw["title"], raw["id"]),
                    title=raw["title"],
                    url=raw["html_url"],
                    updated_at=raw["updated_at"],
                    markdown=markdown,
                )
            )

        url = payload.get("next_page")
        if len(articles) >= min_articles:
            break

    return articles
