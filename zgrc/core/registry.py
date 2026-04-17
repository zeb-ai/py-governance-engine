import logging
from typing import Dict, List, Optional, Type

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Interceptor(BaseModel):
    """Interceptor metadata model"""

    interceptor_class: Type
    packages_required: List[str]
    is_available: Optional[bool] = None

    class Config:
        arbitrary_types_allowed = True


class InterceptorRegistry:
    """Central registry for all LLM provider interceptors"""

    def __init__(self) -> None:
        self._registry: Dict[str, Interceptor] = {}

    def register(
        self, provider: str, interceptor_class: Type, packages_required: List[str]
    ) -> None:
        """Register an interceptor class for a specific LLM provider with its required packages."""
        if provider in self._registry:
            logger.warning(f"Provider '{provider}' already registered, overwriting")

        self._registry[provider] = Interceptor(
            interceptor_class=interceptor_class,
            packages_required=packages_required,
            is_available=None,
        )
        logger.debug(f"Registered interceptor: {provider}")

    def get(self, provider: str) -> Optional[Type]:
        """Retrieve the registered interceptor class for a given provider name."""
        if provider not in self._registry:
            logger.error(f"Provider '{provider}' not registered")
            return None

        return self._registry[provider].interceptor_class
