from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from pydantic import BaseModel, ConfigDict

from .base_telemetry import BaseTelemetry


class LogsConfig(BaseModel):
    provider: str
    model_id: str
    operation: str
    request: Dict[str, Any]
    response: Dict[str, Any]
    usage: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None


class LogData(BaseModel):
    timestamp: str
    trace_id: str
    span_id: str
    request: Dict[str, Any]
    response: Dict[str, Any]
    usage: Dict[str, Any]
    provider: str
    model_id: str
    operation: str

    model_config = ConfigDict(extra="allow")


class Logs(BaseTelemetry):
    def __init__(self):
        super().__init__()
        self._logger_provider: Optional[LoggerProvider] = None
        self._otel_logger = None
        self._log_endpoint = f"{self.log_endpoint}/v1/logs"

    def setup(self):
        """Initialize OpenTelemetry logger provider with OTLP HTTP exporter and batch log processor."""
        exporter = OTLPLogExporter(endpoint=self._log_endpoint, timeout=10)
        self._logger_provider = LoggerProvider(resource=self.resource)

        assert self._logger_provider is not None
        self._logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(exporter=exporter)
        )
        set_logger_provider(self._logger_provider)
        self._otel_logger = self._logger_provider.get_logger("zgrc.llm")

    def attach_logging_handler(self):
        """Attach OpenTelemetry logging handler to capture Python application logs automatically."""
        handler = LoggingHandler(
            level=logging.NOTSET, logger_provider=self._logger_provider
        )
        logging.getLogger().addHandler(handler)

    def send(self, config: LogsConfig):
        """Emit a structured log entry for an LLM inference operation with trace context."""
        span = trace.get_current_span()
        ctx = span.get_span_context()

        log_data = LogData(
            timestamp=datetime.now(timezone.utc).isoformat(),
            trace_id=format(ctx.trace_id, "032x") if ctx.is_valid else "unknown",
            span_id=format(ctx.span_id, "016x") if ctx.is_valid else "unknown",
            provider=config.provider,
            model_id=config.model_id,
            operation=config.operation,
            request=config.request,
            response=config.response,
            usage=config.usage,
            **config.metadata if config.metadata else {},
        )

        self._otel_logger.emit(
            body=json.dumps(log_data.model_dump()),
            severity_text="INFO",
            attributes={
                "log.type": "llm_inference",
                "llm.provider": config.provider,
                "llm.model": config.model_id,
                "llm.operation": config.operation,
                "llm.tokens.input": config.usage.get("input_tokens", 0),
                "llm.tokens.output": config.usage.get("output_tokens", 0),
                "llm.tokens.total": config.usage.get("total_tokens", 0),
            },
        )
