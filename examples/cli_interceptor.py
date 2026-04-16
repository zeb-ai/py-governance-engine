import json
import os
import struct
from datetime import datetime
from mitmproxy.http import Response

LOG_FILE = "token_log.json"
BUDGET = 200


def load_state():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            return json.load(f)
    return {"total": 0, "history": []}


def save_state(state):
    with open(LOG_FILE, "w") as f:
        json.dump(state, f, indent=2)


# noinspection PyBroadException
def parse_event_stream(data):
    """Parse AWS binary event stream format and extract JSON payloads."""
    events = []
    offset = 0
    while offset < len(data):
        if offset + 12 > len(data):
            break
        try:
            total_len = struct.unpack_from(">I", data, offset)[0]
            if total_len < 16 or offset + total_len > len(data):
                break

            # Headers section: bytes 8 to (total_len - 4 - message_len)
            headers_len = struct.unpack_from(">I", data, offset + 4)[0]
            payload_start = offset + 12 + headers_len
            payload_end = offset + total_len - 4  # exclude trailing CRC

            payload = data[payload_start:payload_end]
            try:
                decoded = json.loads(payload.decode("utf-8"))
                # The actual content is base64-encoded inside "bytes"
                if "bytes" in decoded:
                    import base64

                    inner = base64.b64decode(decoded["bytes"]).decode("utf-8")
                    inner_json = json.loads(inner)
                    events.append(inner_json)
            except Exception:
                pass
            offset += total_len
        except Exception:
            break
    return events


# noinspection PyBroadException
def parse_response(content):
    """Try to parse response - JSON or event stream."""
    # Try plain JSON first
    try:
        return json.loads(content.decode("utf-8"))
    except Exception:
        pass
    # Try event stream
    events = parse_event_stream(content)
    if events:
        return {"events": events}
    # Fallback to hex
    return content.hex()


state = load_state()


def request(flow):
    """Block request BEFORE it hits AWS if budget exceeded."""
    if "amazonaws.com" not in flow.request.pretty_host:
        return
    if "invoke" not in flow.request.path:
        return

    if state["total"] >= BUDGET:
        flow.response = Response.make(
            429,
            json.dumps(
                {"error": f"Token budget exceeded: {state['total']} / {BUDGET}"}
            ),
            {"Content-Type": "application/json"},
        )
        print(
            f"[BLOCKED] Request blocked before hitting AWS. Total: {state['total']} / {BUDGET}"
        )


# noinspection PyBroadException
def response(flow):
    if "amazonaws.com" not in flow.request.pretty_host:
        return

    # Only care about model invocations
    if "invoke" not in flow.request.path:
        return

    try:
        req_body = None
        try:
            req_body = json.loads(flow.request.content.decode("utf-8"))
        except Exception:
            req_body = flow.request.content.hex()

        resp_body = parse_response(flow.response.content)

        # Extract token usage from events
        input_tokens = 0
        output_tokens = 0
        if isinstance(resp_body, dict) and "events" in resp_body:
            for event in resp_body["events"]:
                usage = event.get("usage", {})
                input_tokens += usage.get("input_tokens", 0)
                output_tokens += usage.get("output_tokens", 0)

        used = input_tokens + output_tokens
        state["total"] += used

        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "url": flow.request.pretty_url,
            "status": flow.response.status_code,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_so_far": state["total"],
            "request": req_body,
            "response": resp_body,
        }

        state["history"].append(entry)
        save_state(state)
        print(
            f"[OK] Tokens: {used} (in={input_tokens}, out={output_tokens}) | Total: {state['total']} / {BUDGET}"
        )

        if state["total"] >= BUDGET:
            flow.response.status_code = 429
            flow.response.content = json.dumps(
                {"error": f"Token budget exceeded: {state['total']} / {BUDGET}"}
            ).encode()

    except Exception as e:
        print(f"[ERROR] {e}")


"""
NODE_EXTRA_CA_CERTS=~/.mitmproxy/mitmproxy-ca.pem HTTPS_PROXY=http://localhost:8080 claude
"""
