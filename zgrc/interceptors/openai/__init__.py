from zgrc.core import interceptor_registry
from .interceptor import OpenAIInterceptor
from zgrc.providers import Providers

interceptor_registry.register(
    provider=Providers.OPENAI,
    interceptor_class=OpenAIInterceptor,
    packages_required=["openai"],
)

__all__ = ["OpenAIInterceptor"]
