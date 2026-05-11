import asyncio
import logging
from threading import Thread

from .Quota import QuotaClient
from ..utils.exceptions import QuotaReportingException

logger = logging.getLogger(__name__)


class PostChecker:
    def __init__(self) -> None:
        self.quota_client = QuotaClient()

    async def send_usage_report(self, used_tokens: int, cost: float) -> None:
        """Send token usage, cost report to the GRC API."""
        await self.quota_client.post_quota_usage(tokens_used=used_tokens, cost=cost)

    def schedule_background_report(self, tokens: int, cost: float) -> None:
        """Schedule token usage, cost reporting in background without blocking."""

        def report():
            try:
                asyncio.run(self.send_usage_report(tokens, cost))
                logger.debug(f"Background: Successfully reported {tokens} tokens")
            except RuntimeError as e:
                # Only ignore interpreter shutdown errors - all others are critical
                if "interpreter shutdown" in str(
                    e
                ) or "cannot schedule new futures" in str(e):
                    logger.debug(f"Graceful shutdown: {e}")
                    return
                # FAIL FAST: All non-shutdown runtime errors are critical
                raise QuotaReportingException(
                    tokens=tokens, cost=cost, error=str(e)
                ) from e
            except Exception as e:
                # FAIL FAST: Any reporting failure is critical for governance
                raise QuotaReportingException(
                    tokens=tokens, cost=cost, error=str(e)
                ) from e

        # Use daemon thread for true fire-and-forget behavior
        # This prevents blocking interpreter shutdown
        thread = Thread(target=report, daemon=True)
        thread.start()
        logger.debug(f"Scheduled background report for {tokens} tokens")
