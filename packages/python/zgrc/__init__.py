from .core import Intercept

# purely use for development, not compatible for the production use case
# I didn't handle file size handling, may cause in the future.
from .core.native import (
    enable_logging as enable_logging,
    LOG_DEBUG as LOG_DEBUG,
    LOG_INFO as LOG_INFO,
    LOG_WARN as LOG_WARN,
    LOG_ERROR as LOG_ERROR,
)

_instance = None


def init(api_key: str):
    global _instance
    if _instance is not None:
        return
    _instance = Intercept(api_key)


def free():
    global _instance
    if _instance is not None:
        _instance.free()
        _instance = None
