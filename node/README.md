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
✨ **Zero Configuration** - Works out of the box with just your API key  

## Installation

```bash
npm install anosys-logger-4-openai
```

## Quick Start

### 1. Get Your AnoSys API Key

Visit [https://console.anosys.ai/collect/integrationoptions](https://console.anosys.ai/collect/integrationoptions) to get your API key.

### 2. Basic Usage with OpenAI

```javascript
import OpenAI from "openai";
import { instrumentOpenAI } from "anosys-logger-4-openai";

// Set your API keys
process.env.OPENAI_API_KEY = "your-openai-api-key";
process.env.ANOSYS_API_KEY = "your-anosys-api-key";

// Create OpenAI client
const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

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

That's it! All your OpenAI calls are now being sent to AnoSys. 🎉

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
  if (chunk.choices[0]?.delta?.content) {
    process.stdout.write(chunk.choices[0].delta.content);
  }
}
```

The complete aggregated response (with all chunks combined) is automatically logged to AnoSys.

### Custom Function Decorators

Log any function (sync or async):

```javascript
import { anosysLogger, setupAPI } from "anosys-logger-4-openai";

// Setup once (optional, uses ANOSYS_API_KEY by default)
setupAPI();

// Decorate a sync function
let calculateScore = (data) => {
  return data.reduce((a, b) => a + b, 0) / data.length;
};
calculateScore = anosysLogger("my_app.calculations")(calculateScore);

// Function calls are automatically logged
const result = calculateScore([85, 90, 78, 92]);
```

**Async Functions:**

```javascript
let fetchData = async (url) => {
  const response = await fetch(url);
  return response.json();
};
fetchData = anosysLogger("my_app.api_calls")(fetchData);

// Async calls are also logged
const data = await fetchData("https://api.example.com/data");
```

**Note**: Due to JavaScript limitations, you cannot reassign `const` functions. Use `let` or create a new reference:

```javascript
const multiply = (a, b) => a * b;

// Create a decorated version with a new name
const loggedMultiply = anosysLogger("math.multiply")(multiply);

const result = loggedMultiply(5, 3);
```

### Raw Logger

Send custom data directly:

```javascript
import { anosysRawLogger } from "anosys-logger-4-openai";

// Log any custom data
await anosysRawLogger({
  event: "user_action",
  action: "button_click",
  timestamp: new Date().toISOString(),
  user_id: "12345"
});
```

### Custom Configuration

```javascript
import { setupAPI } from "anosys-logger-4-openai";

// Use a custom endpoint (advanced)
setupAPI({ path: "https://custom.anosys.endpoint" });

// Or with custom index starting points (rarely needed)
setupAPI({ 
  startingIndices: {
    string: 200,
    number: 10,
    bool: 5
  }
});
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
- Error details with stack traces
- Trace IDs for distributed tracing
- Streaming indicators
- Custom metadata

## Supported OpenAI Endpoints

✅ Chat Completions (`client.chat.completions.create`)  
✅ Chat Completions Streaming (`stream: true`)  
✅ Embeddings (`client.embeddings.create`)  
✅ Image Generation (`client.images.generate`)  
✅ Legacy Completions (`client.completions.create`)  

## Error Handling

Errors are automatically captured with full context:

```javascript
const loggedFunction = anosysLogger("my_app.risky")(async () => {
  throw new Error("Something went wrong");
});

try {
  await loggedFunction();
} catch (error) {
  // Error is still logged to AnoSys with:
  // - Error type
  // - Error message
  // - Full stack trace
}
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANOSYS_API_KEY` | Yes | Your AnoSys API key |
| `OPENAI_API_KEY` | Yes | Your OpenAI API key |

## TypeScript Support

This package works seamlessly with TypeScript:

```typescript
import OpenAI from "openai";
import { instrumentOpenAI, anosysLogger } from "anosys-logger-4-openai";

const client = new OpenAI();
instrumentOpenAI(client);

// Type-safe decorators
const calculateScore = anosysLogger("app.calc")((data: number[]): number => {
  return data.reduce((a, b) => a + b, 0) / data.length;
});
```

## Requirements

- Node.js 18.0.0 or higher
- OpenAI Node SDK v5.x
- ESM modules support

## Streaming Implementation Details

When you use `stream: true`:

1. **Wrapper intercepts** the async iterator
2. **Collects all chunks** as they arrive
3. **Yields chunks** to your code (no delay)
4. **After stream completes**, aggregates chunks into a complete response
5. **Logs the aggregated response** to AnoSys with full metadata

This means:
- ✅ Zero impact on streaming performance
- ✅ Complete response captured
- ✅ Token usage included (from last chunk)
- ✅ Finish reasons tracked

## Troubleshooting

### No data appearing in AnoSys?

1. **Check your API key**: Ensure `ANOSYS_API_KEY` is set correctly
2. **Instrument before API calls**: Call `instrumentOpenAI(client)` before making requests
3. **Check network**: Ensure you can reach `https://console.anosys.ai`
4. **Check exports**: Make sure you're using ESM (`import`) not CommonJS (`require`)

### Module errors?

Ensure your `package.json` has:
```json
{
  "type": "module"
}
```

### Not capturing streaming?

Make sure you're using `for await` to consume the stream - the aggregation happens after all chunks are consumed.

## Examples

Check out the examples in the repository:
- Basic usage
- Streaming responses
- Custom decorators
- Error handling

## Support

- 📧 Email: support@anosys.ai  
- 🌐 Website: [https://anosys.ai](https://anosys.ai)  
- 📚 Console: [https://console.anosys.ai](https://console.anosys.ai)

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
