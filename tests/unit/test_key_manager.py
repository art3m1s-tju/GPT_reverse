"""Unit tests for API key manager."""

import pytest
from unittest.mock import patch
from datetime import datetime, timedelta

from gpt_proxy.services.key_manager import APIKeyManager, KeyState


class TestRoundRobinStrategy:
    """Tests for round-robin key rotation."""

    def test_rotates_through_keys(self):
        manager = APIKeyManager(keys=["key-a", "key-b", "key-c"], strategy="round-robin")
        results = [manager.get_key() for _ in range(6)]
        assert results == ["key-a", "key-b", "key-c", "key-a", "key-b", "key-c"]

    def test_increments_request_count(self):
        manager = APIKeyManager(keys=["key-a", "key-b"], strategy="round-robin")
        manager.get_key()
        manager.get_key()
        assert manager.keys[0].request_count == 1
        assert manager.keys[1].request_count == 1


class TestLeastUsedStrategy:
    """Tests for least-used key selection."""

    def test_selects_least_used_key(self):
        manager = APIKeyManager(keys=["key-a", "key-b", "key-c"], strategy="least-used")
        # Use key-a twice
        manager.get_key()  # picks key-a (all tied)
        manager.get_key()  # picks key-b (all tied except key-a)
        manager.get_key()  # picks key-c (all tied except key-a, key-b)

        # Now key-a, key-b, key-c each have 1 use, so next should be key-a (first min)
        # Actually let's force usage
        manager.keys[0].request_count = 5
        manager.keys[1].request_count = 2
        manager.keys[2].request_count = 1
        result = manager.get_key()
        assert result == "key-c"

    def test_increments_request_count(self):
        manager = APIKeyManager(keys=["key-a"], strategy="least-used")
        manager.get_key()
        assert manager.keys[0].request_count == 1


class TestRandomStrategy:
    """Tests for random key selection."""

    def test_selects_from_active_keys(self):
        manager = APIKeyManager(keys=["key-a", "key-b", "key-c"], strategy="random")
        selected = set()
        for _ in range(100):
            selected.add(manager.get_key())
        assert selected == {"key-a", "key-b", "key-c"}

    def test_increments_request_count(self):
        manager = APIKeyManager(keys=["key-a"], strategy="random")
        manager.get_key()
        manager.get_key()
        assert manager.keys[0].request_count == 2


class TestKeyExhaustionAndReset:
    """Tests for key exhaustion and automatic reset."""

    def test_exhausted_key_skipped(self):
        manager = APIKeyManager(keys=["key-a", "key-b"], strategy="round-robin")
        # Exhaust key-a
        manager.keys[0].exhausted_at = datetime.now()
        manager.keys[0].reset_at = datetime.now() + timedelta(minutes=1)
        assert manager.get_key() == "key-b"

    def test_all_exhausted_returns_none(self):
        manager = APIKeyManager(keys=["key-a", "key-b"], strategy="round-robin")
        for k in manager.keys:
            k.exhausted_at = datetime.now()
            k.reset_at = datetime.now() + timedelta(minutes=1)
        assert manager.get_key() is None

    def test_exhausted_key_resets_after_reset_time(self):
        manager = APIKeyManager(keys=["key-a"], strategy="round-robin")
        manager.keys[0].exhausted_at = datetime.now() - timedelta(minutes=2)
        manager.keys[0].reset_at = datetime.now() - timedelta(minutes=1)
        # Reset time has passed, should be available again
        result = manager.get_key()
        assert result == "key-a"
        assert manager.keys[0].exhausted_at is None
        assert manager.keys[0].reset_at is None

    def test_inactive_key_skipped(self):
        manager = APIKeyManager(keys=["key-a", "key-b"], strategy="round-robin")
        manager.keys[0].is_active = False
        assert manager.get_key() == "key-b"


class TestErrorReporting:
    """Tests for error reporting."""

    def test_rate_limit_marks_exhausted(self):
        manager = APIKeyManager(keys=["key-a"], strategy="round-robin")
        manager.report_error("key-a", "rate_limit")
        assert manager.keys[0].exhausted_at is not None
        assert manager.keys[0].reset_at is not None
        assert manager.keys[0].error_count == 1

    def test_invalid_deactivates_key(self):
        manager = APIKeyManager(keys=["key-a"], strategy="round-robin")
        manager.report_error("key-a", "invalid")
        assert manager.keys[0].is_active is False
        assert manager.keys[0].error_count == 1

    def test_unknown_error_only_increments_count(self):
        manager = APIKeyManager(keys=["key-a"], strategy="round-robin")
        manager.report_error("key-a", "server_error")
        assert manager.keys[0].error_count == 1
        assert manager.keys[0].is_active is True
        assert manager.keys[0].exhausted_at is None


class TestGetStatus:
    """Tests for get_status."""

    def test_masks_long_keys(self):
        manager = APIKeyManager(keys=["sk-abcdefghijkmnopqrstuvwx"], strategy="round-robin")
        status = manager.get_status()
        assert status[0]["key"] == "sk-abcde...uvwx"

    def test_masks_short_keys(self):
        manager = APIKeyManager(keys=["short"], strategy="round-robin")
        status = manager.get_status()
        assert status[0]["key"] == "***"

    def test_status_fields(self):
        manager = APIKeyManager(keys=["key-a"], strategy="round-robin")
        manager.get_key()
        manager.report_error("key-a", "rate_limit")
        status = manager.get_status()
        assert len(status) == 1
        assert status[0]["active"] is True
        assert status[0]["exhausted"] is True
        assert status[0]["requests"] == 1
        assert status[0]["errors"] == 1


class TestEmptyKeyList:
    """Tests for empty key list."""

    def test_returns_none(self):
        manager = APIKeyManager(keys=[], strategy="round-robin")
        assert manager.get_key() is None

    def test_status_empty(self):
        manager = APIKeyManager(keys=[], strategy="round-robin")
        assert manager.get_status() == []


class TestResetCounts:
    """Tests for reset_counts."""

    def test_resets_all_counts(self):
        manager = APIKeyManager(keys=["key-a", "key-b"], strategy="round-robin")
        manager.get_key()
        manager.get_key()
        manager.report_error("key-a", "server_error")
        manager.reset_counts()
        for k in manager.keys:
            assert k.request_count == 0
            assert k.error_count == 0
