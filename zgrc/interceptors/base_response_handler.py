from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, Optional, Tuple

if TYPE_CHECKING:
    from .models import TokenUsage


class BaseResponseHandler(ABC):
    """Base handler for Bedrock API responses"""

    @abstractmethod
    def can_handle(self, operation_name: str) -> bool:
        """Check if this handler can process the given operation"""
        pass

    @abstractmethod
    def process_response(
        self, response_tuple: Tuple, interceptor_instance
    ) -> Tuple[Optional[Dict], TokenUsage, Tuple]:
        """Process response and extract token usage"""
        pass
