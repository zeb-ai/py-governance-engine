from __future__ import annotations

from ..context import quota_ctx
from ..utils import QuotaExceededException
from .Quota import QuotaClient
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .Quota import Quota


class PreChecker:
    def __init__(self) -> None:
        self.quota_client = QuotaClient()

    async def check_quota(self) -> None:
        """
        Validate that the user has sufficient quota before allowing an LLM API request.

        Fetches current quota from the API if not cached or stale, then checks if remaining quota is positive.
        Raises QuotaExceededException if quota is exhausted, displaying detailed usage information and next steps.
        """
        from ..context import auth_ctx

        current_quota: Quota = quota_ctx.get()

        if current_quota is None or current_quota.need_to_check_usage:
            current_quota = await self.quota_client.get_quota()

        # If continue_to_inference is False, it means quota is exceeded
        if not current_quota.continue_to_inference:
            # For error message
            auth_token = auth_ctx.get()
            domain: str | None = auth_token.domain if auth_token else None

            raise QuotaExceededException(
                used=current_quota.used_quota,
                remaining=current_quota.remaining_quota,
                domain=domain,
            )
