import asyncio
import logging
from threading import Lock
from typing import Optional
from urllib.parse import unquote

logger = logging.getLogger(__name__)

_profile_cache: dict[str, Optional[str]] = {}
_cache_lock = Lock()


def _extract_model_id_from_url(url: str) -> Optional[str]:
    """Extract model ID from Bedrock URL path."""
    if not url:
        return None

    # URL format: https://bedrock-runtime.{region}.amazonaws.com/model/{model_id}/invoke
    # For ARNs, the URL might be split like: /model/{arn}/{profile_id}/invoke
    parts = url.split("/")
    if "model" in parts:
        model_index = parts.index("model")
        if model_index + 1 < len(parts):
            # URL decode the model ID (handles %3A, %2F, etc.)
            model_part = unquote(parts[model_index + 1])

            # Check if this is an ARN that got split
            if model_part.startswith("arn:aws:bedrock") and model_index + 2 < len(
                parts
            ):
                # The next part might be the profile ID
                next_part = parts[model_index + 2]
                if next_part and next_part not in [
                    "invoke",
                    "invoke-with-response-stream",
                    "converse",
                ]:
                    # Reconstruct the full ARN with profile ID
                    return f"{model_part}/{next_part}"

            return model_part

    return None


def _extract_profile_id_from_arn(arn: str) -> str:
    """Extract profile ID from ARN if needed."""
    if arn.startswith("arn:aws:bedrock"):
        # ARN format: arn:aws:bedrock:us-east-1:926251048803:application-inference-profile/7j95b0rxjwhy
        return arn.split("/")[-1]
    return arn


def _is_inference_profile(model_id: str) -> bool:
    """Check if model_id is an inference profile (no dots in ID)."""
    if not model_id:
        return False

    if model_id.startswith("arn:aws:bedrock"):
        return True

    return "." not in model_id


async def _resolve_inference_profile(profile_id: str) -> Optional[str]:
    """Call AWS Bedrock API to get actual model ID from inference profile."""
    with _cache_lock:
        if profile_id in _profile_cache:
            logger.debug(f"Cache hit for profile {profile_id}")
            return _profile_cache[profile_id]

    import boto3
    from botocore.exceptions import ClientError

    try:
        loop = asyncio.get_event_loop()
        client = boto3.client("bedrock", region_name="us-east-1")

        response = await loop.run_in_executor(
            None,
            lambda: client.get_inference_profile(inferenceProfileIdentifier=profile_id),
        )

        models = response.get("models", [])
        if not models:
            return None

        model_arn = models[0].get("modelArn", "")
        model_id = model_arn.split("/")[-1] if "/" in model_arn else None

        if model_id:
            logger.debug(f"Resolved {profile_id} -> {model_id}")

        with _cache_lock:
            _profile_cache[profile_id] = model_id

        return model_id

    except ClientError as e:
        logger.error(f"AWS API error for profile {profile_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to resolve profile {profile_id}: {e}")
        return None


async def resolve_model_id_from_url(url: str) -> Optional[str]:
    """Extract and resolve model ID from Bedrock URL."""
    model_id = _extract_model_id_from_url(url)
    if not model_id:
        return None

    if not _is_inference_profile(model_id):
        return model_id

    # Extract profile ID from ARN if needed
    profile_id = _extract_profile_id_from_arn(model_id)
    return await _resolve_inference_profile(profile_id)


if __name__ == "__main__":

    async def test():
        url1 = "https://bedrock-runtime.us-east-1.amazonaws.com/model/us.anthropic.claude-sonnet-4-20250514-v1%3A0/converse"
        url2 = "https://bedrock-runtime.us-east-1.amazonaws.com/model/arn%3Aaws%3Abedrock%3Aus-east-1%3A926251048803%3Aapplication-inference-profile%2F7j95b0rxjwhy/invoke"

        print("Testing URL 1 (direct model):")
        result1 = await resolve_model_id_from_url(url1)
        print(f"  Result: {result1}\n")

        print("Testing URL 2 (inference profile - first call):")
        result2 = await resolve_model_id_from_url(url2)
        print(f"  Result: {result2}\n")

        print("Testing URL 2 again (should hit cache):")
        result3 = await resolve_model_id_from_url(url2)
        print(f"  Result: {result3}")

    asyncio.run(test())
