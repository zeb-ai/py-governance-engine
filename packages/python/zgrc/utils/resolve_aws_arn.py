import os
import re
from urllib.parse import unquote

_store: dict[str, str] = {}


def _extract_arn_from_url(url: str) -> str | None:
    """converting encode url to arn"""
    try:
        parts = url.split("/model/", 1)
        if len(parts) < 2:
            return None
        raw = parts[1].split("/")[0]
        return unquote(raw)
    except Exception as e:
        print("exception raised in AWS ARN extraction", e)
        return None


def resolve_aws_arn(url: str) -> str | None:
    try:
        if url in _store:
            return _store[url]

        import boto3

        client = boto3.client(
            "bedrock",
            region_name=os.getenv("region")
            or os.getenv("AWS_DEFAULT_REGION")
            or "us-east-1",
        )
        if (raw_arn := _extract_arn_from_url(url)) is not None:
            profile = client.get_inference_profile(inferenceProfileIdentifier=raw_arn)
            model_arn = profile["models"][1]["modelArn"]
            match = re.search(r"foundation-model/(.+)$", model_arn)
            if (result := match.group(1) if match else None) is not None:
                _store[url] = result
                return result
        return None

    except ImportError:
        print("boto3 is needed when your using inference profile")
        return None
    except Exception as e:
        print("exception raised in AWS ARN resolving", e)
        return None


if __name__ == "__main__":
    response = resolve_aws_arn(
        "https://bedrock-runtime.us-east-1.amazonaws.com/model/arn%3Aaws%3Abedrock%3Aus-east-1%3A926251048803%3Aapplication-inference-profile%2F7j95b0rxjwhy/invokehttps://bedrock-runtime.us-east-1.amazonaws.com/model/arn%3Aaws%3Abedrock%3Aus-east-1%3A926251048803%3Aapplication-inference-profile%2F7j95b0rxjwhy/invoke"
    )
    print(response)

    response = resolve_aws_arn("https://google.com")
    print(response)
