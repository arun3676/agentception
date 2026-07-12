"""
Cohort analytics: peer comparison patterns (Phase 3 — activates after 50 users).

Uses Supabase aggregations to surface:
- "Your callback rate vs similar profiles"
- Common patterns among users with same role + gap_type
"""
from __future__ import annotations

from typing import Optional

from ...supabase_client import get_supabase_client


async def get_cohort_comparison(
    user_id: str,
    target_role: str,
    gap_type: str,
) -> dict:
    """
    Compare a user's outcomes against their peer cohort.
    Only returns data when n≥10 for same role + gap_type.
    """
    sb = get_supabase_client()
    if not sb:
        return {"available": False, "reason": "Supabase unavailable"}

    try:
        # Count peers with same role + gap_type
        peer_audits = (
            sb.table("readiness_audits")
            .select("user_id", count="exact")
            .eq("target_role", target_role)
            .eq("gap_type", gap_type)
            .execute()
        )
        peer_count = peer_audits.count or 0

        if peer_count < 10:
            return {
                "available": False,
                "reason": f"Need at least 10 peers with same profile (currently {peer_count}). Growing!",
                "peer_count": peer_count,
            }

        # Get peer outcome stats
        peer_outcomes = (
            sb.table("application_outcomes")
            .select("outcome, user_id")
            .in_(
                "user_id",
                [a["user_id"] for a in (peer_audits.data or []) if a.get("user_id") != user_id],
            )
            .execute()
        )

        peer_data = peer_outcomes.data or []
        if not peer_data:
            return {"available": False, "reason": "No outcome data from peers yet"}

        # Compute peer stats
        total_peer = len(peer_data)
        peer_stats = {}
        for o in peer_data:
            key = o.get("outcome", "unknown")
            peer_stats[key] = peer_stats.get(key, 0) + 1

        peer_callback = (
            peer_stats.get("screen", 0) + peer_stats.get("onsite", 0) + peer_stats.get("offer", 0)
        ) / max(total_peer, 1)

        # Get user's own stats
        user_outcomes = (
            sb.table("application_outcomes")
            .select("outcome")
            .eq("user_id", user_id)
            .execute()
        )
        user_data = user_outcomes.data or []
        total_user = len(user_data)
        user_stats = {}
        for o in user_data:
            key = o.get("outcome", "unknown")
            user_stats[key] = user_stats.get(key, 0) + 1

        user_callback = (
            user_stats.get("screen", 0) + user_stats.get("onsite", 0) + user_stats.get("offer", 0)
        ) / max(total_user, 1)

        return {
            "available": True,
            "peer_count": peer_count,
            "your_callback_rate": round(user_callback * 100, 1),
            "peer_callback_rate": round(peer_callback * 100, 1),
            "your_stats": user_stats,
            "peer_stats": peer_stats,
            "your_total": total_user,
            "peer_total": total_peer,
        }

    except Exception as e:
        return {"available": False, "reason": f"Query error: {e}"}
