# AnoSys Logger for OpenAI

> **Automatic observability for OpenAI API calls** - Available for Python and Node.js

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Monitor, analyze, and debug your OpenAI API usage with [AnoSys](https://anosys.ai) - the observability platform built for AI applications.

## 🚀 Quick Links

- **Python Package**: [./python/README.md](./python/README.md)
- **Node.js Package**: [./node/README.md](./node/README.md)
- **Get API Key**: [https://console.anosys.ai/](https://console.anosys.ai/)

## ✨ Features

- ✅ **Zero-Config Instrumentation** - Just install and set your API keys
- ✅ **Full Streaming Support** - Captures streaming responses with chunk aggregation
- ✅ **OpenTelemetry Standards** - Follows Gen AI semantic conventions
- ✅ **Custom Decorators** - Log any function execution
- ✅ **Error Tracking** - Full stack traces and context
- ✅ **Distributed Tracing** - Unified tracing across your services

## 📦 Installation

### Python

```bash
pip install anosys-logger-4-openai
```

### Node.js

```bash
npm install anosys-logger-4-openai
```

## 🎯 Quick Start

### Python

```python
import os
from openai import OpenAI
from AnosysLoggers import AnosysOpenAILogger

# Set keys or ensure they are in your environment
os.environ["ANOSYS_API_KEY"] = "your-anosys-api-key"
os.environ["OPENAI_API_KEY"] = "your-openai-api-key"

AnosysOpenAILogger() # Initialize once
client = OpenAI()

# All OpenAI calls are now automatically logged ✨
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### Node.js

```javascript
import OpenAI from "openai";
import { instrumentOpenAI } from "anosys-logger-4-openai";

// Set keys or ensure they are in your environment
process.env.ANOSYS_API_KEY = "your-anosys-api-key";
process.env.OPENAI_API_KEY = "your-openai-api-key";

const client = new OpenAI();
instrumentOpenAI(client); // Initialize once

// All OpenAI calls are now automatically logged ✨
const response = await client.chat.completions.create({
  model: "gpt-4o-mini",
  messages: [{ role: "user", content: "Hello!" }]
});
```

## 📊 What's Captured?

Following [OpenTelemetry Gen AI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/):

| Field | Description | Example |
|-------|-------------|---------|
| `gen_ai.system` | AI system name | "openai" |
| `gen_ai.request.model` | Model requested | "gpt-4o-mini" |
| `gen_ai.response.model` | Model responded | "gpt-4o-mini-2024-07-18" |
| `gen_ai.request.temperature` | Temperature parameter | 0.7 |
| `gen_ai.request.max_tokens` | Max tokens parameter | 1000 |
| `gen_ai.usage.input_tokens` | Input tokens used | 45 |
| `gen_ai.usage.output_tokens` | Output tokens used | 120 |
| `gen_ai.response.finish_reasons` | Why response ended | ["stop"] |

Plus:
- Request/response messages
- Timestamps and duration
- Error details and stack traces
- Trace IDs for distributed tracing
- Custom metadata

## 🌊 Streaming Support

Both packages fully support streaming with automatic chunk aggregation:

**Python:**
```python
stream = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True
)

for chunk in stream:
    print(chunk.choices[0].delta.content, end="")
```

**Node.js:**
```javascript
const stream = await client.chat.completions.create({
  model: "gpt-4o-mini",
  messages: [{ role: "user", content: "Tell me a story" }],
  stream: true,
});

for await (const chunk of stream) {
  process.stdout.write(chunk.choices[0]?.delta?.content || "");
}
```

## 🏗️ Architecture

```
┌─────────────────┐
│  Your App Code  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────────┐
│ AnoSys Logger   │─────▶│  OpenTelemetry   │
│  (Interceptor)  │      │  Instrumentation │
└────────┬────────┘      └──────────────────┘
         │
         ▼
┌─────────────────┐
│   OpenAI API    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   AnoSys API    │
│  (Telemetry)    │
└─────────────────┘
```

## 📚 Documentation

- [Python Documentation](./python/README.md)
- [Node.js Documentation](./node/README.md)
- [AnoSys Console](https://console.anosys.ai)
- [OpenTelemetry Gen AI Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)

## 🆘 Support

- 📧 **Email**: support@anosys.ai
- 🌐 **Website**: [https://anosys.ai](https://anosys.ai)
- 📚 **Console**: [https://console.anosys.ai](https://console.anosys.ai)

## 📝 License

MIT License.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

Made with ❤️ by the AnoSys team
