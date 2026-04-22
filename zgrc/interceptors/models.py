from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, computed_field


class TokenUsage(BaseModel):
    """Token usage information from LLM API calls"""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    total_cost: Optional[float] = None
    extraction_error: Optional[str] = None

    @computed_field
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @classmethod
    def from_usage_dict(
        cls, usage: Dict[str, Any], key_format: str = "snake_case"
    ) -> "TokenUsage":
        """Extract token usage from usage dict (snake_case or camelCase)."""
        if key_format == "snake_case":
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            cache_read = usage.get("cache_read_input_tokens", 0)
            cache_creation = usage.get("cache_creation_input_tokens", 0)

            cache_creation_nested = usage.get("cache_creation", {})
            ephemeral_5m = cache_creation_nested.get("ephemeral_5m_input_tokens", 0)
            ephemeral_1h = cache_creation_nested.get("ephemeral_1h_input_tokens", 0)
        else:
            input_tokens = usage.get("inputTokens", 0)
            output_tokens = usage.get("outputTokens", 0)
            cache_read = usage.get("cacheReadInputTokens", 0)
            cache_creation = usage.get("cacheCreationInputTokens", 0)

            cache_creation_nested = usage.get("cacheCreation", {})
            ephemeral_5m = cache_creation_nested.get("ephemeral5mInputTokens", 0)
            ephemeral_1h = cache_creation_nested.get("ephemeral1hInputTokens", 0)

        total_cache_creation = cache_creation + ephemeral_5m + ephemeral_1h

        return cls(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=total_cache_creation,
        )


class RequestData(BaseModel):
    """Captured request data from Bedrock API call"""

    operation: str
    model_id: str
    body: Dict[str, Any] = Field(default_factory=dict)
    headers: Dict[str, Any] = Field(default_factory=dict)
    url: str
    error: Optional[str] = None


class ResponseData(BaseModel):
    """Captured response data from Bedrock API call"""

    body: Dict[str, Any] = Field(default_factory=dict)
    usage: TokenUsage = Field(default_factory=TokenUsage)
    error: Optional[str] = None
    exception_type: Optional[str] = None


class InterceptedCall(BaseModel):
    """Complete intercepted API call with request, response, and metadata"""

    request: RequestData
    response: ResponseData
    timestamp: datetime = Field(default_factory=lambda: datetime.utcnow())

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
