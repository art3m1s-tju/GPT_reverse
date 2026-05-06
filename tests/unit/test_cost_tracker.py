"""Unit tests for cost tracker."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from gpt_proxy.services.cost_tracker import CostTracker


class TestCountTokens:
    """Tests for token counting."""

    def test_counts_tokens_for_known_model(self):
        tracker = CostTracker()
        count = tracker.count_tokens("Hello, world!", "gpt-4")
        assert isinstance(count, int)
        assert count > 0

    def test_counts_tokens_for_unknown_model_falls_back(self):
        tracker = CostTracker()
        count = tracker.count_tokens("Hello, world!", "unknown-model-xyz")
        assert isinstance(count, int)
        assert count > 0

    def test_empty_string_returns_zero_or_low(self):
        tracker = CostTracker()
        count = tracker.count_tokens("", "gpt-4")
        assert count == 0


class TestCountMessagesTokens:
    """Tests for message token counting."""

    def test_string_content(self):
        tracker = CostTracker()
        messages = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        count = tracker.count_messages_tokens(messages, "gpt-4")
        # 2 messages * 4 overhead + tokens + 2 reply priming
        assert count > 10

    def test_list_content(self):
        tracker = CostTracker()
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image"},
                ],
            }
        ]
        count = tracker.count_messages_tokens(messages, "gpt-4")
        assert count > 4  # At least overhead

    def test_list_content_ignores_non_text_parts(self):
        tracker = CostTracker()
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": "http://example.com/img.png"}},
                ],
            }
        ]
        count = tracker.count_messages_tokens(messages, "gpt-4")
        # Only 4 overhead + 2 reply priming = 6
        assert count == 6

    def test_empty_messages(self):
        tracker = CostTracker()
        count = tracker.count_messages_tokens([], "gpt-4")
        assert count == 2  # Just reply priming


class TestTrackUsage:
    """Tests for usage tracking."""

    @pytest.mark.asyncio
    async def test_records_usage(self):
        tracker = CostTracker()
        await tracker.track_usage("key-1", "gpt-4o", 100, 50)
        assert len(tracker._usage) == 1
        entry = tracker._usage[0]
        assert entry["key_id"] == "key-1"
        assert entry["model"] == "gpt-4o"
        assert entry["prompt_tokens"] == 100
        assert entry["completion_tokens"] == 50
        assert entry["total_tokens"] == 150

    @pytest.mark.asyncio
    async def test_calculates_cost(self):
        tracker = CostTracker()
        await tracker.track_usage("key-1", "gpt-4o", 1_000_000, 0)
        entry = tracker._usage[0]
        # gpt-4o input = $2.50 per 1M tokens
        assert entry["cost_usd"] == pytest.approx(2.50, rel=1e-4)

    @pytest.mark.asyncio
    async def test_unknown_model_zero_cost(self):
        tracker = CostTracker()
        await tracker.track_usage("key-1", "nonexistent-model", 1000, 1000)
        entry = tracker._usage[0]
        assert entry["cost_usd"] == 0.0


class TestGetUsage:
    """Tests for usage retrieval."""

    @pytest.mark.asyncio
    async def test_get_usage_day_period(self):
        tracker = CostTracker()
        await tracker.track_usage("key-1", "gpt-4o", 100, 50)
        usage = await tracker.get_usage(period="day")
        assert usage["period"] == "day"
        assert usage["total_requests"] == 1
        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 50

    @pytest.mark.asyncio
    async def test_get_usage_filters_by_key_id(self):
        tracker = CostTracker()
        await tracker.track_usage("key-a", "gpt-4o", 100, 50)
        await tracker.track_usage("key-b", "gpt-4o", 200, 75)

        usage_a = await tracker.get_usage(period="day", key_id="key-a")
        assert usage_a["total_requests"] == 1
        assert usage_a["prompt_tokens"] == 100

        usage_b = await tracker.get_usage(period="day", key_id="key-b")
        assert usage_b["total_requests"] == 1
        assert usage_b["prompt_tokens"] == 200

    @pytest.mark.asyncio
    async def test_get_usage_excludes_old_entries(self):
        tracker = CostTracker()
        # Add a current entry
        await tracker.track_usage("key-1", "gpt-4o", 100, 50)
        # Manually add an old entry (2 days ago)
        old_time = (datetime.now() - timedelta(days=2)).isoformat()
        tracker._usage.append({
            "timestamp": old_time,
            "key_id": "key-1",
            "model": "gpt-4o",
            "prompt_tokens": 999,
            "completion_tokens": 999,
            "total_tokens": 1998,
            "cost_usd": 1.0,
        })

        usage = await tracker.get_usage(period="day")
        assert usage["total_requests"] == 1
        assert usage["prompt_tokens"] == 100

    @pytest.mark.asyncio
    async def test_get_usage_week_period(self):
        tracker = CostTracker()
        await tracker.track_usage("key-1", "gpt-4o", 100, 50)
        usage = await tracker.get_usage(period="week")
        assert usage["period"] == "week"


class TestAggregateByModel:
    """Tests for model aggregation."""

    def test_aggregates_correctly(self):
        tracker = CostTracker()
        usage = [
            {
                "model": "gpt-4o",
                "total_tokens": 100,
                "cost_usd": 0.01,
            },
            {
                "model": "gpt-4o",
                "total_tokens": 200,
                "cost_usd": 0.02,
            },
            {
                "model": "gpt-3.5-turbo",
                "total_tokens": 50,
                "cost_usd": 0.001,
            },
        ]
        result = tracker._aggregate_by_model(usage)
        assert result["gpt-4o"]["tokens"] == 300
        assert result["gpt-4o"]["cost"] == pytest.approx(0.03, rel=1e-4)
        assert result["gpt-4o"]["requests"] == 2
        assert result["gpt-3.5-turbo"]["tokens"] == 50
        assert result["gpt-3.5-turbo"]["requests"] == 1

    def test_empty_usage_returns_empty(self):
        tracker = CostTracker()
        result = tracker._aggregate_by_model([])
        assert result == {}


class TestClear:
    """Tests for clear."""

    @pytest.mark.asyncio
    async def test_clears_usage(self):
        tracker = CostTracker()
        await tracker.track_usage("key-1", "gpt-4o", 100, 50)
        await tracker.track_usage("key-2", "gpt-4", 200, 75)
        tracker.clear()
        assert len(tracker._usage) == 0

    @pytest.mark.asyncio
    async def test_get_usage_after_clear(self):
        tracker = CostTracker()
        await tracker.track_usage("key-1", "gpt-4o", 100, 50)
        tracker.clear()
        usage = await tracker.get_usage(period="day")
        assert usage["total_requests"] == 0
