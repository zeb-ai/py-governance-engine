import asyncio
import logging
from threading import Thread

from .Quota import QuotaClient

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
                # Silently ignore interpreter shutdown errors - it's expected during cleanup
                if "interpreter shutdown" not in str(
                    e
                ) and "cannot schedule new futures" not in str(e):
                    logger.error(f"Background reporting failed: {e}")
            except Exception as e:
                # Log other errors but don't crash
                logger.debug(f"Background reporting failed: {e}")

        # Use daemon thread for true fire-and-forget behavior
        # This prevents blocking interpreter shutdown
        thread = Thread(target=report, daemon=True)
        thread.start()
        logger.debug(f"Scheduled background report for {tokens} tokens")
