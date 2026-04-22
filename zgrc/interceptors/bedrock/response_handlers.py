from __future__ import annotations

import json
import logging
from io import BytesIO
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

import botocore.eventstream

from ..base_response_handler import BaseResponseHandler
from ..models import TokenUsage

if TYPE_CHECKING:
    from ..base_interceptor import BaseInterceptor

logger = logging.getLogger(__name__)


class InvokeModelHandler(BaseResponseHandler):
    """Handler for InvokeModel API (streaming body response)"""

    def can_handle(self, operation_name: str) -> bool:
        """Check if this handler can process InvokeModel operations."""
        return operation_name == "InvokeModel"

    def process_response(
        self,
        response_tuple: Tuple[Any, Any],
        interceptor_instance: BaseInterceptor,
        request_data=None,
    ) -> Tuple[Optional[Dict[str, Any]], TokenUsage, Tuple[Any, Any]]:
        """Read and parse the streaming body response, extract token usage, and return reconstructed response tuple."""
        http_response, parsed_response = response_tuple

        body = (
            parsed_response.get("body") if isinstance(parsed_response, dict) else None
        )

        if body and hasattr(body, "read"):
            logger.debug("Processing InvokeModel response (streaming body)")
            body_content = body.read()
            parsed_response["body"] = BytesIO(body_content)
            response_tuple = (http_response, parsed_response)

            body_content = (
                body_content.decode("utf-8")
                if isinstance(body_content, bytes)
                else body_content
            )
            response_json = json.loads(body_content) if body_content else {}

            logger.debug(f"Response keys: {list(response_json.keys())}")
            if "usage" in response_json:
                logger.debug(f"Usage data: {response_json['usage']}")

            usage = self._extract_token_usage(response_json)
            logger.debug(
                f"Extracted tokens: input={usage.input_tokens}, "
                f"output={usage.output_tokens}, total={usage.total_tokens}"
            )

            return response_json, usage, response_tuple

        return None, TokenUsage(), response_tuple

    @staticmethod
    def _extract_token_usage(response_json: Dict[str, Any]) -> TokenUsage:
        """Extract token usage from InvokeModel response JSON."""
        if "usage" in response_json:
            return TokenUsage.from_usage_dict(
                response_json["usage"], key_format="snake_case"
            )
        return TokenUsage()


class ConverseHandler(BaseResponseHandler):
    """Handler for Converse API (non-streaming, already parsed)"""

    def can_handle(self, operation_name: str) -> bool:
        """Check if this handler can process Converse operations."""
        return operation_name == "Converse"

    def process_response(
        self, response_tuple: Tuple, interceptor_instance, request_data=None
    ) -> Tuple[Optional[Dict], TokenUsage, Tuple]:
        """Extract token usage from already-parsed Converse API response."""
        http_response, parsed_response = response_tuple

        if isinstance(parsed_response, dict) and "stream" not in parsed_response:
            logger.debug("Processing Converse response (already parsed)")
            response_json = parsed_response

            logger.debug(f"Response keys: {list(response_json.keys())}")
            if "usage" in response_json:
                logger.debug(f"Usage data: {response_json['usage']}")

            usage = self._extract_token_usage(response_json)
            logger.debug(
                f"Extracted tokens: input={usage.input_tokens}, "
                f"output={usage.output_tokens}, total={usage.total_tokens}"
            )

            return response_json, usage, response_tuple

        return None, TokenUsage(), response_tuple

    @staticmethod
    def _extract_token_usage(response_json: Dict[str, str]) -> TokenUsage:
        """Extract token usage from Converse response JSON (camelCase format)."""
        if "usage" in response_json:
            # why camelCase :  Converse API uses camelCase (inputTokens, outputTokens)
            return TokenUsage.from_usage_dict(
                response_json["usage"], key_format="camelCase"
            )
        return TokenUsage()


class ConverseStreamHandler(BaseResponseHandler):
    """Handler for ConverseStream API (streaming EventStream)"""

    def can_handle(self, operation_name: str) -> bool:
        """Check if this handler can process ConverseStream operations."""
        return operation_name == "ConverseStream"

    def process_response(
        self, response_tuple: Tuple, interceptor_instance, request_data=None
    ) -> Tuple[Optional[Dict], TokenUsage, Tuple]:
        """Wrap the EventStream with token tracking to capture usage from metadata events."""
        http_response, parsed_response = response_tuple

        if isinstance(parsed_response, dict) and "stream" in parsed_response:
            stream = parsed_response.get("stream")
            if isinstance(stream, botocore.eventstream.EventStream):
                logger.debug("Processing ConverseStream response (streaming)")

                # Wrap the stream to capture token usage, passing request URL
                request_url = request_data.url if request_data else None
                wrapped_stream = TokenTrackingEventStream(
                    stream, interceptor_instance, request_url
                )
                parsed_response["stream"] = wrapped_stream
                response_tuple = (http_response, parsed_response)

                logger.info("GRC::: Wrapped streaming response for token tracking")

                # Return early - token tracking happens asynchronously as stream is consumed
                return None, TokenUsage(), response_tuple

        return None, TokenUsage(), response_tuple


class InvokeModelWithResponseStreamHandler(BaseResponseHandler):
    """Handler for InvokeModelWithResponseStream API (streaming body response)"""

    def can_handle(self, operation_name: str) -> bool:
        """Check if this handler can process InvokeModelWithResponseStream operations."""
        return operation_name == "InvokeModelWithResponseStream"

    def process_response(
        self, response_tuple: Tuple, interceptor_instance, request_data=None
    ) -> Tuple[Optional[Dict], TokenUsage, Tuple]:
        """Wrap the streaming body EventStream with token tracking to capture usage from chunks."""
        http_response, parsed_response = response_tuple

        body = (
            parsed_response.get("body") if isinstance(parsed_response, dict) else None
        )

        if body and isinstance(body, botocore.eventstream.EventStream):
            logger.debug(
                "Processing InvokeModelWithResponseStream response (streaming body)"
            )

            # Wrap the stream to capture token usage, passing request URL
            request_url = request_data.url if request_data else None
            wrapped_stream = StreamingBodyTokenTracker(
                body, interceptor_instance, request_url
            )
            parsed_response["body"] = wrapped_stream
            response_tuple = (http_response, parsed_response)

            logger.info("Wrapped streaming body response for token tracking")

            return None, TokenUsage(), response_tuple

        return None, TokenUsage(), response_tuple


class StreamingBodyTokenTracker:
    """Wrapper around EventStream for InvokeModelWithResponseStream that captures token usage"""

    def __init__(
        self,
        stream: Any,
        interceptor_instance: BaseInterceptor,
        request_url: str = None,
    ) -> None:
        self._stream: Any = stream
        self._interceptor: BaseInterceptor = interceptor_instance
        self._usage: TokenUsage = TokenUsage()
        self._events: list = []  # Store all events
        self._operation_name = "InvokeModelWithResponseStream"
        self._request_url = request_url  # Store URL for cost calculation

    def __iter__(self):
        """Iterate through stream chunks, parse JSON data, extract token usage, and report after completion."""
        for event in self._stream:
            if isinstance(event, dict) and "chunk" in event:
                chunk_bytes = event["chunk"].get("bytes", b"")
                if chunk_bytes:
                    try:
                        chunk_data = json.loads(chunk_bytes.decode("utf-8"))
                        self._events.append(chunk_data)  # Store event

                        usage = self._extract_token_usage(chunk_data)
                        if usage.total_tokens > 0:
                            self._usage = TokenUsage(
                                input_tokens=self._usage.input_tokens
                                + usage.input_tokens,
                                output_tokens=self._usage.output_tokens
                                + usage.output_tokens,
                            )
                            logger.debug(
                                f"Found usage in stream chunk: {usage.total_tokens} tokens"
                            )
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        logger.debug(f"Could not parse chunk JSON: {e}")

            yield event

        if self._usage.total_tokens > 0:
            self._update_policy(self._usage)

    @staticmethod
    def _extract_token_usage(chunk_data: Dict) -> TokenUsage:
        """Extract token usage from stream chunk JSON supporting both snake_case and camelCase formats."""
        if "usage" in chunk_data:
            usage = chunk_data["usage"]
            if "input_tokens" in usage:
                return TokenUsage.from_usage_dict(usage, key_format="snake_case")
            if "inputTokens" in usage:
                return TokenUsage.from_usage_dict(
                    usage, key_format="camelCase"
                )  # camelCase (Amazon models)

        if "inputTokens" in chunk_data and "outputTokens" in chunk_data:
            return TokenUsage.from_usage_dict(chunk_data, key_format="camelCase")

        return TokenUsage()

    def _update_policy(self, usage: TokenUsage):
        """Schedule background reporting of token usage and cost after stream completes."""
        try:
            # Calculate cost from collected events
            cost = 0.0
            logger.debug(f"Starting cost calculation for {self._operation_name}")
            logger.debug(f"Events collected: {len(self._events)}")

            if self._events:
                from ...utils.cost_calculator import calculate_cost_from_events
                from ...utils.model_resolver import resolve_model_id_from_url
                from . import interceptor
                import asyncio

                # Use stored URL instead of trying to get it from calls
                url = self._request_url
                if url:
                    logger.debug(f"Request URL: {url}")

                    # Resolve model ID synchronously using asyncio.run
                    try:
                        model_id = asyncio.run(resolve_model_id_from_url(url))
                        logger.debug(f"Resolved model_id: {model_id}")
                    except Exception as e:
                        logger.error(f"Failed to resolve model ID: {e}", exc_info=True)
                        model_id = None

                    if model_id:
                        # Transform events to standard format
                        standard_events = interceptor._transform_to_standard_events(
                            {"events": self._events}, self._operation_name
                        )
                        logger.debug(
                            f"Transformed to {len(standard_events)} standard events"
                        )

                        if standard_events:
                            cost = (
                                calculate_cost_from_events(standard_events, model_id)
                                or 0.0
                            )
                            logger.info(
                                f"Calculated cost from streaming events: ${cost}"
                            )
                        else:
                            logger.warning("No standard events after transformation")
                    else:
                        logger.warning("No model_id resolved")
                else:
                    logger.warning("No request URL available")

            self._interceptor.post_request_report(usage.total_tokens, cost)
            logger.debug(
                f"Scheduled background report for {usage.total_tokens} tokens, ${cost:.6f} cost from streaming body"
            )
        except Exception as e:
            logger.error(f"Failed to schedule usage reporting: {e}", exc_info=True)


class TokenTrackingEventStream:
    """Wrapper around EventStream that captures token usage from final metadata event"""

    def __init__(
        self,
        stream: Any,
        interceptor_instance: BaseInterceptor,
        request_url: str = None,
    ) -> None:
        self._stream: Any = stream
        self._interceptor: BaseInterceptor = interceptor_instance
        self._usage: TokenUsage = TokenUsage()
        self._events: list = []  # Store all events
        self._operation_name = "ConverseStream"
        self._request_url = request_url  # Store URL for cost calculation

    def __iter__(self):
        """Iterate through stream events, capture token usage from metadata event, and report after completion."""
        for event in self._stream:
            # Store all events
            self._events.append(event)

            # Check if this is a metadata event with usage
            if isinstance(event, dict) and "metadata" in event:
                metadata = event.get("metadata", {})
                if "usage" in metadata:
                    logger.debug(f"Found usage in stream metadata: {metadata['usage']}")
                    self._usage = self._extract_token_usage(metadata["usage"])

            yield event

        # After stream completes, update policy with captured usage
        if self._usage.total_tokens > 0:
            self._update_policy(self._usage)

    @staticmethod
    def _extract_token_usage(usage_data: Dict[str, Any]) -> TokenUsage:
        """Extract token usage from ConverseStream metadata (camelCase format)."""
        if "inputTokens" in usage_data:
            # ConverseStream uses camelCase
            return TokenUsage.from_usage_dict(usage_data, key_format="camelCase")
        return TokenUsage()

    def _update_policy(self, usage: TokenUsage):
        """Schedule background reporting of token usage and cost after stream completes."""
        try:
            # Calculate cost from collected events
            cost = 0.0
            logger.debug(
                f"[COST_DEBUG] Starting cost calculation for {self._operation_name}"
            )
            logger.debug(f"[COST_DEBUG] Events collected: {len(self._events)}")

            if self._events:
                from ...utils.cost_calculator import calculate_cost_from_events
                from ...utils.model_resolver import resolve_model_id_from_url
                from . import interceptor
                import asyncio

                # Use stored URL instead of trying to get it from calls
                url = self._request_url
                if url:
                    logger.debug(f"[COST_DEBUG] Request URL: {url}")

                    # Resolve model ID synchronously using asyncio.run
                    try:
                        model_id = asyncio.run(resolve_model_id_from_url(url))
                        logger.debug(f"[COST_DEBUG] Resolved model_id: {model_id}")
                    except Exception as e:
                        logger.error(
                            f"[COST_DEBUG] Failed to resolve model ID: {e}",
                            exc_info=True,
                        )
                        model_id = None

                    if model_id:
                        # Transform events to standard format
                        standard_events = interceptor._transform_to_standard_events(
                            {"events": self._events}, self._operation_name
                        )
                        logger.debug(
                            f"[COST_DEBUG] Transformed to {len(standard_events)} standard events"
                        )

                        if standard_events:
                            cost = (
                                calculate_cost_from_events(standard_events, model_id)
                                or 0.0
                            )
                            logger.info(
                                f"[COST_DEBUG] ✓ Calculated cost from streaming events: ${cost:.6f}"
                            )
                        else:
                            logger.warning(
                                "[COST_DEBUG] No standard events after transformation"
                            )
                    else:
                        logger.warning("[COST_DEBUG] No model_id resolved")
                else:
                    logger.warning("[COST_DEBUG] No request URL available")

            self._interceptor.post_request_report(usage.total_tokens, cost)
            logger.debug(
                f"Scheduled background report for {usage.total_tokens} tokens, ${cost:.6f} cost from streaming response"
            )
        except Exception as e:
            logger.error(f"Failed to schedule usage reporting: {e}", exc_info=True)


class ResponseHandlerFactory:
    """Factory to get the appropriate response handler for an operation"""

    _handlers = [
        InvokeModelHandler(),
        InvokeModelWithResponseStreamHandler(),
        ConverseHandler(),
        ConverseStreamHandler(),
    ]

    @classmethod
    def get_handler(cls, operation_name: str) -> Optional[BaseResponseHandler]:
        """Retrieve the appropriate response handler for a given Bedrock operation name."""
        for handler in cls._handlers:
            if handler.can_handle(operation_name):
                return handler

        logger.warning(f"No handler found for operation: {operation_name}")
        return None
