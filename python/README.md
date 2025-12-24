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
✨ **Zero Configuration** - Works out of the box with your API keys  

## Installation

```bash
pip install anosys-logger-4-openai
```

## Quick Start

### 1. Get Your AnoSys API Key

Visit [https://console.anosys.ai/collect/integrationoptions](https://console.anosys.ai/collect/integrationoptions) to get your API key.

### 2. Basic Usage

```python
import os
from openai import OpenAI
from AnosysLoggers import AnosysOpenAILogger

# Set your API keys (or set them in your environment)
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

### Custom Function Decorators

Log any Python function execution:

```python
from AnosysLoggers import anosys_logger

@anosys_logger(source="my_app.logic")
def process_data(data):
    # Your function logic
    return sum(data) / len(data)

result = process_data([85, 90, 78, 92])
```

### Raw Logger

Send custom data directly:

```python
from AnosysLoggers import anosys_raw_logger

anosys_raw_logger({
    "event": "report_generated",
    "status": "success",
    "records": 150
})
```

### Configuration

```python
from AnosysLoggers import setup_api

# Optional: Use a custom endpoint
setup_api(path="https://custom.anosys.endpoint")
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANOSYS_API_KEY` | Yes | Your AnoSys API key |
| `OPENAI_API_KEY` | Yes | Your OpenAI API key |
| `ANOSYS_DEBUG_LOGS` | No | Set to `true` to enable detailed logging |

## Requirements

- Python 3.9+
- OpenAI Python SDK
- OpenTelemetry SDK
- traceai-openai

## Troubleshooting

### No data appearing in AnoSys?

1. **Check API key**: Ensure `ANOSYS_API_KEY` is set correctly.
2. **Order of operations**: Call `AnosysOpenAILogger()` before making requests.
3. **Network**: Ensure your environment can reach `https://api.anosys.ai`.

## License

MIT License.
