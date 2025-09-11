import { NodeTracerProvider } from "@opentelemetry/sdk-trace-node";
import { SimpleSpanProcessor } from "@opentelemetry/sdk-trace-base";
import { trace } from "@opentelemetry/api";
import axios from "axios";

let logApiUrl = "https://www.anosys.ai";

// Key mappings
const keyToCV = {
  name: "cvs1",
  trace_id: "cvs2",
  span_id: "cvs3",
  trace_state: "cvs4",
  parent_id: "cvs5",
  start_time: "cvs6",
  cvn1: "cvn1",
  end_time: "cvs7",
  cvn2: "cvn2",
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
  duration_ms: "cvs10",
  trace_flags: "cvs11",
  status: "cvs12",
  resource: "cvs13",
  events: "cvs14",
  links: "cvs15",
  model_method: "cvs16",
  model_arguments: "cvs17",
};

// Separate starting indices per type
const globalStartingIndices = {
  string: 100,
  number: 3,
  bool: 1,
};

// --- Utility functions ---

function getTypeKey(value) {
  if (typeof value === "boolean") return "bool";
  if (typeof value === "number") {
    return Number.isInteger(value) ? "int" : "float";
  }
  if (typeof value === "string") return "string";
  return "string"; // default for objects/arrays
}

function getPrefixAndIndex(typeKey) {
  switch (typeKey) {
    case "bool":
      return ["cvb", "bool"];
    case "int":
    case "float":
      return ["cvn", "number"];
    case "string":
    default:
      return ["cvs", "string"];
  }
}

function stringifyIfNeeded(value) {
  if (value === null || value === undefined) return value;
  if (typeof value === "object") return JSON.stringify(value);
  return value;
}

function renameKeysWithMap(obj, keyToCvsMap) {
  const renamed = {};
  let counter = 100;

  for (const [key, value] of Object.entries(obj)) {
    if (value === null || value === undefined) continue;

    if (keyToCvsMap[key]) {
      renamed[keyToCvsMap[key]] = stringifyIfNeeded(value);
    } else {
      const newKey = `cvs${counter}`;
      renamed[newKey] = stringifyIfNeeded(value);
      keyToCvsMap[key] = newKey;
      counter++;
    }
  }
  return renamed;
}

function reassign(data, startingIndices = null) {
  const indices = startingIndices
    ? { ...startingIndices }
    : { ...globalStartingIndices };
  const mapped = {};

  for (const [key, value] of Object.entries(data)) {
    const typeKey = getTypeKey(value);
    const [prefix, idxKey] = getPrefixAndIndex(typeKey);

    if (!(key in keyToCV)) {
      keyToCV[key] = `${prefix}${indices[idxKey]}`;
      indices[idxKey]++;
    }

    const cvVar = keyToCV[key];
    mapped[cvVar] = stringifyIfNeeded(value);
  }

  Object.assign(globalStartingIndices, indices);
  return mapped;
}

// --- OpenTelemetry Exporter ---

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
        cvn1: hrTimeToMillis(span.startTime),
        cvn2: hrTimeToMillis(span.endTime),
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
        resource: span.resource?.attributes,
        resp_id: JSON.parse(span.attributes?.["openai.result"] || "{}")?.id,
        llm_model_name: JSON.parse(span.attributes?.["openai.result"] || "{}")
          ?.model,
        llm_token_count: JSON.parse(span.attributes?.["openai.result"] || "{}")
          ?.usage,
      };

      try {
        await axios.post(logApiUrl, renameKeysWithMap(payload, keyToCV), {
          timeout: 5000,
        });
      } catch (err) {
        console.error("[ANOSYS]❌ POST failed:", err.message);
      }
    }
    resultCallback({ code: 0 });
  }
  shutdown() {
    return Promise.resolve();
  }
}

// --- Helpers ---

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

// --- Public API ---

export function instrumentOpenAI(client) {
  let tracer = setupTracing("https://www.anosys.ai");

  if (process.env.ANOSYS_API_KEY) {
    axios
      .get(
        `https://api.anosys.ai/api/resolveapikeys?apikey=${process.env.ANOSYS_API_KEY}`,
        { timeout: 5000 }
      )
      .then((response) => {
        const data = response.data;
        const apiUrl = data.url || "https://www.anosys.ai";
        tracer = setupTracing(apiUrl);
      })
      .catch((error) => {
        console.error("[ERROR]❌ Failed to resolve API key:", error.message);
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

export function anosysLogger(source = null) {
  return function (fn) {
    const original = fn;

    async function decorated(...args) {
      let output;
      let result;
      console.log(`[ANOSYS] Logger: ${source}] Starting...`);
      console.log(`[ANOSYS] Logger: Input args:`, JSON.stringify(args));

      try {
        result = await original.apply(this, args);
        output = result;
      } catch (err) {
        output = { error: err.message, stack: err.stack };
        throw err;
      } finally {
        console.log(`[ANOSYS] Logger: Output args:`, JSON.stringify(output));
        const payload = {
          from_source: source,
          input: args.toString(),
          output: output.toString(),
          name: original.name || "anonymous",
        };

        try {
          await axios.post(logApiUrl, renameKeysWithMap(payload, keyToCV), {
            timeout: 5000,
          });
          console.log(
            `[ANOSYS] Logger: ${source} Logged successfully, mapping: ${JSON.stringify(
              keyToCV,
              null,
              2
            )}.`
          );
          console.log(renameKeysWithMap(payload, keyToCV));
        } catch (err) {
          console.error("[ANOSYS]❌ POST failed:", err.message);
          console.error("[ANOSYS]❌ Data:", JSON.stringify(payload, null, 2));
        }
      }
      return result;
    }

    Object.defineProperty(decorated, "name", { value: fn.name });
    return decorated;
  };
}

export async function anosysRawLogger(data = {}) {
  try {
    await axios.post(logApiUrl, reassign(data, globalStartingIndices), {
      timeout: 5000,
    });
    console.log(
      `[ANOSYS] Logger: ${JSON.stringify(
        data
      )} Logged successfully, mapping: ${JSON.stringify(keyToCV, null, 2)}.`
    );
  } catch (err) {
    console.error("[ANOSYS]❌ POST failed:", err.message);
    console.error(
      `[ANOSYS]❌ POST response: ${JSON.stringify(err.response.data)}`
    );
    console.log(JSON.stringify(data, null, 2));
  }
}

export function setupAPI({ path = null, startingIndices = null }) {
  if (startingIndices) {
    Object.assign(globalStartingIndices, startingIndices);
  }

  if (path) {
    logApiUrl = path;
    return;
  }

  if (process.env.ANOSYS_API_KEY) {
    axios
      .get(
        `https://api.anosys.ai/api/resolveapikeys?apikey=${process.env.ANOSYS_API_KEY}`,
        { timeout: 5000 }
      )
      .then((response) => {
        const data = response.data;
        logApiUrl = data.url || "https://www.anosys.ai";
      })
      .catch((error) => {
        console.error("[ERROR]❌ Failed to resolve API key:", error.message);
      });
  } else {
    console.log(
      "[ERROR]‼️ ANOSYS_API_KEY not found. Please obtain your API key from https://console.anosys.ai/collect/integrationoptions"
    );
  }
}
