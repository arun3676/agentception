from __future__ import annotations

"""Public, static career-topic catalogue used by the Resources page."""

import json
import pathlib
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/study")
_DATA_DIR = pathlib.Path(__file__).parent.parent / "data" / "study"


def _load_pillars() -> list[dict[str, Any]]:
    with open(_DATA_DIR / "pillars.json", "r", encoding="utf-8") as handle:
        data = json.load(handle)
    pillars = data.get("pillars", []) if isinstance(data, dict) else []
    return [pillar for pillar in pillars if isinstance(pillar, dict)]


_PILLARS = _load_pillars()


@router.get("/pillars")
async def list_pillars():
    """Return labels and keywords from the repository's dated static catalogue."""
    return {
        "pillars": [
            {
                "key": pillar.get("key", ""),
                "label": pillar.get("label", ""),
                "keywords": list(pillar.get("keywords", []))[:6],
            }
            for pillar in _PILLARS
            if pillar.get("key") and pillar.get("label")
        ]
    }
