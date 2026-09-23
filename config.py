"""Central config, loaded from environment variables (.env in local dev)."""
import os

from dotenv import load_dotenv

load_dotenv()

AI_PROVIDER = os.environ.get("AI_PROVIDER", "openai").lower()
if AI_PROVIDER not in ("openai", "gemini"):
    raise ValueError(f"AI_PROVIDER must be 'openai' or 'gemini', got {AI_PROVIDER!r}")

# Only the active provider's key is required -- switching providers shouldn't
# demand credentials for the one you're not using.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if AI_PROVIDER == "openai" and not OPENAI_API_KEY:
    raise KeyError("OPENAI_API_KEY")
if AI_PROVIDER == "gemini" and not GEMINI_API_KEY:
    raise KeyError("GEMINI_API_KEY")

GEMINI_EMBEDDING_MODEL = os.environ.get("GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-2")

HELP_CENTER_URL = os.environ.get("HELP_CENTER_URL", "https://support.optisigns.com")
LOCALE = os.environ.get("HELP_CENTER_LOCALE", "en-us")
MIN_ARTICLES = int(os.environ.get("MIN_ARTICLES", "30"))

ARTICLES_DIR = os.environ.get("ARTICLES_DIR", "articles")
STATE_PATH = os.environ.get("STATE_PATH", "state.json")

STORE_NAME = os.environ.get("STORE_NAME", "optibot-knowledge-base")
# Once created, pin the id here (or via env) so re-runs reuse the same store
# instead of creating a new one every day. Provider-specific env var names
# (a vector store id and a Gemini file-search-store name are shaped
# differently) collapse into one generic STORE_ID for the rest of the code.
STORE_ID = (
    os.environ.get("VECTOR_STORE_ID") if AI_PROVIDER == "openai" else os.environ.get("GEMINI_STORE_ID")
) or None

SYSTEM_PROMPT = (
    "You are OptiBot, the customer-support bot for OptiSigns.com.\n"
    "• Tone: helpful, factual, concise.\n"
    "• Only answer using the uploaded docs.\n"
    "• Max 5 bullet points; else link to the doc.\n"
    '• Cite up to 3 "Article URL:" lines per reply.'
)
