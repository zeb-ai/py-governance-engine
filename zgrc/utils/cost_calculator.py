import logging
from typing import Optional

from litellm import completion_cost

logger = logging.getLogger(__name__)


def calculate_cost_from_events(events: list, model_id: str) -> Optional[float]:
    """Calculate cost from Bedrock streaming response events using litellm's completion_cost."""
    try:
        # Extract tokens from correct event types
        message_start = next(
            (e["message"]["usage"] for e in events if e.get("type") == "message_start"),
            None,
        )
        message_delta = next(
            (e["usage"] for e in events if e.get("type") == "message_delta"), None
        )

        if not message_start or not message_delta:
            logger.warning("Could not find message_start or message_delta events")
            return None

        # Extract token counts
        input_tokens = message_delta.get("input_tokens", 0)
        output_tokens = message_delta.get("output_tokens", 0)
        cache_read_tokens = message_start.get("cache_read_input_tokens", 0)
        cache_creation_tokens = message_start.get("cache_creation_input_tokens", 0)

        # Build litellm-compatible response structure
        litellm_response = {
            "model": f"bedrock/{model_id}",
            "usage": {
                "prompt_tokens": input_tokens
                + cache_read_tokens
                + cache_creation_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens
                + cache_read_tokens
                + cache_creation_tokens
                + output_tokens,
                "prompt_tokens_details": {"cached_tokens": cache_read_tokens},
                "cache_creation_input_tokens": cache_creation_tokens,
            },
        }

        logger.debug(
            f"Cost calculation for {model_id}: "
            f"input={input_tokens}, output={output_tokens}, "
            f"cache_read={cache_read_tokens}, cache_write={cache_creation_tokens}"
        )

        cost = float(completion_cost(completion_response=litellm_response))

        logger.debug(f"Calculated cost: ${cost:.8f}")

        return cost

    except Exception as e:
        logger.error(f"Cost calculation failed for {model_id}: {e}", exc_info=True)
        return None


class CostCalculationInput:
    pass


class calculate_cost:
    pass
