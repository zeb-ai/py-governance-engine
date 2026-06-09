from pathlib import Path
from .._native import ffi, lib
from ..utils import RequestResult, ResponseResult

_DEFAULT_PRICING = str(
    Path(__file__).resolve().parent.parent / "data" / "merged_pricing.json"
)

_ctx = None

LOG_DEBUG = 0
LOG_INFO = 1
LOG_WARN = 2
LOG_ERROR = 3


def init(api_key: str, app_name: str = None):
    global _ctx
    if _ctx is not None:
        return

    pricing_file = _DEFAULT_PRICING

    if app_name is None:
        app_name = "python-app"

    _ctx = lib.interceptor_init(
        api_key.encode(), pricing_file.encode(), app_name.encode()
    )
    if _ctx == ffi.NULL:
        _ctx = None
        raise RuntimeError("Failed to initialize z-grc")


def enable_logging(level: int = LOG_DEBUG, path: str = "/tmp/zgrc.log"):
    if _ctx is None:
        raise RuntimeError("should be initialize first")
    lib.interceptor_enable_logging(_ctx, level, path.encode())


def request(url: str, body: str) -> RequestResult:
    if _ctx is None:
        raise RuntimeError("should be initialize first")

    body_bytes = body.encode()
    result = lib.intercept_request(_ctx, url.encode(), body_bytes, len(body_bytes))
    return RequestResult(
        allowed=result.allowed,
        model=ffi.string(result.model).decode(),
        used_quota=result.used_quota,
        remaining_quota=result.remaining_quota,
    )


def response(url: str, body: str) -> ResponseResult:
    if _ctx is None:
        raise RuntimeError("should be initialize first")

    body_bytes = body.encode()
    result = lib.intercept_response(_ctx, url.encode(), body_bytes, len(body_bytes))
    return ResponseResult(
        cost=result.cost,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        used_quota=result.used_quota,
        remaining_quota=result.remaining_quota,
    )


def destroy():
    global _ctx
    if _ctx is not None:
        lib.interceptor_free(_ctx)
        _ctx = None
