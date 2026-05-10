from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Iterator, Optional

from ..base_response_handler import BaseResponseHandler
from ..models import TokenUsage

if TYPE_CHECKING:
    from ..base_interceptor import BaseInterceptor

logger = logging.getLogger(__name__)


class ChatCompletionHandler(BaseResponseHandler):
    """Handler for non-streaming OpenAI chat completions"""

    def can_handle(self, operation_name: str) -> bool:
        """Check if this handler can process chat completion operations."""
        return operation_name == "chat.completions.create"

    def process_response(
        self,
        response: Any,
        interceptor_instance: BaseInterceptor,
        request_data=None,
    ) -> tuple[Optional[str], TokenUsage, Any]:
        """Extract token usage from OpenAI ChatCompletion response."""
        try:
            logger.debug("Processing ChatCompletion response (non-streaming)")

            # Extract model ID from response
            model_id = getattr(response, "model", None)

            # Extract usage from response
            usage_obj = getattr(response, "usage", None)
            if usage_obj:
                usage_dict = {
                    "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0),
                    "completion_tokens": getattr(usage_obj, "completion_tokens", 0),
                    "total_tokens": getattr(usage_obj, "total_tokens", 0),
                }

                # Handle prompt_tokens_details if present (cache tokens)
                prompt_details = getattr(usage_obj, "prompt_tokens_details", None)
                if prompt_details:
                    usage_dict["cache_read_input_tokens"] = getattr(
                        prompt_details, "cached_tokens", 0
                    )

                # Handle completion_tokens_details if present
                completion_details = getattr(
                    usage_obj, "completion_tokens_details", None
                )
                if completion_details:
                    # OpenAI doesn't have cache creation tokens in the same way
                    pass

                logger.debug(f"Usage data: {usage_dict}")

                usage = TokenUsage(
                    input_tokens=usage_dict.get("prompt_tokens", 0),
                    output_tokens=usage_dict.get("completion_tokens", 0),
                    cache_read_input_tokens=usage_dict.get(
                        "cache_read_input_tokens", 0
                    ),
                )

                logger.debug(
                    f"Extracted tokens: input={usage.input_tokens}, "
                    f"output={usage.output_tokens}, total={usage.total_tokens}"
                )

                return model_id, usage, response

            logger.warning("No usage data found in response")
            return model_id, TokenUsage(), response

        except Exception as e:
            logger.error(f"Error extracting usage from response: {e}", exc_info=True)
            return None, TokenUsage(extraction_error=str(e)), response


class ChatCompletionStreamHandler(BaseResponseHandler):
    """Handler for streaming OpenAI chat completions"""

    def can_handle(self, operation_name: str) -> bool:
        """Check if this handler can process streaming operations."""
        return operation_name == "chat.completions.create.stream"

    def process_response(
        self,
        response: Any,
        interceptor_instance: BaseInterceptor,
        request_data=None,
    ) -> tuple[Optional[str], TokenUsage, Any]:
        """Wrap streaming response to capture tokens as they arrive."""
        logger.debug("Processing ChatCompletion response (streaming)")

        # Wrap the stream iterator
        wrapped_stream = StreamingResponseWrapper(
            response, interceptor_instance, request_data
        )

        # Return early with wrapped stream - usage will be collected as stream is consumed
        return None, TokenUsage(), wrapped_stream


class StreamingResponseWrapper:
    """
    Wraps OpenAI streaming response to capture token usage after stream completes.
    """

    def __init__(
        self,
        stream: Iterator,
        interceptor_instance: BaseInterceptor,
        request_data=None,
    ):
        self._stream = stream
        self._interceptor = interceptor_instance
        self._request_data = request_data
        self._usage = TokenUsage()
        self._model_id: Optional[str] = None
        self._chunks_collected = []

    def __iter__(self):
        return self

    def __next__(self):
        try:
            chunk = next(self._stream)
            self._chunks_collected.append(chunk)

            # Capture model ID from first chunk
            if self._model_id is None and hasattr(chunk, "model"):
                self._model_id = chunk.model
                logger.debug(f"Captured model ID from stream: {self._model_id}")

            # Check if this chunk has usage information (typically in final chunk)
            if hasattr(chunk, "usage") and chunk.usage is not None:
                usage_obj = chunk.usage
                self._usage = TokenUsage(
                    input_tokens=getattr(usage_obj, "prompt_tokens", 0),
                    output_tokens=getattr(usage_obj, "completion_tokens", 0),
                    cache_read_input_tokens=getattr(
                        getattr(usage_obj, "prompt_tokens_details", None),
                        "cached_tokens",
                        0,
                    )
                    if hasattr(usage_obj, "prompt_tokens_details")
                    else 0,
                )
                logger.debug(f"Captured usage from stream: {self._usage}")

            return chunk

        except StopIteration:
            # Stream completed - report usage if we have it
            if self._usage.total_tokens > 0:
                logger.debug(f"Stream completed with {self._usage.total_tokens} tokens")
                # Note: Cost calculation and reporting will happen in the main interceptor
                # after we return the model_id
            raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Stream context exited
        pass

    @property
    def usage(self) -> TokenUsage:
        """Get accumulated usage after stream completes."""
        return self._usage

    @property
    def model_id(self) -> Optional[str]:
        """Get model ID captured from stream."""
        return self._model_id


class ResponseHandlerFactory:
    """Factory to get the appropriate response handler based on operation type."""

    _handlers = [
        ChatCompletionHandler(),
        ChatCompletionStreamHandler(),
    ]

    @classmethod
    def get_handler(cls, operation_name: str) -> Optional[BaseResponseHandler]:
        """Get handler that can process the given operation."""
        for handler in cls._handlers:
            if handler.can_handle(operation_name):
                return handler
        return None
