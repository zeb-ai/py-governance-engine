from zgrc.core import interceptor_registry
from .interceptor import BedrockInterceptor
from zgrc.providers import Providers

interceptor_registry.register(
    provider=Providers.BEDROCK,
    interceptor_class=BedrockInterceptor,
    packages_required=["boto3", "botocore"],
)

__all__ = ["BedrockInterceptor"]
