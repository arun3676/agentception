"""
Quick check to see if MOCK_SEARCH mode is enabled.
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

# Load .env from the project root (this script lives in scripts/)
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"[OK] Loaded .env from: {env_path}")
else:
    load_dotenv()
    print(f"[WARN] .env not found, checking environment variables")

mock_mode = os.getenv('MOCK_SEARCH', 'false').lower() == 'true'

print(f"\nMOCK_SEARCH status: {'ENABLED' if mock_mode else 'DISABLED'}")
print(f"Current value: {os.getenv('MOCK_SEARCH', 'not set')}")

if mock_mode:
    print("\n[INFO] Mock mode is ON - server will use mock data instead of Tavily")
    print("       This is perfect for testing without consuming API credits!")
else:
    print("\n[INFO] Mock mode is OFF - server will use Tavily API")
    print("       To enable: python enable_mock_mode.py enable")

