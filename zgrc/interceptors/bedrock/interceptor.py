from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, Tuple

import botocore.endpoint
from opentelemetry import context, trace

from ...observability import logs, metrics, traces
from ...observability.logs import LogsConfig
from ...providers import Providers
from ...utils.cost_calculator import CostCalculationInput, calculate_cost
from ...utils.exceptions import QuotaExceededException
from ...utils.model_resolver import resolve_model_id_from_url
from ..base_interceptor import BaseInterceptor
from ..models import InterceptedCall, RequestData, ResponseData
from .response_handlers import ResponseHandlerFactory

if TYPE_CHECKING:
    from opentelemetry.trace import Span, Tracer

logger = logging.getLogger(__name__)


class BedrockInterceptor(BaseInterceptor):
    """Bedrock API interceptor with async quota management"""

    BEDROCK_RUNTIME = "bedrock-runtime"

    async def process_bedrock_request(
        self,
        request_dict: Dict[str, Any],
        operation_model: Any,
        original_call: Callable[[], Tuple[Any, Any]],
    ) -> Tuple[Any, Any]:
        """
        Process a Bedrock API request with quota validation, observability instrumentation, and token tracking.

        This method wraps the original Bedrock API call to perform pre-request quota checks, create tracing spans,
        execute the request, extract token usage from responses (including streaming), report usage metrics, emit
        logs, and handle errors. It delegates response processing to specialized handlers based on the operation type.
        """
        operation_name: str = operation_model.name if operation_model else "unknown"

        request_data: RequestData = self._capture_request(request_dict, operation_model)

        span: Span | None = None
        tracer: Tracer | None = traces.tracer if traces else None
        token: Any = None
        if tracer:
            span = tracer.start_span(
                f"bedrock.{operation_name}",
                attributes={
                    "llm.provider": "bedrock",
                    "llm.model": request_data.model_id,
                    "llm.operation": operation_name,
                },
            )
            ctx = trace.set_span_in_context(span)
            token = context.attach(ctx)

        try:
            await self.pre_request_check()
            logger.debug(f"Quota check passed for {operation_name}")

        except QuotaExceededException:
            if span:
                span.set_status(trace.Status(trace.StatusCode.ERROR, "Quota exceeded"))
                span.end()
                if token:
                    context.detach(token)
            raise
        except Exception as e:
            logger.error(f"Pre-checker failed: {e}", exc_info=True)
            if span:
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                span.end()
                if token:
                    context.detach(token)
            raise

        # Make the actual request (run sync code in executor)
        loop = asyncio.get_event_loop()
        response_tuple = await loop.run_in_executor(None, original_call)

        # POST-REQUEST: Process response and report usage
        try:
            handler = ResponseHandlerFactory.get_handler(operation_name)

            if not handler:
                logger.warning(f"No handler for operation: {operation_name}")
                return response_tuple

            response_json, usage, response_tuple = handler.process_response(
                response_tuple, self
            )

            # Skip if no data extracted
            if response_json is None and usage.total_tokens == 0:
                return response_tuple

            # calculate cost from the tokens
            resolved_model_id = await resolve_model_id_from_url(request_data.url)
            if resolved_model_id and usage.total_tokens > 0:
                cost_input = CostCalculationInput(
                    model_id=resolved_model_id,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    cache_read_input_tokens=usage.cache_read_input_tokens,
                    cache_creation_input_tokens=usage.cache_creation_input_tokens,
                    provider=Providers.BEDROCK,
                )
                total_cost = calculate_cost(cost_input)
                if total_cost:
                    usage.total_cost = total_cost
                    logger.debug(f"Calculated cost: ${total_cost:.6f}")

            response_data = ResponseData(
                body=response_json or {},
                usage=usage,
            )

            if usage.total_tokens > 0:
                cost = usage.total_cost if usage.total_cost is not None else 0.0
                self.post_request_report(usage.total_tokens, cost)
                logger.debug(
                    f"Scheduled background report for {usage.total_tokens} tokens"
                )

            self.calls.append(
                InterceptedCall(request=request_data, response=response_data)
            )

            # Add token and cost attributes to span
            if span:
                span.set_attributes(
                    {
                        "llm.tokens.input": usage.input_tokens,
                        "llm.tokens.output": usage.output_tokens,
                        "llm.tokens.total": usage.total_tokens,
                        "llm.tokens.cache_read": usage.cache_read_input_tokens,
                        "llm.tokens.cache_creation": usage.cache_creation_input_tokens,
                        "llm.cost.total": usage.total_cost,
                    }
                )

            # Record metrics
            if metrics:
                metrics.set_tokens(
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    attributes={
                        "model": resolved_model_id or request_data.model_id,
                        "provider": "bedrock",
                        "operation": operation_name,
                        "cost": usage.total_cost,
                    },
                )

            if logs:
                from threading import Thread

                log_config = LogsConfig(
                    provider=Providers.BEDROCK,
                    model_id=resolved_model_id or request_data.model_id,
                    operation=operation_name,
                    request=request_data.body,
                    response=response_json or {},
                    usage={
                        "input_tokens": usage.input_tokens,
                        "output_tokens": usage.output_tokens,
                        "total_tokens": usage.total_tokens,
                        "cache_read_input_tokens": usage.cache_read_input_tokens,
                        "cache_creation_input_tokens": usage.cache_creation_input_tokens,
                        "total_cost": usage.total_cost,
                    },
                )
                thread = Thread(target=logs.send, args=(log_config,), daemon=False)
                thread.start()

        except Exception as e:
            logger.error(f"Error processing response: {e}", exc_info=True)
            if span:
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            if request_data:
                response_data = ResponseData(
                    error=str(e), exception_type=type(e).__name__
                )
                self.calls.append(
                    InterceptedCall(request=request_data, response=response_data)
                )
        finally:
            # End span and detach context
            if span:
                span.end()
                context.detach(token)

        return response_tuple

    def init(self) -> None:
        """Enable the interceptor by patching botocore's endpoint make_request method."""
        if self._original_method is None:
            self._original_method = botocore.endpoint.Endpoint.make_request

            interceptor_instance = self
            original_method = self._original_method

            def patched_make_request(endpoint_self, operation_model, request_dict):
                """Thin sync wrapper - bridges to async logic"""

                url = request_dict.get("url", "")

                # Check if this is a Bedrock request
                if interceptor_instance.BEDROCK_RUNTIME not in url:
                    return original_method(endpoint_self, operation_model, request_dict)

                # Bridge to async processing
                try:
                    # Create callable for original request
                    def original_call():
                        return original_method(
                            endpoint_self, operation_model, request_dict
                        )

                    # Try to get existing event loop
                    try:
                        loop = asyncio.get_running_loop()
                        # Loop is running - use run_coroutine_threadsafe
                        future = asyncio.run_coroutine_threadsafe(
                            interceptor_instance.process_bedrock_request(
                                request_dict, operation_model, original_call
                            ),
                            loop,
                        )
                        return future.result()
                    except RuntimeError:
                        # No running loop - create new one with asyncio.run()
                        return asyncio.run(
                            interceptor_instance.process_bedrock_request(
                                request_dict, operation_model, original_call
                            )
                        )

                except QuotaExceededException:
                    raise
                except Exception as e:
                    logger.error(f"Interceptor error: {e}", exc_info=True)
                    raise

            botocore.endpoint.Endpoint.make_request = patched_make_request
            logger.info("Bedrock interceptor enabled")

    def disable(self) -> None:
        """Disable the interceptor and restore original botocore behavior."""
        if self._original_method is not None:
            botocore.endpoint.Endpoint.make_request = self._original_method
            self._original_method = None
            logger.info("GRC2::: Bedrock interceptor disabled")

    @staticmethod
    def _capture_request(
        request_dict: Dict[str, Any], operation_model: Any
    ) -> RequestData:
        """Extract and parse request details from botocore request dictionary."""
        try:
            body = request_dict.get("body", b"")
            body = body.decode("utf-8") if isinstance(body, bytes) else body
            body_json = json.loads(body) if body else {}

            return RequestData(
                operation=operation_model.name,
                model_id=request_dict.get("url", "").split("/")[-1],
                body=body_json,
                headers=dict(request_dict.get("headers", {})),
                url=request_dict.get("url", ""),
            )
        except Exception as e:
            return RequestData(
                operation=operation_model.name if operation_model else "unknown",
                model_id="unknown",
                url=request_dict.get("url", ""),
                error=f"Failed to capture request: {e}",
            )
