import asyncio
import logging
from threading import Thread

from .Quota import QuotaClient

logger = logging.getLogger(__name__)


class PostChecker:
    def __init__(self) -> None:
        self.quota_client = QuotaClient()

    async def send_usage_report(self, used_tokens: int) -> None:
        """Send token usage report to the GRC API to update quota consumption."""
        await self.quota_client.post_quota_usage(used_tokens)

    def schedule_background_report(self, tokens: int) -> None:
        """Schedule token usage reporting in background without blocking."""

        def report():
            try:
                asyncio.run(self.send_usage_report(tokens))
                logger.debug(f"Background: Successfully reported {tokens} tokens")
            except Exception as e:
                logger.error(f"Background reporting failed: {e}", exc_info=True)

        # Use non-daemon thread so it completes even if main program exits
        thread = Thread(target=report, daemon=False)
        thread.start()
        logger.debug(f"Scheduled background report for {tokens} tokens")
