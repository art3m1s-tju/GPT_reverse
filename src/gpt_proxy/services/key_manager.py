"""API key management with rotation strategies."""

from typing import Literal
from datetime import datetime, timedelta
from dataclasses import dataclass
import random


@dataclass
class KeyState:
    """State of an individual API key."""

    key: str
    is_active: bool = True
    exhausted_at: datetime | None = None
    reset_at: datetime | None = None
    request_count: int = 0
    error_count: int = 0


class APIKeyManager:
    """Manage multiple OpenAI API keys with rotation strategies."""

    def __init__(
        self,
        keys: list[str],
        strategy: Literal["round-robin", "least-used", "random"] = "round-robin",
    ):
        self.keys = [KeyState(key=k) for k in keys]
        self.strategy = strategy
        self._index = 0

    def get_key(self) -> str | None:
        """Get next available key based on strategy."""
        active_keys = [k for k in self.keys if k.is_active and not self._is_exhausted(k)]

        if not active_keys:
            return None

        if self.strategy == "round-robin":
            key = active_keys[self._index % len(active_keys)]
            self._index += 1
        elif self.strategy == "least-used":
            key = min(active_keys, key=lambda k: k.request_count)
        elif self.strategy == "random":
            key = random.choice(active_keys)
        else:
            key = active_keys[0]

        key.request_count += 1
        return key.key

    def report_error(self, key_str: str, error_type: str):
        """Report key error."""
        for k in self.keys:
            if k.key == key_str:
                k.error_count += 1
                if error_type == "rate_limit":
                    k.exhausted_at = datetime.now()
                    k.reset_at = datetime.now() + timedelta(minutes=1)
                elif error_type == "invalid":
                    k.is_active = False

    def _is_exhausted(self, key: KeyState) -> bool:
        """Check if key is temporarily exhausted."""
        if key.reset_at and datetime.now() > key.reset_at:
            key.exhausted_at = None
            key.reset_at = None
            return False
        return key.exhausted_at is not None

    def get_status(self) -> list[dict]:
        """Get status of all keys."""
        return [
            {
                "key": k.key[:8] + "..." + k.key[-4:] if len(k.key) > 12 else "***",
                "active": k.is_active,
                "exhausted": k.exhausted_at is not None,
                "requests": k.request_count,
                "errors": k.error_count,
            }
            for k in self.keys
        ]

    def reset_counts(self):
        """Reset request and error counts."""
        for k in self.keys:
            k.request_count = 0
            k.error_count = 0