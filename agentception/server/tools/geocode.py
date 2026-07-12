from __future__ import annotations
import os, httpx
from typing import Tuple, Optional, Dict, Any

GEO_URL = "https://maps.googleapis.com/maps/api/geocode/json"

async def geocode_address(address: str) -> Optional[Dict[str, Any]]:
    GMAPS_KEY = os.getenv("GOOGLE_MAPS_KEY")
    if not GMAPS_KEY:
        print(f"❌ GOOGLE_MAPS_KEY not set")
        return None
    print(f"🔍 Geocoding address: '{address}' with key: {GMAPS_KEY[:10]}...")
    params = {"address": address, "key": GMAPS_KEY}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(GEO_URL, params=params)
        r.raise_for_status()
        j = r.json()
    print(f"📡 Google Maps response status: {j.get('status')}")
    if j.get("status") != "OK" or not j.get("results"):
        print(f"❌ Geocoding failed: status={j.get('status')}, results_count={len(j.get('results', []))}")
        if j.get("error_message"):
            print(f"❌ Error message: {j.get('error_message')}")
        return None
    res = j["results"][0]
    loc = res["geometry"]["location"]
    result = {
        "lat": loc["lat"], "lng": loc["lng"],
        "formatted": res.get("formatted_address", address)
    }
    print(f"✅ Geocoded '{address}' to: {result['formatted']} ({result['lat']:.4f}, {result['lng']:.4f})")
    return result
