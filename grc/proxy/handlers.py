import base64
import json
import logging
import struct
from datetime import datetime
from mitmproxy.http import Response

from ..policy.pre_checker import PreChecker
from ..policy.post_checker import PostChecker
from ..utils.exceptions import QuotaExceededException

logger = logging.getLogger(__name__)


class RequestHandler:
    def __init__(self, budget: int = None):

        self.pre_checker = PreChecker()
        self.budget = budget
        self.total_tokens = 0

    async def handle(self, flow):
        if "amazonaws.com" not in flow.request.pretty_host:
            return
        if "invoke" not in flow.request.path:
            return

        logger.info(f"[REQUEST] {flow.request.pretty_url}")

        try:
            await self.pre_checker.check_quota()
            logger.debug("[OK] Quota check passed")

        except QuotaExceededException as e:
            flow.response = Response.make(
                429,
                json.dumps({"error": str(e), "used": e.used, "limit": e.limit}),
                {"Content-Type": "application/json"},
            )
            logger.error(f"[BLOCKED] Quota exceeded: {e}")
        except Exception as e:
            logger.error(f"[ERROR] Pre-check failed: {e}", exc_info=True)


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

        logger.info(f"[RESPONSE] {flow.response.status_code} {flow.request.pretty_url}")

        try:
            response_data = self._parse_response(flow.response.content)

            input_tokens = 0
            output_tokens = 0

            if isinstance(response_data, dict) and "events" in response_data:
                for event in response_data["events"]:
                    usage = event.get("usage", {})
                    input_tokens += usage.get("input_tokens", 0)
                    output_tokens += usage.get("output_tokens", 0)

            used = input_tokens + output_tokens
            self.request_handler.total_tokens += used

            if used > 0:
                logger.info(
                    f"[OK] Tokens: {used} (in={input_tokens}, out={output_tokens}) | Total: {self.request_handler.total_tokens}"
                )

                self.post_checker.schedule_background_report(used)

                self._log_entry(flow, response_data, input_tokens, output_tokens)

        except Exception as e:
            logger.error(f"[ERROR] Response processing failed: {e}")

    def _parse_response(self, content):
        try:
            return json.loads(content.decode("utf-8"))
        except Exception as e:
            logger.error(f"[ERROR] Response processing failed: {e}")

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
