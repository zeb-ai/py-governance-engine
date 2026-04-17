from .registry import InterceptorRegistry
from .lazy_patcher import LazyPatcher
from .manager import AutoManager

# Singleton instances - shared across all imports (Python caches modules in sys.modules)
interceptor_registry = InterceptorRegistry()
auto_manager = AutoManager()

__all__ = [
    "interceptor_registry",
    "auto_manager",
    "LazyPatcher",
    "AutoManager",
]
