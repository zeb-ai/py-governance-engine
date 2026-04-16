# For docs
"""
GRC: Governance, Risk, and Compliance monitoring for LLM applications.
Automatically intercepts, validates and enforces policies on AI model interactions in real-time.
btw its created by zeb labs team
"""

import logging
from typing import Optional

from .auth import AuthToken
from .context import auth_ctx
from .observability import instrument

logger = logging.getLogger(__name__)


class GRC:
    def init(
        self,
        api_key: str,
        auto_instrument: bool = False,
        app_name: Optional[str] = None,
        environment: Optional[str] = None,
        log_level: int = logging.ERROR,
    ) -> None:
        """
        Initialize GRC with optional auto-instrumentation.

        Args:
            api_key            :  GRC API key for authentication and authorization
            auto_instrument    :  Enable automatic instrumentation of frameworks (default: False)
            app_name           :  Application name for resource attributes
            environment        :  Deployment environment (dev/staging/prod)
            log_level          :  Logging level for GRC internal logs (default: ERROR)
        """
        from .core import auto_manager

        # logging configuration
        GRC._config_grc_logger(log_level)

        # api token decoding and storing in context vars
        auth_token = AuthToken.decode(api_key)
        auth_ctx.set(auth_token)

        # llm observability instrumentation (with optional auto-instrumentation)
        instrument(
            auto_instrument=auto_instrument,
            app_name=app_name or "",
            environment=environment or "",
        )

        # registering interceptors to registry
        self._register_interceptors()

        # Initialize AutoManager with hooks
        auto_manager.initialize()
        logger.info("GRC initialized successfully")

    @staticmethod
    def teardown() -> None:
        """Disable all active interceptors and clear context variables to clean up GRC state."""
        from grc.core import auto_manager
        from grc.context import auth_ctx, quota_ctx

        auto_manager.disable_all()

        auth_ctx.set(None)
        quota_ctx.set(None)

    @staticmethod
    def _config_grc_logger(level: int) -> logging.Logger:
        """Configure GRC's internal logger with specified level and formatting."""
        grc_logger = logging.getLogger("grc")

        if not grc_logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                fmt="[%(name)s] %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            grc_logger.addHandler(handler)
            grc_logger.setLevel(level)

        return grc_logger

    @staticmethod
    def _register_interceptors():
        """
        Scan for installed LLM provider SDKs and register their interceptors.
        Detects which provider packages are installed and dynamically
        imports their interceptor modules to register them with the interceptor registry.
        """
        from grc.core.scanner import Scanner
        from grc.providers import Providers

        installed_providers = Scanner.get_installed_providers()
        logger.info(f"Discovered providers: {installed_providers}")

        for provider in installed_providers:
            logger.debug(f"Attempting to register: {provider}")
            try:
                if provider == Providers.BEDROCK:
                    import grc.interceptors.bedrock  # noqa: F401

                    logger.debug(f"Successfully registered {provider} interceptor")
                elif provider == Providers.ANTHROPIC:  # TODO: Not implemented yet
                    logger.debug(f"Skipping {provider} - not implemented yet")
                elif provider == Providers.OPENAI:  # TODO: Not implemented yet
                    logger.debug(f"Skipping {provider} - not implemented yet")
                elif provider == Providers.AZURE:  # TODO: Not implemented yet
                    logger.debug(f"Skipping {provider} - not implemented yet")
                else:
                    logger.debug(f"Skipping {provider} - not implemented yet")
            except ImportError as e:
                logger.warning(f"Failed to import {provider} interceptor: {e}")


grc = GRC()

# just only for easy import
init = grc.init
teardown = grc.teardown

__all__ = ["grc", "init", "teardown"]
