import { NodeTracerProvider } from "@opentelemetry/sdk-trace-node";
import { SimpleSpanProcessor } from "@opentelemetry/sdk-trace-base";
import { trace } from "@opentelemetry/api";
import axios from "axios";

let logApiUrl = "https://www.anosys.ai";

function convertCvsToStrings(obj) {
  const result = { ...obj }; // shallow copy to avoid mutating original

  for (const key in result) {
    if (key.startsWith("cvs")) {
      const value = result[key];
      if (typeof value !== "string") {
        if (value === undefined || value === null) {
          result[key] = String(value); // "undefined" or "null"
        } else {
          result[key] = JSON.stringify(value);
        }
      }
    }
  }
  return result;
}

function renameKeysWithMap(obj, keyToCvsMap) {
  const renamed = {};
  let counter = 100; // start from cvs27 if no map exists

  for (const [key, value] of Object.entries(obj)) {
    // skip null or undefined values
    if (value === null || value === undefined) continue;

    if (keyToCvsMap[key]) {
      // already in map
      renamed[keyToCvsMap[key]] = value;
    } else {
      // assign next available cvsXXX
      const newKey = `cvs${counter}`;
      renamed[newKey] = value;

      // update the map so the same unknown key is consistent later
      keyToCvsMap[key] = newKey;

      counter++;
    }
  }
  return convertCvsToStrings(renamed);
}

const key_to_cvs = {
  name: "cvs1",
  trace_id: "cvs2",
  span_id: "cvs3",
  trace_state: "cvs4",
  parent_id: "cvs5",
  start_time: "cvs6",
  cvi1: "cvi1",
  end_time: "cvs7",
  cvi2: "cvi2",
  llm_tools: "cvs8",
  llm_token_count: "cvs9",
  llm_output_messages: "cvs10",
  llm_input_messages: "cvs11",
  llm_model_name: "cvs12",
  llm_invocation_parameters: "cvs13",
  input: "cvs14",
  output: "cvs15",
  tool: "cvs16",
  kind: "cvs17",
  resp_id: "cvs18",
  from_source: "cvs200",

  duration_ms: "cvs19",
  trace_flags: "cvs20",
  status: "cvs21",
  resource: "cvs22",
  events: "cvs23",
  links: "cvs24",
  model_method: "cvs25",
  model_arguments: "cvs26",
};

class AnoSysExporter {
  async export(spans, resultCallback) {
    for (const span of spans) {
      const ctx = span.spanContext();
      const payload = {
        from_source: "openAI_Telemetry_in_node",
        name: span.name || null,
        trace_id: ctx.traceId || null,
        span_id: ctx.spanId || null,
        parent_id: span?.parentSpanId || null,
        trace_flags: ctx.traceFlags || null,
        trace_state: ctx.traceState?.serialize() || null,
        kind: span.kind || null,
        start_time: new Date(hrTimeToMillis(span.startTime)).toISOString(),
        end_time: new Date(hrTimeToMillis(span.endTime)).toISOString(),
        cvi1: hrTimeToMillis(span.startTime),
        cvi2: hrTimeToMillis(span.endTime),

        duration_ms:
          hrTimeToMillis(span.endTime) - hrTimeToMillis(span.startTime),
        status: span.status || null,
        model_method: span.attributes?.["openai.method"] || null,
        model_arguments: span.attributes?.["openai.args"] || null,
        output: span.attributes?.["openai.result"] || null,
        events: span.events?.map((e) => ({
          name: e.name,
          time: hrTimeToMillis(e.time),
          attributes: e.attributes,
        })),
        links: span.links?.map((l) => ({
          trace_id: l.context.traceId,
          span_id: l.context.spanId,
          attributes: l.attributes,
        })),
        resource: span.resource?.attributes, // if available
        resp_id: JSON.parse(span.attributes?.["openai.result"] || "{}")?.id,
        llm_model_name: JSON.parse(span.attributes?.["openai.result"] || "{}")
          ?.model,
        llm_token_count: JSON.parse(span.attributes?.["openai.result"] || "{}")
          ?.usage,
      };
      try {
        await axios.post(logApiUrl, renameKeysWithMap(payload, key_to_cvs), {
          timeout: 5000,
        });
      } catch (err) {
        console.error("[ANOSYS] POST failed:", err.message);
      }
    }
    resultCallback({ code: 0 });
  }
  shutdown() {
    return Promise.resolve();
  }
}

function hrTimeToMillis(hrtime) {
  if (!Array.isArray(hrtime)) return null;
  const [seconds, nanos] = hrtime;
  return seconds * 1000 + Math.round(nanos / 1e6);
}

function setupTracing(apiUrl) {
  if (apiUrl) logApiUrl = apiUrl;

  const tracerProvider = new NodeTracerProvider();
  tracerProvider.addSpanProcessor(
    new SimpleSpanProcessor(new AnoSysExporter())
  );
  tracerProvider.register();
  trace.setGlobalTracerProvider(tracerProvider);

  return trace.getTracer("anosys-openai");
}

export function instrumentOpenAI(client) {
  let tracer = setupTracing("https://www.anosys.ai");

  if (process.env.ANOSYS_API_KEY) {
    axios
      .get(
        `https://api.anosys.ai/api/resolveapikeys?apikey=${process.env.ANOSYS_API_KEY}`,
        { timeout: 5000 } // 5 seconds
      )
      .then((response) => {
        const data = response.data;
        const logApiUrl = data.url || "https://www.anosys.ai";
        tracer = setupTracing(logApiUrl);
      })
      .catch((error) => {
        console.error("[ERROR] Failed to resolve API key:", error.message);
      });
  }

  function wrapMethod(obj, methodName, spanName) {
    const original = obj[methodName];
    if (typeof original !== "function") return;

    obj[methodName] = async function (...args) {
      const span = tracer.startSpan(spanName);
      try {
        const result = await original.apply(this, args);
        span.setAttribute("openai.method", spanName);
        span.setAttribute("openai.args", JSON.stringify(args));
        span.setAttribute("openai.result", JSON.stringify(result));
        span.end();
        return result;
      } catch (err) {
        span.recordException(err);
        span.end();
        throw err;
      }
    };
  }

  // Patch specific OpenAI methods (can expand this list)
  if (client.chat?.completions) {
    wrapMethod(client.chat.completions, "create", "chat.completions.create");
  }
  if (client.embeddings) {
    wrapMethod(client.embeddings, "create", "embeddings.create");
  }
  if (client.images?.generate) {
    wrapMethod(client.images, "generate", "images.generate");
  }

  console.log("[ANOSYS] OpenAI client instrumented");
}

///////
// ---------- NEW DECORATOR-LIKE WRAPPER ----------
export function anosysLogger(source = null) {
  return function (fn) {
    return async function (...args) {
      let output;
      let result;
      console.log(`[ANOSYS Logger: ${source}] Starting...`);
      console.log(`[ANOSYS Logger: ${source}] Input args:`, args);

      try {
        result = await fn.apply(this, args);
        output = result;
      } catch (err) {
        output = { error: err.message, stack: err.stack };
        throw err; // rethrow after logging
      } finally {
        const payload = {
          from_source: source,
          input: JSON.stringify(args),
          output: JSON.stringify(output),
          name: fn.name || "anonymous",
        };

        try {
          await axios.post(logApiUrl, renameKeysWithMap(payload, key_to_cvs), {
            timeout: 5000,
          });
          console.log(`[ANOSYS Logger: ${source}] Logged successfully.`);
        } catch (err) {
          console.error("[ANOSYS] POST failed:", err.message);
          console.error("[ANOSYS] Data:", JSON.stringify(payload, null, 2));
        }
      }
      return result;
    };
  };
}

export function setupDecorator() {
  if (process.env.ANOSYS_API_KEY) {
    axios
      .get(
        `https://api.anosys.ai/api/resolveapikeys?apikey=${process.env.ANOSYS_API_KEY}`,
        { timeout: 5000 } // 5 seconds
      )
      .then((response) => {
        const data = response.data;
        logApiUrl = data.url || "https://www.anosys.ai";
      })
      .catch((error) => {
        console.error("[ERROR] Failed to resolve API key:", error.message);
      });
  } else {
    console.log(
      "[ERROR] ANOSYS_API_KEY not found. Please obtain your API key from https://console.anosys.ai/collect/integrationoptions"
    );
  }
}
