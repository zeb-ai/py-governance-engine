import logging
from typing import Optional

from litellm import cost_per_token
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CostCalculationInput(BaseModel):
    """Input model for cost calculation."""

    model_id: str
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    provider: str

    @property
    def litellm_model_id(self) -> str:
        """Get formatted model ID for LiteLLM."""
        if self.provider == "bedrock":
            return f"bedrock/{self.model_id}"
        return self.model_id


def calculate_cost(data: CostCalculationInput) -> Optional[float]:
    """Calculate total cost using LiteLLM - only for calculate token not to inference / intercepting."""
    try:
        input_cost, output_cost = cost_per_token(
            model=data.litellm_model_id,
            prompt_tokens=data.input_tokens,
            completion_tokens=data.output_tokens,
            cache_read_input_tokens=data.cache_read_input_tokens,
            cache_creation_input_tokens=data.cache_creation_input_tokens,
        )

        total_cost = input_cost + output_cost
        logger.debug(f"Cost for {data.litellm_model_id}: ${total_cost:.6f}")

        return total_cost

    except Exception as e:
        logger.warning(f"Cost calculation failed for {data.litellm_model_id}: {e}")
        return None
