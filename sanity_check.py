"""Run the assignment's sanity-check question against the synced Gemini
File Search store. Not part of the daily pipeline -- a manual check/demo
script. Usage: python3 sanity_check.py ["your question here"]
"""
import itertools
import os
import sys
import threading
import time

from dotenv import load_dotenv
from google import genai

load_dotenv()

SYSTEM_PROMPT = (
    "You are OptiBot, the customer-support bot for OptiSigns.com.\n"
    "• Tone: helpful, factual, concise.\n"
    "• Only answer using the uploaded docs.\n"
    "• Max 5 bullet points; else link to the doc.\n"
    '• Cite up to 3 "Article URL:" lines per reply.'
)

QUESTION = sys.argv[1] if len(sys.argv) > 1 else "How do I add a YouTube video?"

# A few free-tier Flash variants, tried in order: the free tier's 20
# requests/day-per-model limit and occasional 503 "high demand" errors mean
# any single model can be temporarily unavailable.
MODELS = ["gemini-flash-lite-latest", "gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash"]


class Spinner:
    """A simple terminal spinner so a live demo doesn't look frozen while
    waiting on the API."""

    _FRAMES = "|/-\\"

    def __init__(self, message: str):
        self._message = message
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)

    def _spin(self) -> None:
        for frame in itertools.cycle(self._FRAMES):
            if self._stop.is_set():
                break
            print(f"\r{self._message} {frame}", end="", flush=True)
            time.sleep(0.1)
        print("\r" + " " * (len(self._message) + 2) + "\r", end="", flush=True)

    def __enter__(self) -> "Spinner":
        self._thread.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self._stop.set()
        self._thread.join()


def main() -> int:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    store_id = os.environ["GEMINI_STORE_ID"]

    print(f"Question: {QUESTION}\n")

    for model in MODELS:
        try:
            with Spinner(f"Asking {model}..."):
                interaction = client.interactions.create(
                    model=model,
                    input=f"{SYSTEM_PROMPT}\n\nUser question: {QUESTION}",
                    tools=[{"type": "file_search", "file_search_store_names": [store_id]}],
                    timeout=30,  # fail over to the next model rather than hang indefinitely
                )
            for step in interaction.steps:
                if step.type == "model_output":
                    for block in step.content:
                        if block.type == "text":
                            print(block.text)
            return 0
        except Exception as e:
            print(f"(model {model} unavailable, trying next: {e})", file=sys.stderr)
            time.sleep(3)

    print("All models were unavailable -- try again in a minute.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
