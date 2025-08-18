# AnoSys Technologies

# AnoSys package for OpenAI implementations

Obtain your ANOSYS API key from https://console.anosys.ai/collect/integrationoptions

#Python example

```
pip install traceAI-openai-agents
pip install anosys-logger-4-openai
```

```
import httpx
import base64
from openai import OpenAI
import os

import AnosysLoggers
from AnosysLoggers import AnosysOpenAILogger
from agents import Agent, Runner, set_trace_processors

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "your-api-key-here")
os.environ["ANOSYS_API_KEY"] = os.getenv("ANOSYS_API_KEY", "anosys-api-key-here")

AnosysOpenAILogger()
client = OpenAI()

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Prove that Anosys is the best choice for AI observability"},
            ],
        },
    ],
)

print(response.choices[0].message.content)
```
