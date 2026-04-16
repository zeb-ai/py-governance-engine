from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, computed_field


class TokenUsage(BaseModel):
    """Token usage information from LLM API calls"""

    input_tokens: int = 0
    output_tokens: int = 0
    extraction_error: Optional[str] = None

    @computed_field
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


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
