# GRC - Governance Engine

[![Python Version](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![PyPI version](https://badge.fury.io/py/py-governance-engine.svg)](https://pypi.org/project/py-governance-engine/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/py-governance-engine)](https://pypi.org/project/py-governance-engine/)

[//]: # ([![License]&#40;https://img.shields.io/badge/license-Proprietary-red.svg&#41;]&#40;&#41;)

Enterprise-grade governance engine for Large Language Model applications. Provides automatic interception, policy enforcement, quota management, and comprehensive observability across multiple LLM providers with zero code changes.

## Installation

```bash
uv add py-governance-engine
```

Or with auto-instrumentation:

```bash
uv add py-governance-engine[auto-instrument]
```

## Quick Start

```python
import grc
import boto3
import json

# Initialize GRC
grc.init(api_key="your-grc-api-key")

# Use your LLM SDK normally - GRC handles everything
client = boto3.client("bedrock-runtime", region_name="us-east-1")

response = client.invoke_model(
    modelId="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    body=json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": "Hello!"}]
    })
)

# GRC automatically:
# - Validates quota before requests
# - Tracks token usage
# - Enforces policies
# - Sends telemetry (traces, metrics, logs)
```

## Features

### Zero-Code Integration
Drop-in solution requiring only `grc.init()`. Works with existing code without modifications.

### Auto-Discovery
Automatically detects and intercepts installed LLM SDKs:
- AWS Bedrock (boto3)
- Anthropic (coming soon)
- OpenAI (coming soon)
- Azure OpenAI (coming soon)

### Policy Enforcement
Real-time quota validation and token limit enforcement. Blocks requests when quota is exceeded.

```python
from grc.utils import QuotaExceededException

try:
    response = client.invoke_model(...)
except QuotaExceededException as e:
    print(f"Quota exceeded: {e.used}/{e.limit} tokens")
```

### Auto-Instrumentation
Optional automatic instrumentation for HTTP clients, web frameworks, databases, and more:

```python
grc.init(
    api_key="your-grc-api-key",
    auto_instrument=True,
    app_name="my-app",
    environment="production"
)
```

### Framework Agnostic
Works with vanilla SDKs and popular frameworks:

```python
# PydanticAI
from pydantic_ai import Agent
agent = Agent("bedrock")
result = await agent.run("Your prompt")

# LangChain
from langchain_aws import ChatBedrock
llm = ChatBedrock(model_id="...")
response = llm.invoke("Your prompt")

# Strands Agents
from strands_agents import Agent
agent = Agent(provider="bedrock")
response = agent.execute("Your prompt")
```

### Streaming Support
Fully supports streaming responses with automatic token tracking:

```python
response = client.converse_stream(
    modelId="...",
    messages=[{"role": "user", "content": [{"text": "Tell me a story"}]}]
)

for event in response["stream"]:
    if "contentBlockDelta" in event:
        print(event["contentBlockDelta"]["delta"]["text"], end="")
```

## Configuration

```python
grc.init(
    api_key: str,                  # Your GRC API key (required)
    auto_instrument: bool = False, # Enable auto-instrumentation
    app_name: str = None,          # Application name for telemetry
    environment: str = None,       # Environment (dev/staging/prod)
    log_level: int = logging.ERROR # GRC internal log level
)
```

## Building Executables

Build standalone executables with PyInstaller:

### macOS/Linux
```bash
./build.sh
```
Output: `dist/grc-proxy-macos-arm64` or `dist/grc-proxy-linux-x86_64`

### Windows
```bash
build.bat
```
Output: `dist/grc-proxy-windows-x64.exe`

### Test Executable
```bash
# macOS/Linux
./dist/grc-proxy-macos-arm64 --api-key=grc_xxx

# Windows
dist\grc-proxy-windows-x64.exe --api-key=grc_xxx
```

**Note:** Certificates auto-generate in `~/.mitmproxy/` on first run. Users must set `HTTPS_PROXY` and `NODE_EXTRA_CA_CERTS` environment variables.
