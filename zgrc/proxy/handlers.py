import base64
import json
import logging
import struct
from datetime import datetime
from mitmproxy.http import Response

from opentelemetry import context, trace

from ..interceptors.models import TokenUsage
from .. import observability
from ..observability.logs import LogsConfig
from ..policy.pre_checker import PreChecker
from ..policy.post_checker import PostChecker
from ..providers import Providers
from ..utils.cost_calculator import calculate_cost_from_events
from ..utils.exceptions import QuotaExceededException
from ..utils.model_resolver import resolve_model_id_from_url

logger = logging.getLogger(__name__)


def _extract_operation_name(path: str) -> str:
    """Extract Bedrock operation name from URL path"""
    if "invoke-with-response-stream" in path:
        return "InvokeModelWithResponseStream"
    elif "converse-stream" in path:
        return "ConverseStream"
    elif "converse" in path:
        return "Converse"
    elif "invoke" in path:
        return "InvokeModel"
    return "unknown"


class RequestHandler:
    def __init__(self, budget: int = None):

        self.pre_checker = PreChecker()
        self.budget = budget
        self.total_tokens = 0

    async def handle(self, flow):
        if flow.request.path == "/__health":
            flow.response = Response.make(
                200,
                json.dumps({"status": 200}, indent=2),
                {"Content-Type": "application/json"},
            )
            return

        if "amazonaws.com" not in flow.request.pretty_host:
            return
        if "invoke" not in flow.request.path:
            return

        # Create trace span for this request
        span = None
        token = None
        operation_name = _extract_operation_name(flow.request.path)

        if observability.traces and observability.traces.tracer:
            span = observability.traces.tracer.start_span(
                f"bedrock.proxy.{operation_name}",
                attributes={
                    "llm.provider": "bedrock",
                    "llm.operation": operation_name,
                    "http.url": flow.request.pretty_url,
                    "http.method": flow.request.method,
                },
            )
            ctx = trace.set_span_in_context(span)
            token = context.attach(ctx)

            # Store span context in flow for response handler
            flow.metadata["trace_span"] = span
            flow.metadata["trace_token"] = token

        logger.debug(f"{flow.request.pretty_url}")

        try:
            await self.pre_checker.check_quota()
            logger.debug("[OK] Quota check passed")

        except QuotaExceededException as e:
            if span:
                span.set_status(trace.Status(trace.StatusCode.ERROR, "Quota exceeded"))
                span.add_event(
                    "quota_exceeded",
                    {
                        "used": str(e.used),
                        "remaining": str(e.remaining),
                    },
                )

            error_body = {
                "__type": "ServiceCostExceededException",
                "message": f"Cost exceeded: ${e.used:.4f} used, ${e.remaining:.4f} remaining. Increase quota at your GRC dashboard to continue.",
                "used": e.used,
                "remaining": e.remaining,
            }
            flow.response = Response.make(
                400,
                json.dumps(error_body),
                {"Content-Type": "application/json"},
            )
            logger.error(f"[BLOCKED] Quota exceeded: {e}")

            # End span on error
            if span:
                span.end()
                if token:
                    context.detach(token)
            return
        except Exception as e:
            logger.error(f"[ERROR] Pre-check failed: {e}", exc_info=True)
            if span:
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                span.end()
                if token:
                    context.detach(token)
            return


class ResponseHandler:
    def __init__(self, request_handler: RequestHandler):
        self.request_handler = request_handler
        self.post_checker = PostChecker()
        self.history = []

    async def handle(self, flow):
        if "amazonaws.com" not in flow.request.pretty_host:
            return
        if "invoke" not in flow.request.path:
            return

        # Retrieve span from request handler
        span = flow.metadata.get("trace_span")
        token = flow.metadata.get("trace_token")

        logger.info(f"{flow.response.status_code} {flow.request.pretty_url}")

        try:
            response_data = self._parse_response(flow.response.content)

            total_usage = TokenUsage()

            if isinstance(response_data, dict) and "events" in response_data:
                for idx, event in enumerate(response_data["events"]):
                    usage_dict = event.get("usage", {})
                    if not usage_dict:
                        continue
                    # Try snake_case first (Anthropic models)
                    if "input_tokens" in usage_dict:
                        event_usage = TokenUsage.from_usage_dict(
                            usage_dict, key_format="snake_case"
                        )
                    # Try camelCase (Amazon models)
                    elif "inputTokens" in usage_dict:
                        event_usage = TokenUsage.from_usage_dict(
                            usage_dict, key_format="camelCase"
                        )
                    else:
                        continue

                    # DEBUG: Log parsed event usage
                    logger.info(
                        f"Event {idx} parsed - "
                        f"input={event_usage.input_tokens}, "
                        f"output={event_usage.output_tokens}, "
                        f"cache_read={event_usage.cache_read_input_tokens}, "
                        f"cache_write={event_usage.cache_creation_input_tokens}"
                    )

                    total_usage = TokenUsage(
                        input_tokens=total_usage.input_tokens
                        + event_usage.input_tokens,
                        output_tokens=total_usage.output_tokens
                        + event_usage.output_tokens,
                        cache_read_input_tokens=total_usage.cache_read_input_tokens
                        + event_usage.cache_read_input_tokens,
                        cache_creation_input_tokens=total_usage.cache_creation_input_tokens
                        + event_usage.cache_creation_input_tokens,
                    )

            # Calculate cost using the new event-based method
            cost = 0.0
            model_id = None
            if isinstance(response_data, dict) and "events" in response_data:
                model_id = await resolve_model_id_from_url(flow.request.pretty_url)
                if model_id:
                    logger.debug(f"Resolved model_id: {model_id}")
                    cost = (
                        calculate_cost_from_events(response_data["events"], model_id)
                        or 0.0
                    )
                    logger.info(f"Calculated cost: ${cost}")

            used = total_usage.total_tokens
            self.request_handler.total_tokens += used

            if used > 0:
                logger.debug(
                    f"Tokens: {used} (in={total_usage.input_tokens}, out={total_usage.output_tokens}, "
                    f"cache_read={total_usage.cache_read_input_tokens}, cache_write={total_usage.cache_creation_input_tokens}) | "
                    f"Cost: ${cost:.6f} | Total: {self.request_handler.total_tokens}"
                )

                self.post_checker.schedule_background_report(used, cost)

                # Add token and cost attributes to span
                if span:
                    span.set_attributes(
                        {
                            "llm.tokens.input": total_usage.input_tokens,
                            "llm.tokens.output": total_usage.output_tokens,
                            "llm.tokens.total": total_usage.total_tokens,
                            "llm.tokens.cache_read": total_usage.cache_read_input_tokens,
                            "llm.tokens.cache_creation": total_usage.cache_creation_input_tokens,
                            "llm.cost.total": cost,
                            "llm.model": model_id or "unknown",
                        }
                    )

                # Record metrics
                if observability.metrics:
                    observability.metrics.set_tokens(
                        input_tokens=total_usage.input_tokens,
                        output_tokens=total_usage.output_tokens,
                        attributes={
                            "model": model_id or "unknown",
                            "provider": "bedrock",
                            "operation": _extract_operation_name(flow.request.path),
                            "cost": cost,
                        },
                    )

                # Send structured logs to OpenTelemetry
                if observability.logs and span:
                    from threading import Thread

                    logger.debug("Preparing to send logs to OpenTelemetry")

                    # Parse request body
                    try:
                        req_body = json.loads(flow.request.content.decode("utf-8"))
                    except Exception:
                        req_body = {"_raw": flow.request.content.hex()[:200]}

                    log_config = LogsConfig(
                        provider=Providers.BEDROCK,
                        model_id=model_id or "unknown",
                        operation=_extract_operation_name(flow.request.path),
                        request=req_body,
                        response=response_data
                        if isinstance(response_data, dict)
                        else {},
                        usage={
                            "input_tokens": total_usage.input_tokens,
                            "output_tokens": total_usage.output_tokens,
                            "total_tokens": total_usage.total_tokens,
                            "cache_read_input_tokens": total_usage.cache_read_input_tokens,
                            "cache_creation_input_tokens": total_usage.cache_creation_input_tokens,
                            "total_cost": cost,
                        },
                    )

                    # Capture current context to propagate to thread
                    current_context = context.get_current()

                    def send_logs_with_context():
                        """Send logs in background thread with propagated context"""
                        token = context.attach(current_context)
                        try:
                            logger.debug("Sending logs to OpenTelemetry backend")
                            observability.logs.send(log_config)
                            logger.debug("Logs sent successfully")
                        except Exception as e:
                            logger.error(f"Failed to send logs: {e}", exc_info=True)
                        finally:
                            try:
                                context.detach(token)
                            except ValueError:
                                # Context was created in different async context, ignore
                                pass

                    # Send logs in background thread with context propagation
                    thread = Thread(target=send_logs_with_context, daemon=False)
                    thread.start()
                    logger.debug("Log send thread started")
                elif not observability.logs:
                    logger.warning("Logs module not initialized, skipping log send")
                elif not span:
                    logger.warning("No span available, skipping log send")

                # Keep existing history logging
                self._log_entry(
                    flow,
                    response_data,
                    total_usage.input_tokens,
                    total_usage.output_tokens,
                )

        except Exception as e:
            logger.error(f"[ERROR] Response processing failed: {e}")
            if span:
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
        finally:
            # Always end span and detach context
            if span:
                span.end()
            if token:
                try:
                    context.detach(token)
                except ValueError:
                    # Context was created in different async context, ignore
                    pass

    # noinspection PyBroadException
    def _parse_response(self, content):
        try:
            return json.loads(content.decode("utf-8"))
        except Exception:
            pass

        events = self._parse_event_stream(content)
        if events:
            return {"events": events}

        return content.hex()

    def _parse_event_stream(self, data):
        # AWS Bedrock uses binary event stream format with base64-encoded JSON chunks
        events = []
        offset = 0

        while offset < len(data):
            if offset + 12 > len(data):
                break

            try:
                total_len = struct.unpack_from(">I", data, offset)[0]
                if total_len < 16 or offset + total_len > len(data):
                    break

                headers_len = struct.unpack_from(">I", data, offset + 4)[0]
                payload_start = offset + 12 + headers_len
                payload_end = offset + total_len - 4

                payload = data[payload_start:payload_end]

                try:
                    decoded = json.loads(payload.decode("utf-8"))
                    if "bytes" in decoded:
                        inner = base64.b64decode(decoded["bytes"]).decode("utf-8")
                        inner_json = json.loads(inner)
                        events.append(inner_json)
                except Exception as e:
                    logger.error(
                        f"[ERROR] Response parse event deserialization failed: {e}"
                    )

                offset += total_len
            except Exception as e:
                logger.error(f"[ERROR] Response processing failed: {e}")
                break
        return events

    # noinspection PyBroadException
    def _log_entry(self, flow, response_data, input_tokens, output_tokens):
        try:
            req_body = json.loads(flow.request.content.decode("utf-8"))
        except Exception:
            req_body = flow.request.content.hex()

        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "url": flow.request.pretty_url,
            "status": flow.response.status_code,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_so_far": self.request_handler.total_tokens,
            "request": req_body,
            "response": response_data,
        }

        self.history.append(entry)

        if len(self.history) > 100:
            self.history.pop(0)

    def get_stats(self):
        return {
            "total_tokens": self.request_handler.total_tokens,
            "budget": self.request_handler.budget,
            "request_count": len(self.history),
            "history": self.history[-10:],
        }
