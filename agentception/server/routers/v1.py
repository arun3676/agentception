from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from ..memory import sql_store

router = APIRouter(prefix="/api/v1")


# External catalogues shown as optional discovery links, not ranked endorsements.
JOB_BOARDS = [
    {"title": "Wellfound", "url": "https://wellfound.com/jobs"},
    {"title": "Y Combinator Jobs", "url": "https://www.workatastartup.com/"},
    {"title": "Hacker News Jobs", "url": "https://news.ycombinator.com/jobs"},
    {"title": "LinkedIn Jobs", "url": "https://www.linkedin.com/jobs/"},
    {"title": "Welcome to the Jungle", "url": "https://www.welcometothejungle.com/"},
    {"title": "Built In", "url": "https://builtin.com/jobs"},
]


def _public_resource(resource: dict) -> dict:
    """Remove internal popularity and review flags that have no public method."""
    return {
        key: value
        for key, value in resource.items()
        if key not in {"verified", "upvotes", "added_at", "updated_at"}
    }


@router.get("/resources")
async def list_resources(
    q: Optional[str] = None,
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    cost: Optional[str] = None,
    tag: Optional[str] = None,
    featured: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
):
    items = sql_store.resources_list(
        query=q,
        category=category,
        difficulty=difficulty,
        cost=cost,
        tag=tag,
        featured=featured,
        limit=limit,
        offset=offset,
    )
    public_items = [_public_resource(item) for item in items]
    return {"items": public_items, "count": len(public_items)}


@router.get("/resources/{resource_id}")
async def get_resource(resource_id: str):
    resource = sql_store.resources_get(resource_id)
    if not resource:
        raise HTTPException(404, "Resource not found")
    return _public_resource(resource)


@router.get("/recommendations")
async def recommendations(topic: Optional[str] = None):
    if topic:
        resources = sql_store.resources_list(query=topic, limit=12)
        if not resources:
            resources = sql_store.resources_featured(limit=12)
    else:
        resources = sql_store.resources_featured(limit=12)
    return {
        "resources": [_public_resource(resource) for resource in resources],
        "job_boards": JOB_BOARDS,
    }
