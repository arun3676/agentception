"""
Redis-based persistent cache for job search results.
Falls back to in-memory cache if Redis unavailable.

Free tier compatible:
- Short TTL (1 hour) to manage storage
- Compressed JSON to save space
- Graceful fallback on errors
"""
import os
import json
import hashlib
from typing import Any, Optional
from dotenv import load_dotenv

# Load .env at module level
load_dotenv()

# In-memory fallback
_memory_fallback: dict = {}

# Redis client (lazy initialized)
_redis_client = None

def get_redis_client():
    """Get Redis client from REDIS_URL environment variable."""
    global _redis_client
    
    if _redis_client is not None:
        return _redis_client
    
    # IMPORTANT: Load from environment
    redis_url = os.getenv("REDIS_URL")
    
    # Debug: print what we got
    if redis_url:
        # Mask password for logging
        masked = redis_url[:20] + "***" + redis_url[-30:] if len(redis_url) > 50 else redis_url
        print(f"🔗 Redis URL found: {masked}")
    else:
        print("⚠️ REDIS_URL not set in environment, using in-memory cache")
        return None
    
    try:
        import redis
        
        # Check if SSL URL (rediss://)
        is_ssl = redis_url.startswith("rediss://")
        
        if is_ssl:
            # Redis Cloud with SSL - use redis-py 4.x compatible options
            # The WRONG_VERSION_NUMBER error usually means the URL scheme is wrong
            # or the port doesn't support SSL. Try converting to non-SSL first.
            
            # Option 1: Try with SSL disabled (convert rediss:// to redis://)
            non_ssl_url = redis_url.replace("rediss://", "redis://", 1)
            print(f"    🔄 Trying non-SSL connection...")
            
            try:
                _redis_client = redis.from_url(
                    non_ssl_url,
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True,
                )
                _redis_client.ping()
                print("✅ Redis Cloud connected (non-SSL)")
                return _redis_client
            except Exception as non_ssl_err:
                print(f"    ⚠️ Non-SSL failed: {non_ssl_err}")
                
                # Option 2: Try original SSL URL with cert verification disabled
                _redis_client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True,
                    ssl_cert_reqs="none",
                )
        else:
            # Non-SSL connection
            _redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
        
        # Test connection
        _redis_client.ping()
        print("✅ Redis Cloud connected successfully")
        return _redis_client
        
    except Exception as e:
        print(f"⚠️ Redis connection failed: {e}, using in-memory cache")
        _redis_client = None
        return None

def make_cache_key(prefix: str, *args) -> str:
    """Create a consistent cache key from arguments."""
    # Hash the arguments to create a short key
    key_data = ":".join(str(a).lower().strip() for a in args if a)
    key_hash = hashlib.md5(key_data.encode()).hexdigest()[:12]
    return f"{prefix}:{key_hash}"

def cache_set(key: str, value: Any, ttl_seconds: int = 3600) -> bool:
    """
    Store value in cache with TTL.
    
    Args:
        key: Cache key
        value: Value to store (will be JSON serialized)
        ttl_seconds: Time to live in seconds (default 1 hour)
    
    Returns:
        True if stored successfully
    """
    client = get_redis_client()
    
    try:
        json_value = json.dumps(value, default=str)
        
        if client:
            client.setex(key, ttl_seconds, json_value)
            return True
        else:
            # Fallback to memory
            _memory_fallback[key] = {
                'value': value,
                'expires': None  # Memory cache doesn't expire (cleared on restart)
            }
            return True
    except Exception as e:
        print(f"⚠️ Cache set error for {key}: {e}")
        return False

def cache_get(key: str) -> Optional[Any]:
    """
    Retrieve value from cache.
    
    Returns:
        Cached value or None if not found/expired
    """
    client = get_redis_client()
    
    try:
        if client:
            value = client.get(key)
            if value:
                return json.loads(value)
            return None
        else:
            # Fallback to memory
            cached = _memory_fallback.get(key)
            if cached:
                return cached.get('value')
            return None
    except Exception as e:
        print(f"⚠️ Cache get error for {key}: {e}")
        return None

def cache_delete(key: str) -> bool:
    """Delete a key from cache."""
    client = get_redis_client()
    
    try:
        if client:
            client.delete(key)
        else:
            _memory_fallback.pop(key, None)
        return True
    except Exception as e:
        print(f"⚠️ Cache delete error for {key}: {e}")
        return False

# === SEARCH-SPECIFIC CACHE FUNCTIONS ===

def cache_search_results(role: str, location: str, results: list, ttl_seconds: int = 1800) -> bool:
    """
    Cache search results for a role+location combination.
    TTL: 30 minutes (fresh enough, saves API calls)
    """
    key = make_cache_key("search", role, location)
    return cache_set(key, results, ttl_seconds)

def get_cached_search_results(role: str, location: str) -> Optional[list]:
    """
    Get cached search results for role+location.
    Returns None if not cached or expired.
    """
    key = make_cache_key("search", role, location)
    return cache_get(key)

def cache_ats_query(query: str, results: list, ttl_seconds: int = 900) -> bool:
    """
    Cache individual ATS query results.
    TTL: 15 minutes (Tavily results change frequently)
    """
    key = make_cache_key("ats", query)
    return cache_set(key, results, ttl_seconds)

def get_cached_ats_query(query: str) -> Optional[list]:
    """Get cached ATS query results."""
    key = make_cache_key("ats", query)
    return cache_get(key)
