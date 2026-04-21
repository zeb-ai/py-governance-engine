from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from pydantic import BaseModel

from ..client import APIClient
from ..context import auth_ctx, quota_ctx

if TYPE_CHECKING:
    from ..auth import AuthToken


class Quota(BaseModel):
    used_quota: float = 0.0  # Dollar-based tracking instead of tokens
    remaining_quota: float = 0.0  # Dollar-based tracking instead of tokens

    @property
    def need_to_check_usage(self) -> bool:
        """Check if quota usage needs to be fetched from the API (all values are zero initially)."""
        return self.used_quota == 0 and self.remaining_quota == 0

    @property
    def continue_to_inference(self) -> bool:
        """Check if there is remaining quota available to proceed with LLM inference."""
        if self.remaining_quota <= 0:
            return False
        return True


class QuotaClient:
    def __init__(self) -> None:
        self.auth_token: AuthToken = auth_ctx.get()
        self.base_url: str = self.auth_token.domain
        self.client: APIClient = APIClient(base_url=self.base_url)

    async def get_quota(self) -> Quota:
        """Fetch current quota status from the GRC API and update the context."""
        params = {
            "group_id": self.auth_token.group_id,
            "user_id": self.auth_token.user_id,
        }

        response: Dict[str, Any] = await self.client.get(
            "/api/quota/user", params=params
        )
        quota_status = Quota(
            used_quota=response.get("used_quota", 0.0),
            remaining_quota=response.get("remaining_quota", 0.0),
        )
        quota_ctx.set(quota_status)
        return quota_status

    async def post_quota_usage(self, tokens_used: int, cost: float) -> Quota:
        """Report token consumption and cost to the GRC API."""
        body = {
            "user_id": self.auth_token.user_id,
            "policy_id": self.auth_token.group_id,
            "amount": tokens_used,
            "cost": cost,
        }

        response: Dict[str, Any] = await self.client.post(
            "/api/quota/consume", json=body
        )

        quota_status = Quota(
            used_quota=response.get("used_quota", 0.0),
            remaining_quota=response.get("remaining_quota", 0.0),
        )
        quota_ctx.set(quota_status)
        return quota_status
