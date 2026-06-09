import ssl
import re
import zlib

from .native import (
    init as c_init,
    request as c_request,
    response as c_response,
    destroy as c_destroy,
)
from ..utils import QuotaExceededError
from ..utils.resolve_aws_arn import resolve_aws_arn


class Intercept:
    def __init__(self, api_key: str, app_name: str = None):
        c_init(api_key, app_name)

        self._orig_sendall = ssl.SSLSocket.sendall
        self._orig_recv_into = ssl.SSLSocket.recv_into

        orig_sendall = self._orig_sendall
        orig_recv_into = self._orig_recv_into

        send_buffers = {}
        recv_buffers = {}
        sock_urls = {}
        sock_req_body = {}
        sock_models = {}
        recv_meta = {}

        def patched_sendall(sock, data, flags=0):
            orig_sendall(sock, data, flags)

            sid = id(sock)
            raw = bytes(data) if not isinstance(data, bytes) else data
            buf = send_buffers.get(sid, b"") + raw
            send_buffers[sid] = buf

            # not enough data yet
            if b"\r\n\r\n" not in buf:
                return None

            # not HTTP
            if not Intercept._is_http_request(buf):
                send_buffers.pop(sid, None)
                return None

            header_section, _, body_bytes = buf.partition(b"\r\n\r\n")
            first_line = header_section.split(b"\r\n", 1)[0]
            parts = first_line.decode("utf-8", errors="replace").split(" ", 2)
            path = parts[1] if len(parts) > 1 else "/"
            body = body_bytes.decode("utf-8", errors="replace")

            if sid not in sock_urls:
                host = Intercept._parse_host(sock)
                if not host:
                    send_buffers.pop(sid, None)
                    return None
                full_url = f"https://{host}{path}"
                sock_urls[sid] = full_url

                if "arn" in path and "/model/" in path:
                    resolved = resolve_aws_arn(full_url)
                    if resolved:
                        sock_models[sid] = resolved

            full_url = sock_urls[sid]

            # only fire c_request when we have body
            if body.strip():
                send_buffers.pop(sid, None)
                req_result = c_request(full_url, body)
                if req_result.allowed == 0:
                    raise QuotaExceededError(
                        req_result.used_quota, req_result.remaining_quota
                    )
                if req_result.allowed == 1:
                    sock_req_body[sid] = True

        def patched_recv_into(sock, buffer, nbytes=0, flags=0):
            n = orig_recv_into(sock, buffer, nbytes, flags)

            if n <= 0:
                return n

            sid = id(sock)
            url = sock_urls.get(sid)
            if not url:
                return n

            chunk = bytes(buffer[:n])
            buf = recv_buffers.get(sid, b"") + chunk
            recv_buffers[sid] = buf

            if b"\r\n\r\n" not in buf:
                return n

            # parse response headers once
            if sid not in recv_meta:
                header_section, _, _ = buf.partition(b"\r\n\r\n")
                recv_meta[sid] = (
                    Intercept._get_content_length(header_section),
                    Intercept._is_chunked(header_section),
                    Intercept._is_eventstream(header_section),
                )

            content_length, chunked, eventstream = recv_meta[sid]
            _, _, body_bytes = buf.partition(b"\r\n\r\n")

            if chunked or eventstream:
                # wait for terminal chunk
                if not buf.endswith(b"0\r\n\r\n"):
                    return n
                raw_body = Intercept._decode_chunked(body_bytes)
            elif content_length >= 0:
                if len(body_bytes) < content_length:
                    return n
                raw_body = body_bytes[:content_length]
            else:
                raw_body = body_bytes

            header_sec, _, _ = buf.partition(b"\r\n\r\n")
            raw_body = Intercept._decompress(header_sec, raw_body)

            if eventstream:
                body_str = Intercept._build_usage_json_from_eventstream(raw_body)
            else:
                body_str = raw_body.decode("utf-8", errors="replace")

            status = Intercept._parse_response_status(buf)
            if status == 0:
                return n

            if sid not in sock_req_body:
                recv_buffers.pop(sid, None)
                recv_meta.pop(sid, None)
                sock_urls.pop(sid, None)
                sock_models.pop(sid, None)
                return n

            c_url = url
            if sid in sock_models:
                model = sock_models[sid]
                c_url = re.sub(r"/model/[^/]+/", f"/model/regional.{model}/", url)

            resp_result = c_response(c_url, body_str)
            if resp_result.cost == 0.0 and resp_result.input_tokens == 0:
                import warnings

                warnings.warn(f"[z-grc] failed to report usage for {url}")

            recv_buffers.pop(sid, None)
            recv_meta.pop(sid, None)
            sock_urls.pop(sid, None)
            sock_req_body.pop(sid, None)
            sock_models.pop(sid, None)

            return n

        self._patched_sendall = patched_sendall
        self._patched_recv_into = patched_recv_into

        ssl.SSLSocket.sendall = patched_sendall
        ssl.SSLSocket.recv_into = patched_recv_into

    def free(self):
        ssl.SSLSocket.sendall = self._orig_sendall
        ssl.SSLSocket.recv_into = self._orig_recv_into
        c_destroy()

    @staticmethod
    def _parse_host(sock) -> str:
        try:
            if hasattr(sock, "server_hostname") and sock.server_hostname:
                return sock.server_hostname
            return sock.getpeername()[0]
        except Exception:
            return ""

    @staticmethod
    def _is_http_request(data: bytes) -> bool:
        HTTP_METHODS = (
            b"GET ",
            b"POST ",
            b"PUT ",
            b"DELETE ",
            b"PATCH ",
            b"HEAD ",
            b"OPTIONS ",
            b"CONNECT ",
            b"TRACE ",
        )
        return any(data.startswith(m) for m in HTTP_METHODS)

    @staticmethod
    def _decompress(header_section: bytes, body: bytes) -> bytes:
        encoding = ""
        for line in header_section.split(b"\r\n"):
            if line.lower().startswith(b"content-encoding:"):
                encoding = line.split(b":", 1)[1].strip().lower().decode()
                break
        if encoding == "gzip":
            return zlib.decompress(body, zlib.MAX_WBITS | 16)
        elif encoding == "deflate":
            return zlib.decompress(body, -zlib.MAX_WBITS)
        return body

    @staticmethod
    def _get_content_length(header_section: bytes) -> int:
        for line in header_section.split(b"\r\n"):
            if line.lower().startswith(b"content-length:"):
                try:
                    return int(line.split(b":", 1)[1].strip())
                except Exception:
                    pass
        return -1

    @staticmethod
    def _is_chunked(header_section: bytes) -> bool:
        for line in header_section.split(b"\r\n"):
            if line.lower().startswith(b"transfer-encoding:"):
                return b"chunked" in line.lower()
        return False

    @staticmethod
    def _is_eventstream(header_section: bytes) -> bool:
        for line in header_section.split(b"\r\n"):
            if line.lower().startswith(b"content-type:"):
                return b"amazon.eventstream" in line.lower()
        return False

    @staticmethod
    def _decode_chunked(data: bytes) -> bytes:
        body = b""
        while data:
            crlf = data.find(b"\r\n")
            if crlf == -1:
                break
            try:
                chunk_size = int(data[:crlf], 16)
            except ValueError:
                break
            if chunk_size == 0:
                break
            chunk_start = crlf + 2
            body += data[chunk_start : chunk_start + chunk_size]
            data = data[chunk_start + chunk_size + 2 :]
        return body

    @staticmethod
    def _build_usage_json_from_eventstream(data: bytes) -> str:
        import json

        text = data.decode("utf-8", errors="replace")
        lines = re.findall(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text)
        for line in reversed(lines):
            try:
                obj = json.loads(line)
                if "inputTokens" in obj or "input_tokens" in obj:
                    return json.dumps({"usage": obj})
            except (json.JSONDecodeError, ValueError):
                continue
        return text

    @staticmethod
    def _parse_response_status(data: bytes) -> int:
        try:
            first_line = data.split(b"\r\n", 1)[0].decode("utf-8", errors="replace")
            parts = first_line.split(" ", 2)
            return int(parts[1]) if len(parts) > 1 else 0
        except Exception:
            return 0
