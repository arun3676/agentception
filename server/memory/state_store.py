from __future__ import annotations
import asyncio
from typing import Dict, Any

class Memory:
    def __init__(self):
        self.kv: Dict[str, Any] = {}
    def set(self, key: str, value: Any): self.kv[key] = value
    def get(self, key: str, default=None): return self.kv.get(key, default)

class TimelineBus:
    def __init__(self): self.queues: Dict[str, asyncio.Queue] = {}
    def ensure(self, run_id: str):
        q = self.queues.get(run_id)
        if not q:
            q = asyncio.Queue(); self.queues[run_id] = q
        return q
    def get(self, run_id: str): return self.queues.get(run_id)
