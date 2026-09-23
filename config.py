"""Central config, loaded from environment variables (.env in local dev)."""
import os

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

HELP_CENTER_URL = os.environ.get("HELP_CENTER_URL", "https://support.optisigns.com")
LOCALE = os.environ.get("HELP_CENTER_LOCALE", "en-us")
MIN_ARTICLES = int(os.environ.get("MIN_ARTICLES", "30"))

ARTICLES_DIR = os.environ.get("ARTICLES_DIR", "articles")
STATE_PATH = os.environ.get("STATE_PATH", "state.json")

VECTOR_STORE_NAME = os.environ.get("VECTOR_STORE_NAME", "optibot-knowledge-base")
# Once created, pin the id here (or via env) so re-runs reuse the same store
# instead of creating a new one every day.
VECTOR_STORE_ID = os.environ.get("VECTOR_STORE_ID") or None

SYSTEM_PROMPT = (
    "You are OptiBot, the customer-support bot for OptiSigns.com.\n"
    "• Tone: helpful, factual, concise.\n"
    "• Only answer using the uploaded docs.\n"
    "• Max 5 bullet points; else link to the doc.\n"
    '• Cite up to 3 "Article URL:" lines per reply.'
)
