# AnoSys Logger for OpenAI - Python

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)

Automatically capture and send OpenAI API calls to [AnoSys](https://anosys.ai) for monitoring, analytics, and observability.

## Features

✨ **Automatic OpenAI Instrumentation** - Captures all OpenAI API calls via OpenTelemetry  
✨ **Streaming Support** - Detects and logs streaming responses  
✨ **Custom Function Decorators** - Log any Python function (sync or async)  
✨ **OpenTelemetry Semantic Conventions** - Follows Gen AI standards  
✨ **Error Tracking** - Captures exceptions with full stack traces  
✨ **Zero Configuration** - Works out of the box with just your API key  

## Installation

```bash
pip install anosys-logger-4-openai
```

## Quick Start

### 1. Get Your AnoSys API Key

Visit [https://console.anosys.ai/collect/integrationoptions](https://console.anosys.ai/collect/integrationoptions) to get your API key.

### 2. Basic Usage with OpenAI

```python
import os
from openai import OpenAI
from AnosysLoggers import AnosysOpenAILogger

# Set your API keys
os.environ["OPENAI_API_KEY"] = "your-openai-api-key"
os.environ["ANOSYS_API_KEY"] = "your-anosys-api-key"

# Initialize AnoSys logger (do this once)
AnosysOpenAILogger()

# Use OpenAI as normal - all calls are automatically logged
client = OpenAI()

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain why AnoSys is great for AI observability"}
    ]
)

print(response.choices[0].message.content)
```

That's it! All your OpenAI calls are now being sent to AnoSys. 🎉

## Advanced Usage

### Streaming Responses

Streaming is automatically detected and logged:

```python
from openai import OpenAI
from AnosysLoggers import AnosysOpenAILogger

AnosysOpenAILogger()
client = OpenAI()

stream = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Write a haiku about AI"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

The complete aggregated response will be logged to AnoSys.

### Custom Function Decorators

Log any Python function (sync or async):

```python
from AnosysLoggers import anosys_logger

@anosys_logger(source="my_app.calculations")
def calculate_score(data):
    # Your function logic
    return sum(data) / len(data)

# Function calls are automatically logged
result = calculate_score([85, 90, 78, 92])
```

**Async Functions:**

```python
@anosys_logger(source="my_app.async_tasks")
async def fetch_data(url):
    # Your async logic
    return await some_async_operation()

# Async calls are also logged
result = await fetch_data("https://api.example.com")
```

### Raw Logger

Send custom data directly:

```python
from AnosysLoggers import anosys_raw_logger

# Log any custom data
anosys_raw_logger({
    "event": "user_action",
    "action": "button_click",
    "timestamp": "2024-01-15T10:30:00Z",
    "user_id": "12345"
})
```

### Custom Configuration

```python
from AnosysLoggers import setup_api

# Use a custom endpoint (advanced)
setup_api(path="https://custom.anosys.endpoint")

# Or with custom index starting points (rarely needed)
setup_api(starting_indices={
    "string": 200,
    "number": 10,
    "bool": 5
})
```

## What Data is Captured?

### OpenTelemetry Semantic Conventions

Following the [OpenTelemetry Gen AI standards](https://opentelemetry.io/docs/specs/semconv/gen-ai/):

- `gen_ai.system` - Always "openai"
- `gen_ai.request.model` - Model requested (e.g., "gpt-4o-mini")
- `gen_ai.response.model` - Model that responded
- `gen_ai.request.temperature` - Temperature parameter
- `gen_ai.request.max_tokens` - Max tokens parameter
- `gen_ai.request.top_p` - Top-p parameter
- `gen_ai.response.finish_reasons` - Why the response ended
- `gen_ai.usage.input_tokens` - Input token count
- `gen_ai.usage.output_tokens` - Output token count

### Additional Fields

- Request/response messages
- Timestamps and duration
- Error details (if any)
- Trace IDs for distributed tracing
- Custom metadata

## Error Handling

Errors are automatically captured with full context:

```python
@anosys_logger(source="my_app.risky_function")
def risky_operation():
    raise ValueError("Something went wrong")

try:
    risky_operation()
except ValueError:
    pass  # Error is still logged to AnoSys with stack trace
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANOSYS_API_KEY` | Yes | Your AnoSys API key |
| `OPENAI_API_KEY` | Yes | Your OpenAI API key |
| `ANOSYS_DEBUG_LOGS` | No | Set to `false` to disable raw span logging |

## Requirements

- Python 3.9 - 3.12
- OpenAI Python SDK
- OpenTelemetry SDK
- traceai-openai

## Troubleshooting

### No data appearing in AnoSys?

1. **Check your API key**: Ensure `ANOSYS_API_KEY` is set correctly
2. **Initialize before OpenAI calls**: Call `AnosysOpenAILogger()` before making OpenAI requests
3. **Check network**: Ensure you can reach `https://api.anosys.ai`

### Import errors?

Make sure all dependencies are installed:
```bash
pip install --upgrade anosys-logger-4-openai
```

## Support

- 📧 Email: support@anosys.ai  
- 🌐 Website: [https://anosys.ai](https://anosys.ai)  
- 📚 Console: [https://console.anosys.ai](https://console.anosys.ai)

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
