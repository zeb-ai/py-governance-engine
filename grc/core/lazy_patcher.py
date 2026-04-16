import functools
import logging
from typing import Any, Callable

from grc.providers import Providers

logger = logging.getLogger(__name__)


class LazyPatcher:
    def __init__(self, activation_callback: Callable[[str], None]) -> None:
        self._activation_callback: Callable[[str], None] = activation_callback
        self._hooks_installed: bool = False

    def install_hooks(self) -> None:
        """Install lightweight detection hooks for all LLM provider SDKs to enable lazy activation."""
        if self._hooks_installed:
            logger.debug("Hooks already installed")
            return

        self._hook_boto3()
        self._hook_anthropic()
        self._hook_openai()
        self._hook_azure()

        self._hooks_installed = True
        logger.debug("Detection hooks installed")

    def _hook_boto3(self) -> None:
        """
        Hook boto3.client() and botocore.session.create_client() to detect Bedrock usage.

        Wraps both boto3.client() and botocore's internal session.create_client() method to intercept
        client creation. When a bedrock-runtime or bedrock service is requested, triggers the activation
        callback to initialize the Bedrock interceptor before returning the client.
        """
        try:
            import boto3
            import botocore.session

            # Hook boto3.client()
            original_client = boto3.client

            @functools.wraps(original_client)
            def hooked_client(*args: Any, **kwargs: Any) -> Any:
                service_name = args[0] if args else kwargs.get("service_name")
                logger.debug(
                    f"[HOOK] boto3.client() called with service: {service_name}"
                )

                client = original_client(*args, **kwargs)

                if service_name is not None and "bedrock" in service_name.lower():
                    logger.debug(
                        "[HOOK] Detected Bedrock client - activating interceptor"
                    )
                    self._activation_callback(Providers.BEDROCK)

                return client

            boto3.client = hooked_client

            # ALSO hook botocore.session.Session.create_client() for deeper coverage
            original_session_create_client = botocore.session.Session.create_client

            @functools.wraps(original_session_create_client)
            def hooked_session_create_client(
                session_self: Any, *args: Any, **kwargs: Any
            ) -> Any:
                service_name = args[0] if args else kwargs.get("service_name")
                logger.debug(
                    f"[HOOK] botocore.session.create_client() called with service: {service_name}"
                )

                client = original_session_create_client(session_self, *args, **kwargs)

                if service_name is not None and "bedrock" in service_name.lower():
                    logger.debug(
                        "[HOOK] Detected Bedrock client via botocore - activating interceptor"
                    )
                    self._activation_callback(Providers.BEDROCK)

                return client

            botocore.session.Session.create_client = hooked_session_create_client

            logger.debug("Installed boto3.client() and botocore.session hooks")

        except ImportError:
            logger.debug("boto3 not installed, skipping hook")

    def _hook_anthropic(self) -> None: ...

    def _hook_openai(self) -> None: ...

    def _hook_azure(self) -> None: ...
