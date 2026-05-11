from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Callable, Dict

from opentelemetry import context, trace

from ...observability import logs, metrics, traces
from ...observability.logs import LogsConfig
from ...utils.exceptions import CostCalculationException, QuotaExceededException
from ..base_interceptor import BaseInterceptor
from ..models import InterceptedCall, RequestData, ResponseData
from .response_handlers import ResponseHandlerFactory, StreamingResponseWrapper
from ...providers import Providers

if TYPE_CHECKING:
    from opentelemetry.trace import Span, Tracer

logger = logging.getLogger(__name__)


class OpenAIInterceptor(BaseInterceptor):
    """OpenAI API interceptor with async quota management"""

    async def process_openai_request(
        self,
        original_method: Callable,
        args: tuple,
        kwargs: Dict[str, Any],
    ) -> Any:
        """
        Process an OpenAI API request with quota validation, observability instrumentation, and token tracking.

        This method wraps the original OpenAI API call to perform pre-request quota checks, create tracing spans,
        execute the request, extract token usage from responses (including streaming), report usage metrics, emit
        logs, and handle errors.
        """
        # Capture request data
        request_data: RequestData = self._capture_request(kwargs)

        # Determine if streaming
        is_streaming = kwargs.get("stream", False)
        operation_name = (
            "chat.completions.create.stream"
            if is_streaming
            else "chat.completions.create"
        )

        span: Span | None = None
        tracer: Tracer | None = traces.tracer if traces else None
        token: Any = None
        if tracer:
            span = tracer.start_span(
                f"openai.{operation_name}",
                attributes={
                    "llm.provider": "openai",
                    "llm.model": request_data.model_id,
                    "llm.operation": operation_name,
                    "llm.streaming": is_streaming,
                },
            )
            ctx = trace.set_span_in_context(span)
            token = context.attach(ctx)

        try:
            # Pre-request quota check
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
        response = await loop.run_in_executor(
            None, lambda: original_method(*args, **kwargs)
        )

        # POST-REQUEST: Process response and report usage
        try:
            handler = ResponseHandlerFactory.get_handler(operation_name)

            if not handler:
                logger.warning(f"No handler for operation: {operation_name}")
                return response

            # Extract model ID and usage from response
            actual_model_id, usage, processed_response = handler.process_response(
                response, self, request_data
            )

            # For streaming, we need to handle differently
            if is_streaming:
                # Return wrapped stream immediately - usage will be collected later
                # We'll update the interceptor when stream completes
                if isinstance(processed_response, StreamingResponseWrapper):
                    # Store reference for later processing
                    self._pending_stream = {
                        "wrapper": processed_response,
                        "request_data": request_data,
                        "operation_name": operation_name,
                        "span": span,
                        "token": token,
                    }
                return processed_response

            # Non-streaming: process immediately
            # Use actual model from response if available
            resolved_model_id = actual_model_id or request_data.model_id

            # Calculate cost using litellm - CRITICAL: cost tracking is mandatory
            total_cost = 0.0
            if usage.total_tokens > 0:
                try:
                    import litellm

                    # Convert usage to OpenAI format for litellm
                    litellm_response = {
                        "model": resolved_model_id,
                        "usage": {
                            "prompt_tokens": usage.input_tokens,
                            "completion_tokens": usage.output_tokens,
                            "total_tokens": usage.total_tokens,
                        },
                    }
                    total_cost = litellm.completion_cost(
                        completion_response=litellm_response
                    )
                    usage.total_cost = total_cost
                    logger.debug(f"Calculated cost: ${total_cost:.6f}")
                except Exception as e:
                    # FAIL FAST: Cost calculation is mandatory for governance
                    raise CostCalculationException(
                        model_id=resolved_model_id, error=str(e)
                    ) from e

            response_data = ResponseData(
                body={"model": resolved_model_id},
                usage=usage,
                actual_model_id=resolved_model_id if actual_model_id else None,
            )

            # Report usage
            if usage.total_tokens > 0:
                cost = usage.total_cost if usage.total_cost is not None else 0.0
                self.post_request_report(usage.total_tokens, cost)
                logger.debug(
                    f"Scheduled background report for {usage.total_tokens} tokens"
                )

            # Store intercepted call
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
                        "llm.cost.total": usage.total_cost,
                        "llm.model.requested": request_data.model_id,
                        "llm.model.actual": resolved_model_id,
                    }
                )

            # Record metrics
            if metrics:
                metrics.set_tokens(
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    attributes={
                        "model": resolved_model_id,
                        "provider": "openai",
                        "operation": operation_name,
                        "cost": usage.total_cost,
                    },
                )

            # Emit logs
            if logs:
                from threading import Thread

                log_config = LogsConfig(
                    provider=Providers.OPENAI,
                    model_id=resolved_model_id,  # Actual model used
                    operation=operation_name,
                    request=request_data.body,
                    response={"model": resolved_model_id},
                    usage={
                        "input_tokens": usage.input_tokens,
                        "output_tokens": usage.output_tokens,
                        "total_tokens": usage.total_tokens,
                        "cache_read_input_tokens": usage.cache_read_input_tokens,
                        "total_cost": usage.total_cost,
                    },
                    requested_model_id=request_data.model_id,  # Gateway route name
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
            # End span and detach context (only for non-streaming)
            if not is_streaming:
                if span:
                    span.end()
                    if token:
                        context.detach(token)

        return response

    def init(self) -> None:
        """Enable the interceptor by patching OpenAI's chat completions create method."""
        if self._original_method is None:
            try:
                import openai.resources.chat.completions

                self._original_method = (
                    openai.resources.chat.completions.Completions.create
                )

                interceptor_instance = self
                original_method = self._original_method

                def patched_create(self, *args, **kwargs):
                    """Thin sync wrapper - bridges to async logic"""
                    try:
                        # Try to get existing event loop
                        try:
                            loop = asyncio.get_running_loop()
                            # Loop is running - use run_coroutine_threadsafe
                            future = asyncio.run_coroutine_threadsafe(
                                interceptor_instance.process_openai_request(
                                    original_method, (self, *args), kwargs
                                ),
                                loop,
                            )
                            return future.result()
                        except RuntimeError:
                            # No running loop - create new one with asyncio.run()
                            return asyncio.run(
                                interceptor_instance.process_openai_request(
                                    original_method, (self, *args), kwargs
                                )
                            )

                    except QuotaExceededException:
                        raise
                    except Exception as e:
                        logger.error(f"Interceptor error: {e}", exc_info=True)
                        raise

                openai.resources.chat.completions.Completions.create = patched_create
                logger.info("OpenAI interceptor enabled")

            except ImportError as e:
                logger.error(f"Failed to import OpenAI module: {e}")
                raise

    def disable(self) -> None:
        """Disable the interceptor and restore original OpenAI behavior."""
        if self._original_method is not None:
            try:
                import openai.resources.chat.completions

                openai.resources.chat.completions.Completions.create = (
                    self._original_method
                )
                self._original_method = None
                logger.info("OpenAI interceptor disabled")
            except ImportError:
                logger.warning("OpenAI module not available for cleanup")

    @staticmethod
    def _capture_request(kwargs: Dict[str, Any]) -> RequestData:
        """Extract and parse request details from OpenAI API call."""
        try:
            model = kwargs.get("model", "unknown")
            messages = kwargs.get("messages", [])

            return RequestData(
                operation="chat.completions.create",
                model_id=model,
                body={
                    "messages": messages,
                    "stream": kwargs.get("stream", False),
                    "temperature": kwargs.get("temperature"),
                    "max_tokens": kwargs.get("max_tokens"),
                    "top_p": kwargs.get("top_p"),
                },
                headers={},
                url="",  # OpenAI SDK doesn't expose URL at this level
            )
        except Exception as e:
            return RequestData(
                operation="chat.completions.create",
                model_id="unknown",
                url="",
                error=f"Failed to capture request: {e}",
            )
