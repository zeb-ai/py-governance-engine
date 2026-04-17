from __future__ import annotations

from contextvars import ContextVar
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .auth import AuthToken
    from .policy import Quota

auth_ctx: ContextVar[Optional[AuthToken]] = ContextVar("auth_ctx", default=None)
quota_ctx: ContextVar[Optional[Quota]] = ContextVar("quota_ctx", default=None)
