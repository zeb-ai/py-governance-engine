# import boto3
# import os
# from dotenv import load_dotenv
#
# load_dotenv()
#
# client = boto3.client("bedrock", region_name="us-east-1")
#
# response = client.get_inference_profile(
#     inferenceProfileIdentifier=os.getenv("MODEL_ID")
# )
#
# print(response["inferenceProfileName"])
# print(response["models"])


# from litellm import cost_per_token
#
# input_cost, output_cost = cost_per_token(
#     model="bedrock/anthropic.claude-sonnet-4-5-20250929-v1:0",
#     prompt_tokens=3,
#     completion_tokens=46,
#     cache_read_input_tokens=0,
#     cache_creation_input_tokens=16900,
# )
#
# print(input_cost)
# print(output_cost)
# print(input_cost + output_cost)

from litellm import completion_cost

MODEL = "bedrock/anthropic.claude-sonnet-4-5-20250929-v1:0"


def calc_cost_from_bedrock_stream(payload: dict) -> float:
    events = payload["events"]

    message_start = next(
        e["message"]["usage"] for e in events if e["type"] == "message_start"
    )
    message_delta = next(e["usage"] for e in events if e["type"] == "message_delta")

    input_tokens = message_delta["input_tokens"]
    output_tokens = message_delta["output_tokens"]
    cache_read_tokens = message_start.get("cache_read_input_tokens", 0)
    cache_creation_tokens = message_start.get("cache_creation_input_tokens", 0)

    lite_like_response = {
        "model": MODEL,
        "usage": {
            "prompt_tokens": input_tokens + cache_read_tokens + cache_creation_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens
            + cache_read_tokens
            + cache_creation_tokens
            + output_tokens,
            "prompt_tokens_details": {"cached_tokens": cache_read_tokens},
            "cache_creation_input_tokens": cache_creation_tokens,
        },
    }

    return float(completion_cost(completion_response=lite_like_response))


payload = {
    "events": [
        {
            "type": "message_start",
            "message": {
                "model": "claude-sonnet-4-5-20250929",
                "id": "msg_bdrk_017mghGceb7KF3P5kTzwUAYf",
                "type": "message",
                "role": "assistant",
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {
                    "input_tokens": 3,
                    "cache_creation_input_tokens": 16833,
                    "cache_read_input_tokens": 0,
                    "cache_creation": {
                        "ephemeral_5m_input_tokens": 16833,
                        "ephemeral_1h_input_tokens": 0,
                    },
                    "output_tokens": 1,
                },
            },
        },
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "text", "text": ""},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "Hi"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": " Samrat! I can"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": " see you're working on the"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": " token"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "-to-cost-tracking-system"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "-"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "updation branch"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": " with"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": " some"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": " changes"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": " to"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": " the cost"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": " tracking"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": " system. How"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": " can I help you today?"},
        },
        {"type": "content_block_stop", "index": 0},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            "usage": {
                "input_tokens": 3,
                "cache_creation_input_tokens": 16833,
                "cache_read_input_tokens": 0,
                "output_tokens": 45,
            },
        },
        {
            "type": "message_stop",
            "amazon-bedrock-invocationMetrics": {
                "inputTokenCount": 3,
                "outputTokenCount": 44,
                "invocationLatency": 6059,
                "firstByteLatency": 1988,
                "cacheReadInputTokenCount": 0,
                "cacheWriteInputTokenCount": 16833,
            },
        },
    ]
}

print(f"${calc_cost_from_bedrock_stream(payload):.10f}")
