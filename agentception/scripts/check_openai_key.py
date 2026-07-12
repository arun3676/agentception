"""Smoke-check the OpenAI API key.

Named check_* rather than test_* on purpose: pytest imports every `test_*.py` it
finds during collection, and this file makes a real (billed) API call at import
time. As a test module it charged the account on every bare `pytest` run.

    python scripts/check_openai_key.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def main() -> int:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    api_key = os.getenv("OPENAI_API_KEY")

    print(f"OPENAI_API_KEY exists: {bool(api_key)}")
    if not api_key:
        print("[FAIL] OPENAI_API_KEY not found in environment")
        return 1

    print(f"OPENAI_API_KEY length: {len(api_key)}")
    print(f"OPENAI_API_KEY starts with 'sk-': {api_key.startswith('sk-')}")

    from openai import OpenAI

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say 'API key works!'"}],
            max_tokens=10,
        )
        print(f"[OK] API key works. Response: {response.choices[0].message.content}")
        return 0
    except Exception as e:
        print(f"[FAIL] API key rejected: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
