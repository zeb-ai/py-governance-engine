from opentelemetry.sdk.resources import Resource

from .logs import Logs
from .traces import Traces
from .metrics import Metrics
from .auto_instrumentation import AutoInstrumentation

traces = None
metrics = None
logs = None
auto_manager = None


def create_app_resource(
    base_resource: Resource, app_name: str, environment: str
) -> Resource:
    """Merges application-specific attributes into the base OpenTelemetry resource."""
    app_attributes = {}

    if app_name:
        app_attributes["service.name"] = app_name

    if environment:
        app_attributes["deployment.environment"] = environment

    app_attributes["telemetry.sdk.name"] = "grc-auto-instrument"
    app_attributes["telemetry.sdk.language"] = "python"

    app_resource = Resource.create(app_attributes)
    return base_resource.merge(app_resource)


def instrument(
    app_name: str,
    environment: str,
    auto_instrument: bool = False,
):
    """
    Initialize GRC telemetry components (traces, metrics, logs) and optionally enable automatic instrumentation.

    This function sets up OpenTelemetry observability for the application. When auto_instrument is enabled,
    it enriches the telemetry resource with application metadata (service name, environment, SDK info),
    configures all telemetry components with this enriched resource, attaches a logging handler to capture
    application logs, and automatically instruments supported frameworks and libraries for distributed tracing.
    Without auto-instrumentation, it performs a basic setup of traces, metrics, and logs components.
    """
    global traces, metrics, logs, auto_manager

    traces = Traces()
    metrics = Metrics()
    logs = Logs()

    # If auto-instrumentation is enabled, enrich the resource BEFORE setup
    if auto_instrument:
        base_resource = traces.resource
        enriched_resource = create_app_resource(
            base_resource=base_resource,
            app_name=app_name,
            environment=environment,
        )

        # Update the resource for all telemetry components
        traces.resource = enriched_resource
        metrics.resource = enriched_resource
        logs.resource = enriched_resource

        # Now setup with enriched resource
        traces.setup()
        metrics.setup()
        logs.setup()

        # Attach logging handler to capture application logs
        logs.attach_logging_handler()

        # Initialize auto-instrumentation
        auto_manager = AutoInstrumentation(resource=enriched_resource)
        auto_manager.instrument()
    else:
        # Normal setup without auto-instrumentation
        traces.setup()
        metrics.setup()
        logs.setup()


__all__ = [
    "instrument",
    "traces",
    "metrics",
    "logs",
    "auto_manager",
]
