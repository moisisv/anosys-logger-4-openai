# Implementation Guide: High-Priority Fixes for AI Logger Package

This document provides detailed instructions for implementing critical improvements to an AI observability logger package (for OpenAI or similar AI APIs) in both Python and Node.js.

## Overview of Changes

The following high-priority improvements were implemented:

1. **Fix missing Python functions** - Create shared utilities module
2. **Add streaming support** - Full support for streaming AI responses
3. **Improve error handling** - Proper span status codes and exception tracking
4. **Add semantic conventions** - OpenTelemetry Gen AI standards
5. **Add comprehensive tests** - Unit tests for core functionality

---

## Part 1: Python Package Improvements

### 1.1 Create Shared Utilities Module

**Objective**: Eliminate code duplication by creating a shared utilities module.

**File to Create**: `src/AnosysLoggers/utils.py`

**Key Components**:

```python
"""
Shared utility functions for AnosysLoggers package.
Eliminates code duplication between decorator.py and tracing.py.
"""
import json
from typing import Dict, Any, Optional, Union

# Separate index tracking for each type
global_starting_indices = {
    "string": 100,
    "number": 3,
    "bool": 1
}

# Known key mappings - will be updated dynamically
key_to_cvs = {
    "custom_mapping": "otel_schema_url",
    "otel_observed_timestamp": "otel_observed_timestamp",
    "otel_record_type": "otel_record_type",
    # ... [include basic mappings]
    
    # OpenTelemetry Semantic Conventions for Gen AI
    "gen_ai.system": "gen_ai_system",
    "gen_ai.request.model": "gen_ai_request_model",
    "gen_ai.response.model": "gen_ai_response_model",
    "gen_ai.request.temperature": "gen_ai_request_temperature",
    "gen_ai.request.max_tokens": "gen_ai_request_max_tokens",
    "gen_ai.request.top_p": "gen_ai_request_top_p",
    "gen_ai.response.finish_reasons": "gen_ai_response_finish_reasons",
    "gen_ai.usage.input_tokens": "gen_ai_usage_input_tokens",
    "gen_ai.usage.output_tokens": "gen_ai_usage_output_tokens",
    
    # Error tracking
    "error": "cvs3",
    "error_type": "cvs10",
    "error_message": "cvs11",
    "error_stack": "cvs12",
}
```

**Required Functions**:

1. `_get_type_key(value: Any) -> str` - Detect value type
2. `_get_prefix_and_index(value_type: str) -> tuple` - Map type to prefix
3. `reassign(data: Union[Dict, str], starting_index: Optional[Dict] = None) -> Dict` - Map keys to CVS variables
4. `to_json_fallback(resp: Any) -> str` - Safe JSON conversion
5. `to_str_or_none(val: Any) -> Optional[str]` - String conversion helper
6. `assign(variables: Dict, variable: str, var_value: Any) -> None` - Smart value assignment

### 1.2 Update Tracing Module

**File to Modify**: `src/AnosysLoggers/tracing.py`

**Changes Required**:

1. **Import shared utilities**:
```python
from .utils import (
    key_to_cvs,
    reassign,
    to_str_or_none,
    assign,
    to_json_fallback,
)
```

2. **Remove duplicate functions**: Delete local copies of utility functions

3. **Add semantic conventions extraction** in `extract_span_info()`:

```python
# OpenTelemetry Semantic Conventions for Gen AI
assign(variables, 'gen_ai.system', 'openai')  # or appropriate AI system

# Extract model information
model_name = llm_attrs.get('model_name')
if model_name:
    assign(variables, 'gen_ai.request.model', to_str_or_none(model_name))

# Extract invocation parameters
if isinstance(invocation_params, dict):
    temperature = invocation_params.get('temperature')
    max_tokens = invocation_params.get('max_tokens')
    top_p = invocation_params.get('top_p')
    
    if temperature is not None:
        assign(variables, 'gen_ai.request.temperature', temperature)
    if max_tokens is not None:
        assign(variables, 'gen_ai.request.max_tokens', max_tokens)
    if top_p is not None:
        assign(variables, 'gen_ai.request.top_p', top_p)

# Extract token usage
if isinstance(token_count, dict):
    input_tokens = token_count.get('prompt_tokens') or token_count.get('input_tokens')
    output_tokens = token_count.get('completion_tokens') or token_count.get('output_tokens')
    
    if input_tokens is not None:
        assign(variables, 'gen_ai.usage.input_tokens', input_tokens)
    if output_tokens is not None:
        assign(variables, 'gen_ai.usage.output_tokens', output_tokens)

# Extract finish reasons
finish_reasons = []
choices = output_value.get('choices', [])
if isinstance(choices, list):
    for choice in choices:
        if isinstance(choice, dict):
            finish_reason = choice.get('finish_reason')
            if finish_reason:
                finish_reasons.append(finish_reason)

if finish_reasons:
    assign(variables, 'gen_ai.response.finish_reasons', finish_reasons)
```

4. **Add status code handling**:

```python
# Status information
status = span.get('status', {})
if status:
    assign(variables, 'status', to_str_or_none(status))
    status_code = status.get('status_code')
    if status_code:
        status_map = {0: 'UNSET', 1: 'OK', 2: 'ERROR'}
        assign(variables, 'status_code', status_map.get(status_code, str(status_code)))
```

5. **Add streaming detection**:

```python
# Check if streaming
is_streaming = invocation_params.get('stream', False) if isinstance(invocation_params, dict) else False
if is_streaming:
    assign(variables, 'is_streaming', True)
```

### 1.3 Update Decorator Module

**File to Modify**: `src/AnosysLoggers/decorator.py`

**Changes Required**:

1. **Import shared utilities** (same as tracing.py)

2. **Remove duplicate code**: Delete ~200 lines of utility functions

3. **Add async support**:

```python
import asyncio
import traceback

def anosys_logger(source=None):
    def decorator(func):
        is_async = asyncio.iscoroutinefunction(func)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            global key_to_cvs
            variables = {}
            
            # Detect caller
            stack = inspect.stack()
            caller_frame = stack[1]
            caller_info = {
                "function": caller_frame.function,
                "file": caller_frame.filename,
                "line": caller_frame.lineno,
            }
            
            error_occurred = False
            result = None
            error_info = None
            
            try:
                result = await func(*args, **kwargs)
            except Exception as e:
                error_occurred = True
                error_info = {
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": traceback.format_exc()
                }
                raise
            finally:
                # Prepare payload with error handling
                input_array = [to_str_or_none(arg) for arg in args]
                if kwargs:
                    input_array.append({"kwargs": kwargs})
                
                assign(variables, "source", to_str_or_none(source))
                assign(variables, "input", input_array)
                assign(variables, "caller", caller_info)
                
                if error_occurred:
                    assign(variables, "error", True)
                    assign(variables, "error_type", error_info["type"])
                    assign(variables, "error_message", error_info["message"])
                    assign(variables, "error_stack", error_info["traceback"])
                    assign(variables, "output", None)
                else:
                    assign(variables, "output", to_json_fallback(result))
                
                # Send log
                # [logging code here]
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Similar implementation for sync functions
            pass
        
        return async_wrapper if is_async else sync_wrapper
    return decorator
```

4. **Remove stdout redirection** - It's unreliable for async functions

### 1.4 Create Tests

**File to Create**: `tests/test_basic.py`

**Test Coverage**:

```python
import pytest
from unittest.mock import Mock, patch

class TestUtils:
    def test_get_type_key(self):
        """Test type detection"""
        
    def test_reassign(self):
        """Test key reassignment to CVS variables"""

class TestDecorator:
    @patch('requests.post')
    def test_sync_function_logging(self, mock_post):
        """Test logging of synchronous functions"""
    
    @patch('requests.post')
    @pytest.mark.asyncio
    async def test_async_function_logging(self, mock_post):
        """Test logging of asynchronous functions"""
    
    @patch('requests.post')
    def test_error_logging(self, mock_post):
        """Test logging when function raises an error"""

class TestRawLogger:
    @patch('requests.post')
    def test_raw_logger_success(self, mock_post):
        """Test raw logger with successful post"""
```

---

## Part 2: Node.js Package Improvements

### 2.1 Update Main Module

**File to Modify**: `index.js`

**Key Changes**:

1. **Add imports for semantic conventions**:

```javascript
import { NodeTracerProvider, Resource } from "@opentelemetry/sdk-trace-node";
import { SimpleSpanProcessor } from "@opentelemetry/sdk-trace-base";
import { trace, SpanStatusCode } from "@opentelemetry/api";
import { SemanticResourceAttributes } from "@opentelemetry/semantic-conventions";
import packageJson from "./package.json" assert { type: "json" };
```

2. **Update key mappings** to include semantic conventions:

```javascript
const keyToCV = {
  // ... existing mappings ...
  
  // OpenTelemetry Semantic Conventions for Gen AI
  "gen_ai.system": "gen_ai_system",
  "gen_ai.request.model": "gen_ai_request_model",
  "gen_ai.response.model": "gen_ai_response_model",
  "gen_ai.request.temperature": "gen_ai_request_temperature",
  "gen_ai.request.max_tokens": "gen_ai_request_max_tokens",
  "gen_ai.request.top_p": "gen_ai_request_top_p",
  "gen_ai.response.finish_reasons": "gen_ai_response_finish_reasons",
  "gen_ai.usage.input_tokens": "gen_ai_usage_input_tokens",
  "gen_ai.usage.output_tokens": "gen_ai_usage_output_tokens",
  
  // Error tracking
  "error": "cvs3",
  "error_type": "cvs10",
  "error_message": "cvs11",
  "error_stack": "cvs12",
  
  "is_streaming": "cvb2",
};
```

3. **Add semantic conventions to exporter**:

```javascript
class AnoSysExporter {
  async export(spans, resultCallback) {
    for (const span of spans) {
      // Parse result and arguments
      let result = null;
      let args = null;
      let isStreaming = false;
      
      try {
        if (attrs["openai.result"]) {
          result = typeof attrs["openai.result"] === "string" 
            ? JSON.parse(attrs["openai.result"]) 
            : attrs["openai.result"];
        }
        if (attrs["openai.args"]) {
          args = typeof attrs["openai.args"] === "string"
            ? JSON.parse(attrs["openai.args"])
            : attrs["openai.args"];
          isStreaming = args[0]?.stream === true;
        }
      } catch (e) {
        console.error("[ANOSYS]⚠️ Error parsing attributes:", e.message);
      }
      
      const payload = {
        // ... existing fields ...
        
        // Status information
        status_code: span.status?.code !== undefined ? 
          ['UNSET', 'OK', 'ERROR'][span.status.code] : null,
        
        // OpenTelemetry Semantic Conventions for Gen AI
        "gen_ai.system": "openai",
        "gen_ai.request.model": args?.[0]?.model || null,
        "gen_ai.response.model": result?.model || null,
        "gen_ai.request.temperature": args?.[0]?.temperature || null,
        "gen_ai.request.max_tokens": args?.[0]?.max_tokens || null,
        "gen_ai.request.top_p": args?.[0]?.top_p || null,
        "gen_ai.response.finish_reasons": result?.choices?.map(c => c.finish_reason).filter(Boolean) || null,
        "gen_ai.usage.input_tokens": result?.usage?.prompt_tokens || null,
        "gen_ai.usage.output_tokens": result?.usage?.completion_tokens || null,
        
        // Streaming flag
        is_streaming: isStreaming,
      };
    }
  }
}
```

4. **Add resource attributes**:

```javascript
function setupTracing(apiUrl) {
  if (apiUrl) logApiUrl = apiUrl;

  const resource = Resource.default().merge(
    new Resource({
      [SemanticResourceAttributes.SERVICE_NAME]: "anosys-openai-logger",
      [SemanticResourceAttributes.SERVICE_VERSION]: packageJson.version,
      "telemetry.sdk.name": "anosys",
    })
  );

  const tracerProvider = new NodeTracerProvider({ resource });
  tracerProvider.addSpanProcessor(
    new SimpleSpanProcessor(new AnoSysExporter())
  );
  tracerProvider.register();
  trace.setGlobalTracerProvider(tracerProvider);

  return trace.getTracer("anosys-openai", packageJson.version);
}
```

5. **Add streaming support**:

```javascript
function wrapMethod(obj, methodName, spanName) {
  const original = obj[methodName];
  if (typeof original !== "function") return;

  obj[methodName] = async function (...args) {
    const span = tracer.startSpan(spanName);
    const isStreaming = args[0]?.stream === true;
    
    try {
      const result = await original.apply(this, args);
      
      span.setAttribute("openai.method", spanName);
      span.setAttribute("openai.args", JSON.stringify(args));
      
      // Handle streaming responses
      if (isStreaming && result && typeof result[Symbol.asyncIterator] === 'function') {
        const chunks = [];
        const wrappedIterator = async function* () {
          try {
            for await (const chunk of result) {
              chunks.push(chunk);
              yield chunk;
            }
            
            // After streaming completes, aggregate and log
            const aggregated = aggregateStreamChunks(chunks);
            span.setAttribute("openai.result", JSON.stringify(aggregated));
            span.setStatus({ code: SpanStatusCode.OK });
          } catch (streamErr) {
            span.recordException(streamErr);
            span.setStatus({ code: SpanStatusCode.ERROR, message: streamErr.message });
            throw streamErr;
          } finally {
            span.end();
          }
        };
        
        return wrappedIterator();
      } else {
        // Non-streaming response
        span.setAttribute("openai.result", JSON.stringify(result));
        span.setStatus({ code: SpanStatusCode.OK });
        span.end();
        return result;
      }
    } catch (err) {
      span.recordException(err);
      span.setStatus({ code: SpanStatusCode.ERROR, message: err.message });
      span.end();
      throw err;
    }
  };
}

// Helper to aggregate streaming chunks
function aggregateStreamChunks(chunks) {
  if (!chunks.length) return {};
  
  const aggregated = {
    id: chunks[0]?.id,
    object: chunks[0]?.object,
    created: chunks[0]?.created,
    model: chunks[0]?.model,
    choices: [],
  };
  
  // Aggregate content from chunks
  const choiceMap = new Map();
  for (const chunk of chunks) {
    for (const choice of chunk.choices || []) {
      if (!choiceMap.has(choice.index)) {
        choiceMap.set(choice.index, {
          index: choice.index,
          message: { role: 'assistant', content: '' },
          finish_reason: null,
        });
      }
      const existing = choiceMap.get(choice.index);
      if (choice.delta?.content) {
        existing.message.content += choice.delta.content;
      }
      if (choice.finish_reason) {
        existing.finish_reason = choice.finish_reason;
      }
    }
  }
  
  aggregated.choices = Array.from(choiceMap.values());
  
  // Add usage if present in last chunk
  const lastChunk = chunks[chunks.length - 1];
  if (lastChunk?.usage) {
    aggregated.usage = lastChunk.usage;
  }
  
  return aggregated;
}
```

6. **Improve decorator with error handling**:

```javascript
export function anosysLogger(source = null) {
  return function (fn) {
    const original = fn;
    const isAsync = original.constructor.name === 'AsyncFunction';

    async function decoratedAsync(...args) {
      let errorOccurred = false;
      let errorInfo = null;
      let result;
      
      try {
        result = await original.apply(this, args);
      } catch (err) {
        errorOccurred = true;
        errorInfo = {
          type: err.name,
          message: err.message,
          stack: err.stack
        };
        throw err;
      } finally {
        const payload = {
          from_source: source,
          input: JSON.stringify(args),
          name: original.name || "anonymous",
        };
        
        if (errorOccurred) {
          payload.error = true;
          payload.error_type = errorInfo.type;
          payload.error_message = errorInfo.message;
          payload.error_stack = errorInfo.stack;
          payload.output = null;
        } else {
          payload.output = typeof output === 'object' ? JSON.stringify(output) : String(output);
        }
        
        // Log payload
      }
      return result;
    }
    
    // Similar for sync version
    
    return isAsync ? decoratedAsync : decoratedSync;
  };
}
```

### 2.2 Update Package Dependencies

**File to Modify**: `package.json`

**Add dependency**:

```json
{
  "dependencies": {
    "@opentelemetry/semantic-conventions": "^1.7.0"
  }
}
```

### 2.3 Create Tests

**File to Create**: `test/basic.test.js`

```javascript
import { describe, it } from 'node:test';
import assert from 'node:assert';
import { anosysLogger, anosysRawLogger, setupAPI } from '../index.js';

describe('Decorator Tests', () => {
  it('should log synchronous function execution', () => {
    // Test sync function
  });
  
  it('should log async function execution', async () => {
    // Test async function
  });
  
  it('should handle errors', () => {
    // Test error handling
  });
});
```

---

## Part 3: Documentation

### 3.1 Create Comprehensive README

**For both Python and Node.js**, create README.md with:

1. **Installation instructions**
2. **Quick start example**
3. **Streaming support examples**
4. **Custom decorator examples**
5. **OpenTelemetry semantic conventions table**
6. **Error handling examples**
7. **Environment variables**
8. **Troubleshooting section**

**Example Structure**:

```markdown
# Package Name

## Features
- Automatic instrumentation
- Streaming support
- Semantic conventions
- Error tracking

## Installation
[pip/npm install instructions]

## Quick Start
[Basic usage code]

## Advanced Usage
### Streaming
[Streaming example]

### Custom Decorators
[Decorator examples]

## What Data is Captured?
[Semantic conventions table]

## Troubleshooting
[Common issues and solutions]
```

---

## Part 4: Key Semantic Conventions

Ensure these semantic convention fields are extracted and logged:

| Field | Description | Example |
|-------|-------------|---------|
| `gen_ai.system` | AI system name | "openai" |
| `gen_ai.request.model` | Model requested | "gpt-4" |
| `gen_ai.response.model` | Model that responded | "gpt-4-0613" |
| `gen_ai.request.temperature` | Temperature parameter | 0.7 |
| `gen_ai.request.max_tokens` | Max tokens | 1000 |
| `gen_ai.request.top_p` | Top-p parameter | 0.9 |
| `gen_ai.response.finish_reasons` | Why response ended | ["stop"] |
| `gen_ai.usage.input_tokens` | Input tokens | 45 |
| `gen_ai.usage.output_tokens` | Output tokens | 120 |

Reference: https://opentelemetry.io/docs/specs/semconv/gen-ai/

---

## Implementation Checklist

### Python Package
- [ ] Create `utils.py` with shared functions
- [ ] Update `tracing.py` to import from utils
- [ ] Update `decorator.py` to import from utils
- [ ] Add semantic conventions to `tracing.py`
- [ ] Add async support to `decorator.py`
- [ ] Add error handling with stack traces
- [ ] Create `test_basic.py` with unit tests
- [ ] Update README with examples

### Node.js Package
- [ ] Add semantic-conventions dependency
- [ ] Update key mappings
- [ ] Add semantic conventions to exporter
- [ ] Add resource attributes
- [ ] Implement streaming support with chunk aggregation
- [ ] Add error handling to decorator
- [ ] Create `basic.test.js`
- [ ] Update README with examples

### Both Packages
- [ ] Test with real API calls
- [ ] Verify semantic conventions are captured
- [ ] Test streaming functionality
- [ ] Test error scenarios
- [ ] Verify backward compatibility

---

## Testing Instructions

### Python
```bash
cd python
pip install pytest pytest-asyncio
pytest tests/test_basic.py -v
```

### Node.js
```bash
cd node
npm install
node test/basic.test.js
```

### Manual Testing
1. Test basic instrumentation
2. Test streaming responses
3. Test error handling
4. Verify semantic conventions in logged data

---

## Expected Outcomes

After implementing these changes:

1. ✅ **Reduced Code Duplication** - ~200 lines removed in Python
2. ✅ **Better Observability** - OpenTelemetry semantic conventions
3. ✅ **Streaming Support** - Full capture of streaming responses
4. ✅ **Error Tracking** - Complete error context with stack traces
5. ✅ **Test Coverage** - Unit tests for core functionality
6. ✅ **Better Documentation** - Clear usage examples

---

## Notes for Implementation

- Maintain backward compatibility with existing field names
- Test with different AI models and endpoints
- Ensure streaming doesn't impact performance
- Validate all semantic conventions are properly mapped
- Keep error logging comprehensive but not excessive

---

## Support References

- OpenTelemetry Gen AI Conventions: https://opentelemetry.io/docs/specs/semconv/gen-ai/
- Python asyncio documentation: https://docs.python.org/3/library/asyncio.html
- JavaScript async iterators: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/for-await...of
