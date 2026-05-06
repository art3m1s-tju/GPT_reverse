"""Unit tests for response cache."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch

from gpt_proxy.services.cache import ResponseCache


class TestGenerateKey:
    """Tests for cache key generation."""

    def test_deterministic(self):
        cache = ResponseCache()
        key1 = cache.generate_key("POST", "/v1/chat/completions", b'{"model":"gpt-4"}')
        key2 = cache.generate_key("POST", "/v1/chat/completions", b'{"model":"gpt-4"}')
        assert key1 == key2

    def test_different_for_different_inputs(self):
        cache = ResponseCache()
        key1 = cache.generate_key("POST", "/v1/chat/completions", b'{"model":"gpt-4"}')
        key2 = cache.generate_key("POST", "/v1/chat/completions", b'{"model":"gpt-3.5"}')
        key3 = cache.generate_key("GET", "/v1/models", None)
        assert key1 != key2
        assert key1 != key3
        assert key2 != key3

    def test_none_body_handled(self):
        cache = ResponseCache()
        key = cache.generate_key("GET", "/v1/models", None)
        assert isinstance(key, str)
        assert len(key) == 64  # SHA-256 hex


class TestCacheGetSet:
    """Tests for cache get/set operations."""

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        cache = ResponseCache()
        key = cache.generate_key("GET", "/test", None)
        await cache.set(key, b"response-data")
        result = await cache.get(key)
        assert result == b"response-data"

    @pytest.mark.asyncio
    async def test_cache_miss_returns_none(self):
        cache = ResponseCache()
        result = await cache.get("nonexistent-key")
        assert result is None


class TestCacheTTL:
    """Tests for TTL expiration."""

    @pytest.mark.asyncio
    async def test_expired_entry_returns_none(self):
        cache = ResponseCache(ttl_seconds=1)
        key = "test-key"
        await cache.set(key, b"data")

        # Manually set timestamp to the past
        old_time = datetime.now() - timedelta(seconds=2)
        cache._cache[key] = (b"data", old_time)

        result = await cache.get(key)
        assert result is None

    @pytest.mark.asyncio
    async def test_fresh_entry_returns_data(self):
        cache = ResponseCache(ttl_seconds=3600)
        key = "test-key"
        await cache.set(key, b"data")
        result = await cache.get(key)
        assert result == b"data"

    @pytest.mark.asyncio
    async def test_expired_entry_removed_from_cache(self):
        cache = ResponseCache(ttl_seconds=1)
        key = "test-key"
        await cache.set(key, b"data")

        old_time = datetime.now() - timedelta(seconds=2)
        cache._cache[key] = (b"data", old_time)

        await cache.get(key)
        assert key not in cache._cache


class TestCacheClear:
    """Tests for cache clear."""

    @pytest.mark.asyncio
    async def test_clear_resets_cache(self):
        cache = ResponseCache()
        await cache.set("key1", b"data1")
        await cache.set("key2", b"data2")
        await cache.get("key1")  # hit

        await cache.clear()
        assert len(cache._cache) == 0
        assert cache._hits == 0
        assert cache._misses == 0

    @pytest.mark.asyncio
    async def test_get_after_clear_is_miss(self):
        cache = ResponseCache()
        key = cache.generate_key("GET", "/test", None)
        await cache.set(key, b"data")
        await cache.clear()
        result = await cache.get(key)
        assert result is None


class TestCacheStats:
    """Tests for cache statistics."""

    def test_initial_stats(self):
        cache = ResponseCache()
        stats = cache.stats()
        assert stats["size"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0

    @pytest.mark.asyncio
    async def test_stats_after_operations(self):
        cache = ResponseCache()
        await cache.set("key1", b"data")
        await cache.get("key1")  # hit
        await cache.get("missing")  # miss

        stats = cache.stats()
        assert stats["size"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    def test_stats_ttl_value(self):
        cache = ResponseCache(ttl_seconds=7200)
        assert cache.stats()["ttl_seconds"] == 7200
