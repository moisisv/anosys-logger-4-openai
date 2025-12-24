# AnoSys Logger for OpenAI - Node.js

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Node.js](https://img.shields.io/badge/node-%3E%3D18.0.0-brightgreen.svg)](https://nodejs.org/)

Automatically capture and send OpenAI API calls to [AnoSys](https://anosys.ai) for monitoring, analytics, and observability.

## Features

✨ **Automatic OpenAI Instrumentation** - Captures all OpenAI API calls via OpenTelemetry  
✨ **Full Streaming Support** - Captures and aggregates streaming responses  
✨ **Custom Function Decorators** - Log any JavaScript/TypeScript function  
✨ **OpenTelemetry Semantic Conventions** - Follows Gen AI standards  
✨ **Error Tracking** - Captures exceptions with full stack traces  
✨ **Zero Configuration** - Works out of the box with your API keys  

## Installation

```bash
npm install anosys-logger-4-openai
```

## Quick Start

### 1. Get Your AnoSys API Key

Visit [https://console.anosys.ai/collect/integrationoptions](https://console.anosys.ai/collect/integrationoptions) to get your API key.

### 2. Basic Usage

```javascript
import OpenAI from "openai";
import { instrumentOpenAI } from "anosys-logger-4-openai";

// Set your API keys (or set them in your environment)
process.env.OPENAI_API_KEY = "your-openai-api-key";
process.env.ANOSYS_API_KEY = "your-anosys-api-key";

// Create OpenAI client
const client = new OpenAI();

// Instrument it (do this once)
instrumentOpenAI(client);

// Use OpenAI as normal - all calls are automatically logged
const response = await client.chat.completions.create({
  model: "gpt-4o-mini",
  messages: [
    { role: "system", content: "You are a helpful assistant." },
    { role: "user", content: "Explain why AnoSys is great for AI observability" }
  ],
});

console.log(response.choices[0].message.content);
```

## Advanced Usage

### Streaming Responses

Streaming is fully supported with automatic chunk aggregation:

```javascript
import OpenAI from "openai";
import { instrumentOpenAI } from "anosys-logger-4-openai";

const client = new OpenAI();
instrumentOpenAI(client);

const stream = await client.chat.completions.create({
  model: "gpt-4o-mini",
  messages: [{ role: "user", content: "Write a haiku about AI" }],
  stream: true,
});

for await (const chunk of stream) {
  process.stdout.write(chunk.choices[0]?.delta?.content || "");
}
```

The complete aggregated response is automatically logged to AnoSys.

### Custom Function Decorators

Log any function execution:

```javascript
import { anosysLogger } from "anosys-logger-4-openai";

// Decorate an async function
let chatService = async (query) => {
  // logic...
  return "result";
};
chatService = anosysLogger("chat_service")(chatService);

const result = await chatService("Hello");
```

### Raw Logger

Send custom data directly:

```javascript
import { anosysRawLogger } from "anosys-logger-4-openai";

await anosysRawLogger({
  event: "logic_executed",
  status: "success",
  tokens_used: 42
});
```

### Configuration

```javascript
import { setupAPI } from "anosys-logger-4-openai";

// Optional: Use a custom endpoint
setupAPI({ path: "https://custom.anosys.endpoint" });
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANOSYS_API_KEY` | Yes | Your AnoSys API key |
| `OPENAI_API_KEY` | Yes | Your OpenAI API key |
| `ANOSYS_DEBUG_LOGS` | No | Set to `true` to enable detailed logging |

## Requirements

- Node.js 18.0+
- OpenAI Node SDK v4.x or v5.x
- ESM modules support

## Troubleshooting

### No data appearing in AnoSys?

1. **Check API key**: Ensure `ANOSYS_API_KEY` is set correctly.
2. **Order of operations**: Call `instrumentOpenAI(client)` before making requests.
3. **Module Type**: Ensure your `package.json` has `"type": "module"`.

## License

MIT License.
