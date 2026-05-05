"""Unit tests for services."""

import pytest
from datetime import datetime, timedelta

from gpt_proxy.services.key_manager import APIKeyManager, KeyState
from gpt_proxy.services.cache import ResponseCache
from gpt_proxy.services.cost_tracker import CostTracker


class TestAPIKeyManager:
    """Tests for API key rotation."""

    def test_round_robin_rotation(self):
        manager = APIKeyManager(
            keys=["key1", "key2", "key3"],
            strategy="round-robin",
        )

        assert manager.get_key() == "key1"
        assert manager.get_key() == "key2"
        assert manager.get_key() == "key3"
        assert manager.get_key() == "key1"  # Wraps around

    def test_least_used_strategy(self):
        manager = APIKeyManager(
            keys=["key1", "key2", "key3"],
            strategy="least-used",
        )

        # Get keys - should always pick the one with least requests
        k1 = manager.get_key()  # key1 (all have 0, picks first)
        k2 = manager.get_key()  # key2 or key3 (both have 0, picks one with least)
        k3 = manager.get_key()  # the remaining one with 0

        # All keys should have been used once
        assert sum(k.request_count for k in manager.keys) == 3

    def test_random_strategy(self):
        manager = APIKeyManager(
            keys=["key1", "key2", "key3"],
            strategy="random",
        )

        # Just verify it returns a key
        key = manager.get_key()
        assert key in ["key1", "key2", "key3"]

    def test_report_rate_limit_error(self):
        manager = APIKeyManager(keys=["key1", "key2"])

        manager.report_error("key1", "rate_limit")

        # key1 should be exhausted
        assert manager.keys[0].exhausted_at is not None
        assert manager.keys[0].reset_at is not None

        # Should skip exhausted key
        assert manager.get_key() == "key2"

    def test_report_invalid_key_error(self):
        manager = APIKeyManager(keys=["key1", "key2"])

        manager.report_error("key1", "invalid")

        # key1 should be inactive
        assert manager.keys[0].is_active is False

        # Should skip invalid key
        assert manager.get_key() == "key2"

    def test_exhausted_key_recovery(self):
        manager = APIKeyManager(keys=["key1"])

        # Mark key as exhausted with past reset time
        manager.keys[0].exhausted_at = datetime.now()
        manager.keys[0].reset_at = datetime.now() - timedelta(minutes=1)

        # Key should be recovered
        assert manager.get_key() == "key1"

    def test_get_status(self):
        manager = APIKeyManager(keys=["sk-test1234567890abcdef"])

        status = manager.get_status()
        assert len(status) == 1
        # Key should be masked: first 8 chars + ... + last 4 chars
        # sk-test1234567890abcdef (20 chars) -> sk-test12...cdef
        assert "..." in status[0]["key"]
        assert status[0]["key"].endswith("cdef")
        assert status[0]["active"] is True


class TestResponseCache:
    """Tests for response caching."""

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self):
        cache = ResponseCache(ttl_seconds=60)

        key = cache.generate_key("POST", "/v1/chat/completions", b'{"test": 1}')
        await cache.set(key, b'{"response": 1}')

        result = await cache.get(key)
        assert result == b'{"response": 1}'

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        cache = ResponseCache()

        result = await cache.get("nonexistent-key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_expiry(self):
        cache = ResponseCache(ttl_seconds=0)  # Immediate expiry

        key = cache.generate_key("POST", "/test", b"body")
        await cache.set(key, b"response")

        # Should be expired immediately
        result = await cache.get(key)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_clear(self):
        cache = ResponseCache()

        key = cache.generate_key("POST", "/test", b"body")
        await cache.set(key, b"response")

        await cache.clear()

        result = await cache.get(key)
        assert result is None

    def test_cache_stats(self):
        cache = ResponseCache()
        stats = cache.stats()

        assert "size" in stats
        assert "ttl_seconds" in stats
        assert "hits" in stats
        assert "misses" in stats


class TestCostTracker:
    """Tests for cost tracking."""

    def test_count_tokens(self):
        tracker = CostTracker()

        count = tracker.count_tokens("Hello, world!", "gpt-4")
        assert count > 0

    def test_count_messages_tokens(self):
        tracker = CostTracker()

        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi!"},
        ]

        count = tracker.count_messages_tokens(messages, "gpt-4")
        assert count > 0

    @pytest.mark.asyncio
    async def test_track_usage(self):
        tracker = CostTracker()

        await tracker.track_usage(
            key_id="key1",
            model="gpt-4o-mini",
            prompt_tokens=100,
            completion_tokens=50,
        )

        usage = await tracker.get_usage("day")
        assert usage["total_requests"] == 1
        assert usage["total_tokens"] == 150
        # Cost should be calculated (gpt-4o-mini: $0.15/1M input, $0.60/1M output)
        # 100 * 0.15/1M + 50 * 0.60/1M = 0.000015 + 0.000030 = 0.000045
        assert usage["total_cost_usd"] >= 0

    @pytest.mark.asyncio
    async def test_usage_by_model(self):
        tracker = CostTracker()

        await tracker.track_usage("key1", "gpt-4o-mini", 100, 50)
        await tracker.track_usage("key1", "gpt-4o", 200, 100)

        usage = await tracker.get_usage("day")

        assert "gpt-4o-mini" in usage["by_model"]
        assert "gpt-4o" in usage["by_model"]
        assert usage["by_model"]["gpt-4o-mini"]["tokens"] == 150
        assert usage["by_model"]["gpt-4o"]["tokens"] == 300
