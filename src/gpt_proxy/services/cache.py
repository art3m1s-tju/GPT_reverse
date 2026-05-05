"""Response caching service."""

import hashlib
from datetime import datetime, timedelta


class ResponseCache:
    """Cache responses for identical requests."""

    def __init__(self, ttl_seconds: int = 3600, backend: str = "memory"):
        self.ttl = ttl_seconds
        self.backend = backend
        self._cache: dict[str, tuple[bytes, datetime]] = {}
        self._hits = 0
        self._misses = 0

    def generate_key(self, method: str, path: str, body: bytes | None) -> str:
        """Generate deterministic cache key."""
        content = f"{method}:{path}:{body.hex() if body else 'empty'}"
        return hashlib.sha256(content.encode()).hexdigest()

    async def get(self, cache_key: str) -> bytes | None:
        """Get cached response if not expired."""
        if cache_key not in self._cache:
            self._misses += 1
            return None

        response, timestamp = self._cache[cache_key]
        if datetime.now() - timestamp > timedelta(seconds=self.ttl):
            del self._cache[cache_key]
            self._misses += 1
            return None

        self._hits += 1
        return response

    async def set(self, cache_key: str, response: bytes):
        """Cache response."""
        self._cache[cache_key] = (response, datetime.now())

    async def clear(self):
        """Clear all cached responses."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def stats(self) -> dict:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0
        return {
            "size": len(self._cache),
            "ttl_seconds": self.ttl,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 4),
        }