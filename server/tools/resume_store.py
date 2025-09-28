from __future__ import annotations
import os, uuid
from typing import Optional, Dict

# In-memory cache for resume text
_CACHE: Dict[str, str] = {}

# Create uploads directory
UP = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "uploads"))
os.makedirs(UP, exist_ok=True)

def put_text(text: str) -> str:
    """Store resume text and return a token"""
    tok = uuid.uuid4().hex
    _CACHE[tok] = text
    print(f"📄 Stored resume text: {len(text)} characters with token {tok[:8]}...")
    return tok

def get_text(token: str) -> Optional[str]:
    """Retrieve resume text by token"""
    text = _CACHE.get(token)
    if text:
        print(f"📄 Retrieved resume text: {len(text)} characters for token {token[:8]}...")
    else:
        print(f"❌ No resume found for token {token[:8]}...")
    return text

def clear_cache():
    """Clear all cached resume text (for cleanup)"""
    global _CACHE
    _CACHE.clear()
    print("🗑️ Cleared resume cache")
