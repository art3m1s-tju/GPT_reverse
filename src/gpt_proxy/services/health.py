"""Health check service."""

from datetime import datetime


class HealthService:
    """Health check service."""

    def __init__(self, start_time: datetime | None = None):
        self.start_time = start_time or datetime.now()

    async def check(self) -> dict:
        """Basic health check."""
        uptime = (datetime.now() - self.start_time).total_seconds()
        return {
            "status": "healthy",
            "uptime_seconds": round(uptime, 2),
            "timestamp": datetime.now().isoformat(),
        }

    async def check_ready(self, key_manager=None, cache=None) -> dict:
        """Readiness check."""
        checks = {}

        # Check API keys
        if key_manager:
            active_keys = len([k for k in key_manager.keys if k.is_active])
            checks["api_keys"] = {"status": "ok" if active_keys > 0 else "error", "count": active_keys}
        else:
            checks["api_keys"] = {"status": "unknown"}

        # Check cache
        if cache:
            checks["cache"] = {"status": "ok", "stats": cache.stats()}
        else:
            checks["cache"] = {"status": "disabled"}

        # Overall status
        all_ok = all(c.get("status") in ("ok", "disabled", "unknown") for c in checks.values())

        return {
            "status": "ready" if all_ok else "not_ready",
            "checks": checks,
            "timestamp": datetime.now().isoformat(),
        }