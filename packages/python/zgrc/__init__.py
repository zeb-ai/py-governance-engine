from .core import Intercept

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
