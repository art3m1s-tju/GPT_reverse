"""Token counting and cost tracking."""

import tiktoken
from datetime import datetime, timedelta
from typing import Literal


# Pricing per 1M tokens (as of 2024)
MODEL_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "gpt-3.5-turbo-0125": {"input": 0.50, "output": 1.50},
    "text-embedding-3-small": {"input": 0.02, "output": 0},
    "text-embedding-3-large": {"input": 0.13, "output": 0},
    "text-embedding-ada-002": {"input": 0.10, "output": 0},
    "dall-e-3": {"input": 0, "output": 0, "per_image": 0.04},
    "whisper-1": {"input": 0, "output": 0, "per_minute": 0.006},
    "tts-1": {"input": 0, "output": 0, "per_1k_chars": 0.015},
    "tts-1-hd": {"input": 0, "output": 0, "per_1k_chars": 0.030},
}


class CostTracker:
    """Track token usage and costs."""

    def __init__(self):
        self._usage: list[dict] = []

    def count_tokens(self, text: str, model: str) -> int:
        """Count tokens using tiktoken."""
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))

    def count_messages_tokens(self, messages: list[dict], model: str) -> int:
        """Count tokens in chat messages."""
        total = 0
        for msg in messages:
            total += 4  # Message overhead
            content = msg.get("content", "")
            if isinstance(content, str):
                total += self.count_tokens(content, model)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        total += self.count_tokens(part.get("text", ""), model)
        total += 2  # Reply priming
        return total

    async def track_usage(
        self,
        key_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ):
        """Record token usage."""
        pricing = MODEL_PRICING.get(model, {"input": 0, "output": 0})
        cost = (
            prompt_tokens * pricing["input"] / 1_000_000
            + completion_tokens * pricing["output"] / 1_000_000
        )

        self._usage.append({
            "timestamp": datetime.now().isoformat(),
            "key_id": key_id,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cost_usd": cost,
        })

    async def get_usage(
        self,
        period: Literal["day", "week", "month"] = "day",
        key_id: str | None = None,
    ) -> dict:
        """Get usage summary."""
        now = datetime.now()
        if period == "day":
            cutoff = now - timedelta(days=1)
        elif period == "week":
            cutoff = now - timedelta(days=7)
        else:
            cutoff = now - timedelta(days=30)

        filtered = [
            u
            for u in self._usage
            if datetime.fromisoformat(u["timestamp"]) > cutoff
            and (key_id is None or u["key_id"] == key_id)
        ]

        total_cost = sum(u["cost_usd"] for u in filtered)
        total_prompt = sum(u["prompt_tokens"] for u in filtered)
        total_completion = sum(u["completion_tokens"] for u in filtered)

        return {
            "period": period,
            "total_requests": len(filtered),
            "total_tokens": total_prompt + total_completion,
            "prompt_tokens": total_prompt,
            "completion_tokens": total_completion,
            "total_cost_usd": round(total_cost, 4),
            "by_model": self._aggregate_by_model(filtered),
        }

    def _aggregate_by_model(self, usage: list[dict]) -> dict:
        """Aggregate usage by model."""
        result: dict[str, dict] = {}
        for u in usage:
            model = u["model"]
            if model not in result:
                result[model] = {"tokens": 0, "cost": 0, "requests": 0}
            result[model]["tokens"] += u["total_tokens"]
            result[model]["cost"] += u["cost_usd"]
            result[model]["requests"] += 1

        # Round costs
        for model in result:
            result[model]["cost"] = round(result[model]["cost"], 4)

        return result

    def clear(self):
        """Clear usage history."""
        self._usage.clear()