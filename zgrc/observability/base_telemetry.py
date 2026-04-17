from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from opentelemetry.sdk.resources import Resource

from ..context import auth_ctx

if TYPE_CHECKING:
    from ..auth import AuthToken


class BaseTelemetry(ABC):
    def __init__(self) -> None:
        self.ctx: AuthToken | None = auth_ctx.get()
        if self.ctx is None:
            raise RuntimeError("API is corrupted, please provide an proper API key")

        self.resource: Resource = Resource.create(
            {
                "user_id": self.ctx.user_id,
                "policy_id": self.ctx.policy_id,
                "project_id": self.ctx.project_id,
            }
        )
        self.log_endpoint: str = self.ctx.opentelemetry

    @abstractmethod
    def setup(self) -> None:
        """Setup for telemetry data"""
        ...

    @abstractmethod
    def send(self, *args, **kwargs):
        """Send telemetry data"""
        ...
