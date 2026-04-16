from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict

from .lazy_patcher import LazyPatcher
from .scanner import Scanner

if TYPE_CHECKING:
    from ..interceptors.base_interceptor import BaseInterceptor

logger = logging.getLogger(__name__)


class AutoManager:
    def __init__(self) -> None:
        self._active_interceptors: Dict[str, BaseInterceptor] = {}
        self._patcher: LazyPatcher = LazyPatcher(activation_callback=self.activate)

    def initialize(self) -> None:
        """Scan for installed LLM providers and install detection hooks for lazy activation."""
        installed_providers = Scanner.get_installed_providers()

        if not installed_providers:
            logger.warning("No LLM SDK packages detected")
            return

        # installing hooks
        self._patcher.install_hooks()
        logger.debug(f"GRC ready - will auto-activate for: {installed_providers}")

    def activate(self, provider: str) -> None:
        """Activate the interceptor from the registry."""
        if provider in self._active_interceptors:
            logger.debug(f"{provider} interceptor already active")
            return

        try:
            # Import here to avoid circular import
            from . import interceptor_registry

            interceptor_class = interceptor_registry.get(provider)

            if not interceptor_class:
                logger.error(f"No interceptor registered for {provider}")
                return

            interceptor = interceptor_class()
            interceptor.init()
            self._active_interceptors[provider] = interceptor

            logger.debug(f"{provider} interceptor activated")
        except Exception as e:
            logger.error(f"Failed to activate {provider}: {e}", exc_info=True)

    def disable_all(self) -> None:
        """Disable all active interceptors and restore original SDK behavior."""
        for provider, interceptor in self._active_interceptors.items():
            try:
                interceptor.disable()
                logger.debug(f"Disabled {provider} interceptor")
            except Exception as e:
                logger.error(f"Failed to disable {provider}: {e}")

        self._active_interceptors.clear()
