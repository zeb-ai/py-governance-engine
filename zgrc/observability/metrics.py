from typing import TYPE_CHECKING, Any, Dict

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

from .base_telemetry import BaseTelemetry

if TYPE_CHECKING:
    from opentelemetry.metrics import Meter, Counter


class Metrics(BaseTelemetry):
    def __init__(self) -> None:
        super().__init__()
        self._meter: Meter | None = None
        self._counters: Dict[str, Counter] | None = None

    def setup(self) -> None:
        """Initialize OpenTelemetry metrics provider with OTLP HTTP exporter and periodic export."""
        metrics_endpoint = f"{self.log_endpoint}/v1/metrics"
        exporter = OTLPMetricExporter(endpoint=metrics_endpoint, timeout=10)

        reader = PeriodicExportingMetricReader(exporter, export_interval_millis=60000)
        _meter_provider = MeterProvider(resource=self.resource, metric_readers=[reader])
        metrics.set_meter_provider(_meter_provider)
        self._meter = metrics.get_meter("zgrc")

        self._counters = {
            "total_token": self._meter.create_counter(
                name="total_token",
                description="Total number of tokens",
                unit="Tokens",
            ),
            "input_token": self._meter.create_counter(
                name="input_token", description="Input tokens consumed", unit="tokens"
            ),
            "output_token": self._meter.create_counter(
                name="output_token", description="Output tokens consumed", unit="tokens"
            ),
            "requests": self._meter.create_counter(
                "zgrc.llm.requests", description="Total LLM requests", unit="1"
            ),
        }

    def set_tokens(
        self,
        input_tokens: int,
        output_tokens: int,
        attributes: Dict[str, Any] | None = None,
    ) -> None:
        """Record token usage metrics including input, output, total tokens, and request count."""
        if self._counters is None:
            return

        attrs: Dict[str, Any] = attributes or {}
        total_tokens: int = input_tokens + output_tokens
        self._counters["total_token"].add(total_tokens, attributes=attrs)
        self._counters["input_token"].add(input_tokens, attributes=attrs)
        self._counters["output_token"].add(output_tokens, attributes=attrs)
        self._counters["requests"].add(1, attributes=attrs)

    def send(self) -> None:
        pass
