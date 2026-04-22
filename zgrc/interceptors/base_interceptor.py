from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import InterceptedCall

from ..policy import PreChecker
from ..policy import PostChecker

logger = logging.getLogger(__name__)


class BaseInterceptor(ABC):
    """Abstract base class for intercepting LLM API calls"""

    def __init__(self) -> None:
        self.calls: List[InterceptedCall] = []
        self._original_method: Any = None
        self.pre_checker: PreChecker = PreChecker()
        self.post_checker: PostChecker = PostChecker()

    @abstractmethod
    def init(self) -> None:
        """Initialize and enable the interceptor by patching the API client"""
        pass

    @abstractmethod
    def disable(self) -> None:
        """Disable the interceptor and restore original behavior"""
        pass

    def clear(self) -> None:
        """Clear all captured API calls from memory."""
        self.calls.clear()

    async def pre_request_check(self) -> None:
        """Validate user quota before allowing the LLM API request to proceed."""
        await self.pre_checker.check_quota()
        logger.debug("Pre-request quota check passed")

    def post_request_report(self, tokens: int, cost: float) -> None:
        """Report token usage and cost to the GRC API after request completion."""
        self.post_checker.schedule_background_report(tokens=tokens, cost=cost)
        logger.debug(f"Reported {tokens} tokens, ${cost:.6f} to API")
