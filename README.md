<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=700&size=48&duration=1&pause=1000000&color=6366F1&center=true&vCenter=true&multiline=true&repeat=false&width=600&height=120&lines=Z-GRC" alt="Z-GRC">
</p>

<h2 align="center"><strong>Governance, Risk, and Control Engine for LLMs</strong></h2>
<p align="center">Built by <a href="https://zeb.co/research/">Zeb Labs</a></p>

<p align="center">
  <a href="https://pypi.org/project/z-grc/"><img src="https://img.shields.io/pypi/v/z-grc?color=FFD700&label=PyPI&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://www.npmjs.com/package/@zeb_labs/zgrc"><img src="https://img.shields.io/npm/v/@zeb_labs/zgrc?color=CB3837&logo=npm&logoColor=white" alt="npm"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white" alt="Python"></a>
  <a href="https://nodejs.org/"><img src="https://img.shields.io/badge/Node.js-18+-339933?logo=node.js&logoColor=white" alt="Node.js"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License"></a>
</p>

---

Enterprise-grade governance engine for Large Language Model applications. Provides automatic interception, policy enforcement, quota management, and comprehensive observability across multiple LLM providers with zero code changes.

Built with a high-performance native C core and bindings for Python and Node.js, Z-GRC intercepts LLM API calls at the network level, enabling seamless integration with any LLM SDK or framework.

## Installation

### Python

```bash
pip install z-grc
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv add z-grc
```

### Node.js

```bash
npm install @zeb_labs/zgrc
```

## Quick Start

### Python - AWS Bedrock

```python
import zgrc
import boto3
import json

# Initialize Z-GRC
zgrc.init(api_key="your-zgrc-api-key")

# Use AWS Bedrock SDK normally - Z-GRC handles everything
client = boto3.client("bedrock-runtime", region_name="us-east-1")

response = client.invoke_model(
    modelId="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    body=json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": "Hello!"}]
    })
)

# Z-GRC automatically:
# - Validates quota before requests
# - Tracks token usage and calculates costs
# - Enforces policies
# - Sends telemetry (traces, metrics, logs)
```

### Python - OpenAI

```python
import zgrc
from openai import OpenAI

# Initialize Z-GRC
zgrc.init(api_key="your-zgrc-api-key")

# Use OpenAI SDK normally
client = OpenAI(api_key="your-openai-key")

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### Node.js - AWS Bedrock

```javascript
const zgrc = require("@zeb_labs/zgrc");
const {
  BedrockRuntimeClient,
  InvokeModelCommand,
} = require("@aws-sdk/client-bedrock-runtime");

// Initialize Z-GRC
zgrc.init({ apiKey: "your-zgrc-api-key" });

// Use AWS SDK normally
const client = new BedrockRuntimeClient({ region: "us-east-1" });

const response = await client.send(
  new InvokeModelCommand({
    modelId: "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    body: JSON.stringify({
      anthropic_version: "bedrock-2023-05-31",
      max_tokens: 1024,
      messages: [{ role: "user", content: "Hello!" }],
    }),
  }),
);
```

### Node.js - OpenAI

```javascript
const zgrc = require("@zeb_labs/zgrc");
const OpenAI = require("openai");

// Initialize Z-GRC
zgrc.init({ apiKey: "your-zgrc-api-key" });

// Use OpenAI SDK normally
const client = new OpenAI({ apiKey: "your-openai-key" });

const response = await client.chat.completions.create({
  model: "gpt-4",
  messages: [{ role: "user", content: "Hello!" }],
});
```

Streaming is fully supported with automatic token tracking.

## Features

### Zero-Code Integration

Drop-in solution requiring only `zgrc.init()`. Works with existing code without modifications.

### Auto-Discovery

Automatically detects and intercepts installed LLM SDKs:

- AWS Bedrock (boto3)
- OpenAI (including Azure OpenAI, Databricks, and OpenAI-compatible endpoints)
- Anthropic (coming soon)

### Policy Enforcement

Real-time quota validation and cost limit enforcement. Blocks requests when quota is exceeded.

<p align="center">
  <img src="docs/assets/quota-exceeded.png" alt="Quota Exceeded Example" width="600">
</p>

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

## How It Works

### Architecture

Z-GRC works by intercepting LLM API calls at the **network layer** (SSL/TLS sockets) rather than the application layer. This enables governance without modifying any existing code.

```
Application Code
    ↓
Z-GRC SDK (Python/Node.js)
    ↓
Network Interception (SSL Socket Patching)
    ↓
Native C Core Engine
├─ Request Validation (Quota Check)
├─ Response Parsing (Token Counting)
├─ Cost Calculation
└─ Telemetry (OpenTelemetry Export)
    ↓
Quota Management Server
```

### Request Flow

1. **Request Interception**: Before sending a request to an LLM provider
   - Parse the HTTP request (URL, headers, body)
   - Extract model information and request details
   - Check current quota from the server
   - **Block** if quota exceeded, **Allow** if quota available

2. **Response Processing**: After receiving a response from an LLM provider
   - Handle compressed/chunked responses (gzip, deflate, brotli)
   - Parse token usage from provider-specific response format
   - Calculate cost based on configurable pricing
   - Report usage to quota server
   - Generate OpenTelemetry spans for observability

3. **Quota Management**: Dollar-based quota tracking
   - Track spending per user/group
   - Block requests when quota exceeded
   - Support quota resets and manual adjustments

## Project Structure

### Core Components

```
c-z-grc/
├── src/                          # Native C core engine
│   ├── interceptor.c            # Main interception logic & request/response handling
│   ├── cost_calculator.c        # Cost calculation based on tokens and pricing
│   ├── quota_client.c           # Quota server communication (HTTP)
│   ├── response_parser.c        # Provider-specific response parsing
│   ├── auth_token.c             # JWT API key authentication
│   ├── otel_exporter.c          # OpenTelemetry trace export
│   └── logger.c                 # Structured logging
│
├── packages/python/              # Python SDK & bindings
│   ├── zgrc/
│   │   ├── __init__.py          # Entry point: zgrc.init(api_key)
│   │   ├── core/
│   │   │   ├── interceptor.py   # SSL socket patching (ssl.SSLSocket.sendall/recv_into)
│   │   │   └── native.py        # C binding loader (ctypes)
│   │   └── utils/
│   │       ├── exceptions.py    # QuotaExceededError
│   │       └── resolve_aws_arn.py  # AWS Bedrock ARN resolution
│   └── setup.py
│
├── packages/node/                # Node.js SDK & bindings
│   ├── lib/
│   │   ├── index.js             # Entry point: zgrc.init(apiKey)
│   │   ├── intercept.js         # TLS stream interception
│   │   └── resolve-arn.js       # AWS ARN resolution
│   ├── src/                     # Native addon source
│   └── binding.gyp              # Node-gyp build configuration
│
├── data/                         # Model pricing database
│   └── merged_pricing.json      # Pricing for all supported models
│
├── examples/                     # Integration examples
│   └── databricks/              # Databricks AI Gateway integration
│       └── ai_gateway_cost_tracker.py  # Real-world usage example
│
├── docs/                         # User documentation
│   ├── how-to-use.md           # Setup & integration guide
│   └── index.md                # Documentation home
│
└── CMakeLists.txt / Makefile    # Build configuration
```

### Key Features by Component

#### Python SDK (`packages/python/zgrc/`)

- **Zero-Code Integration**: Single `zgrc.init()` call
- **SSL Socket Patching**: Intercepts all HTTPS traffic
- **Provider Detection**: Automatically identifies OpenAI, Bedrock, Anthropic
- **Streaming Support**: Handles AWS EventStream chunked responses
- **Error Handling**: Raises `QuotaExceededError` with quota details

```python
import zgrc
zgrc.init(api_key="your-api-key")  # That's it!
# All LLM calls are now governed automatically
```

#### Node.js SDK (`packages/node/lib/`)

- **Native Addon**: High-performance C++ bindings
- **TLS Interception**: Stream-level request/response capture
- **ARN Resolution**: Async AWS Bedrock model resolution
- **File Logging**: Optional structured logging to file

```javascript
const zgrc = require("@zeb_labs/zgrc");
zgrc.init({ apiKey: "your-api-key" }); // That's it!
// All LLM calls are now governed automatically
```

#### Native C Core (`src/`)

- **Request Validation**: Regex-based URL matching against API patterns
- **Cost Calculation**: O(1) model lookup + token-based pricing
- **Quota Management**: REST API integration with quota server
- **Response Parsing**: Provider-specific JSON parsing using yyjson
- **Observability**: OpenTelemetry span generation with comprehensive attributes
- **Performance**: <10ms per request overhead

### Provider Support

#### OpenAI

```json
{
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0
  }
}
```

#### AWS Bedrock

```json
{
  "usage": {
    "inputTokens": 100,
    "outputTokens": 50
  }
}
```

With streaming: Usage comes from the final event in EventStream format.

#### Anthropic

Similar to Bedrock with additional cache token fields.

### Pricing Model

Z-GRC uses **dollar-based quotas** (not token-based) because:

- Token counts vary by provider and use case
- Cost is what matters for budget management
- Supports cache tokens at different rates

```json
{
  "regional.openai.gpt-4": {
    "input_cost_per_1k": 0.003,
    "output_cost_per_1k": 0.006
  },
  "regional.anthropic.claude-sonnet": {
    "input_cost_per_1k": 0.003,
    "output_cost_per_1k": 0.006,
    "cache_write_per_1k": 0.0015,
    "cache_read_per_1k": 0.00015
  }
}
```

### Quota Management

**Quota Structure** (per user/group):

- `allocated_cost`: Total budget (e.g., $100)
- `used_cost`: Amount spent (e.g., $45)
- `remaining_cost`: Available budget (e.g., $55)

**Behavior**:

- ✅ Request allowed if `remaining_cost > 0`
- ❌ Request blocked if `remaining_cost <= 0`
- Cost updated after each request

**Server Interaction**:

```
GET /api/quota/user?group_id=...&user_id=...
  → Returns current quota

POST /api/quota/consume
  → Report usage: {user_id, group_id, tokens, cost}
  → Returns updated quota
```

### Example: Databricks Integration

See `examples/databricks/ai_gateway_cost_tracker.py` for a complete example that:

1. **Reads** LLM usage from Databricks inference tables
2. **Calculates** costs using Z-GRC pricing
3. **Tracks** quotas via Z-GRC API
4. **Enforces** rate limits when quota exceeded
5. **Manages** users dynamically

```python
from zgrc.utils.cost_calculator import calculate_cost_from_events

# Get usage
usage = await main.get_usage_from_inference_table()

# Calculate cost
cost = calculate_cost_from_events(events, model_id)

# Report to Z-GRC
quota = await main.post_usage_cost(user_email, usage)

# Enforce limits if exceeded
if quota['exceeded']:
    await main.set_rate_limit(user_email, 0, 0)  # Block user
```

## Security & Authentication

### API Keys (JWT-based)

API keys are JWT tokens containing:

```json
{
  "user_id": "uuid",
  "email": "user@example.com",
  "group_id": "uuid",
  "domain": "https://z-grc.zeb.co", // Quota server
  "opentelemetry": "grpc://collector:4317" // OTEL endpoint
}
```

### Security Best Practices

- ✅ Store API keys in environment variables or secret managers
- ✅ Never commit keys to version control
- ✅ Use HTTPS for all quota server communication
- ✅ Enable OpenTelemetry for audit trails
- ❌ Don't share API keys between environments

## OpenTelemetry Integration

Z-GRC automatically exports detailed spans to your OpenTelemetry collector:

```
Span: llm.completion
├─ Attributes:
│  ├─ llm.provider: "bedrock"
│  ├─ llm.model: "anthropic.claude-sonnet"
│  ├─ llm.input_tokens: 100
│  ├─ llm.output_tokens: 50
│  ├─ llm.cost.total: 0.0036
│  ├─ llm.cost.input: 0.0003
│  ├─ llm.cost.output: 0.0033
│  ├─ quota.used: 45.50
│  ├─ quota.remaining: 54.50
│  ├─ user.id: "uuid"
│  ├─ group.id: "uuid"
│  └─ http.url: "..."
└─ Duration: start_time → end_time
```

## Performance

- **Request Latency**: +5-10ms per LLM call (C core overhead)
- **Memory**: ~50-100MB per engine instance
- **Throughput**: 1000+ requests/sec per instance
- **Scaling**: Stateless design → horizontal scaling supported

## Development

### Building from Source

```bash
# Clone repository
git clone https://github.com/zeb-ai/z-grc.git
cd z-grc

# Build C core
make build

# Build Python package
cd packages/python
pip install -e .

# Build Node.js package
cd ../node
npm install
npm run build
```

### Running Tests

```bash
# Python tests
cd packages/python
pytest test/

# Node.js tests
cd packages/node
npm test
```

## Contributing

Contributions are welcome! The codebase is organized for:

1. **Clear separation of concerns**: Parsing, cost calculation, quota management
2. **Language bindings**: Native C core with Python & Node.js APIs
3. **Minimal dependencies**: Only yyjson (JSON) and curl (HTTP)
4. **Performance-first**: Every request passes through the engine

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Roadmap

- [ ] Anthropic SDK support (WIP)
- [ ] Enhanced proxy mode for non-code-modification environments
- [ ] Additional LLM providers (Cohere, Mistral, Llama, etc.)
- [ ] Advanced policy engine (request filtering, rate limiting)
- [ ] Custom cost model support
- [ ] UI dashboard for policy management

## Documentation

- 📖 [Full Documentation](docs/how-to-use.md)
- 🚀 [Quick Start Guide](docs/how-to-use.md)
- 🏗️ [Architecture Overview](CODEBASE_OVERVIEW.md)
- 💾 [Pricing Data Format](data/merged_pricing.json)
- 🔗 [Databricks Integration Example](examples/databricks/)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- 📧 **Email**: support@zeb.co
- 🐛 **Issues**: [GitHub Issues](https://github.com/zeb-ai/z-grc/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/zeb-ai/z-grc/discussions)
- 📚 **Docs**: [Full Documentation](docs/how-to-use.md)

---

<p align="center">
  Made with ❤️ by <a href="https://zeb.ai">Zeb Labs</a>
</p>
