"""Gemini-only VLM smoke tests."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from perception.vlm import get_vlm_client


def main() -> int:
    print("Gemini-only VLM smoke test")
    if not os.getenv("GEMINI_API_KEY"):
        print("GEMINI_API_KEY not set; skipping live client creation.")
        return 0

    client = get_vlm_client()
    print(f"Client type: {type(client).__name__}")
    print("Gemini VLM client initialized successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
