from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .base_telemetry import BaseTelemetry
from typing import Optional
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter


class Traces(BaseTelemetry):
    def __init__(self):
        super().__init__()
        self._tracer_provider: Optional[TracerProvider] = None
        self._tracer: Optional[trace.Tracer] = None

    @property
    def tracer(self):
        """Get the configured OpenTelemetry tracer instance."""
        return self._tracer

    def setup(self):
        """Initialize OpenTelemetry tracer provider with OTLP HTTP exporter and batch span processor."""
        trace_endpoint = f"{self.log_endpoint}/v1/traces"
        exporter = OTLPSpanExporter(endpoint=trace_endpoint, timeout=10)
        self._tracer_provider = TracerProvider(resource=self.resource)

        assert self._tracer_provider is not None
        self._tracer_provider.add_span_processor(
            BatchSpanProcessor(exporter, max_export_batch_size=512)
        )
        trace.set_tracer_provider(self._tracer_provider)
        self._tracer = trace.get_tracer("zgrc")

    def send(self):
        pass
