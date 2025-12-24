import { NodeTracerProvider } from "@opentelemetry/sdk-trace-node";
import { SimpleSpanProcessor } from "@opentelemetry/sdk-trace-base";
import { trace } from "@opentelemetry/api";
import axios from "axios";

let logApiUrl = "https://www.anosys.ai";

// Key mappings
const keyToCV = {
    // OpenTelemetry core fields
    cvn1: "cvn1",
    cvn2: "cvn2",
    name: "otel_name",
    trace_id: "otel_trace_id",
    span_id: "otel_span_id",
    trace_state: "otel_trace_flags",
    parent_id: "otel_parent_span_id",
    start_time: "otel_start_time",
    end_time: "otel_end_time",
    kind: "otel_kind",
    resp_id: "otel_status_message",
    status: "otel_status",
    status_code: "otel_status_code",

    // --- General & System ---
    "gen_ai.system": "gen_ai_system",
    "gen_ai.provider.name": "gen_ai_provider_name",
    "gen_ai.operation.name": "gen_ai_operation_name",
    "server.address": "server_address",
    "server.port": "server_port",
    "error.type": "error_type",

    // --- Request Configuration (LLM) ---
    "gen_ai.request.model": "gen_ai_request_model",
    "gen_ai.request.temperature": "gen_ai_request_temperature",
    "gen_ai.request.top_p": "gen_ai_request_top_p",
    "gen_ai.request.top_k": "gen_ai_request_top_k",
    "gen_ai.request.max_tokens": "gen_ai_request_max_tokens",
    "gen_ai.request.frequency_penalty": "gen_ai_request_frequency_penalty",
    "gen_ai.request.presence_penalty": "gen_ai_request_presence_penalty",
    "gen_ai.request.stop_sequences": "gen_ai_request_stop_sequences",
    "gen_ai.request.seed": "gen_ai_request_seed",
    "gen_ai.request.choice.count": "gen_ai_request_choice_count",
    "gen_ai.request.encoding_formats": "gen_ai_request_encoding_formats",

    // --- Response & Usage (LLM) ---
    "gen_ai.response.model": "gen_ai_response_model",
    "gen_ai.response.id": "gen_ai_response_id",
    "gen_ai.response.finish_reasons": "gen_ai_response_finish_reasons",
    "gen_ai.usage.input_tokens": "gen_ai_usage_input_tokens",
    "gen_ai.usage.output_tokens": "gen_ai_usage_output_tokens",
    "gen_ai.usage.total_tokens": "gen_ai_usage_total_tokens",
    "gen_ai.output.type": "gen_ai_output_type",

    // --- Content & Messages (Opt-In) ---
    "gen_ai.input.messages": "gen_ai_input_messages",
    "gen_ai.output.messages": "gen_ai_output_messages",
    "gen_ai.system_instructions": "gen_ai_system_instructions",
    "gen_ai.tool.definitions": "gen_ai_tool_definitions",

    // --- Agents & Frameworks ---
    "gen_ai.agent.id": "gen_ai_agent_id",
    "gen_ai.agent.name": "gen_ai_agent_name",
    "gen_ai.agent.description": "gen_ai_agent_description",
    "gen_ai.conversation.id": "gen_ai_conversation_id",
    "gen_ai.data_source.id": "gen_ai_data_source_id",

    // --- Embeddings Specific ---
    "gen_ai.embeddings.dimension.count": "gen_ai_embeddings_dimension_count",

    // Legacy LLM fields (backward compatibility)
    input: "cvs1",
    output: "cvs2",
    tool: "cvs3",
    llm_tools: "cvs4",
    llm_token_count: "cvs5",
    llm_output_messages: "cvs6",
    llm_input_messages: "cvs7",
    llm_model_name: "cvs8",
    llm_invocation_parameters: "cvs9",
    raw: "cvs199",
    from_source: "cvs200",
    duration_ms: "otel_duration_ms",
    trace_flags: "cvs11",
    resource: "cvs13",
    events: "cvs14",
    links: "cvs15",
    model_method: "cvs16",
    model_arguments: "cvs17",
    is_streaming: "cvb1",
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

            // Parse OpenAI result
            let result = {};
            try {
                result = JSON.parse(span.attributes?.["openai.result"] || "{}");
            } catch (e) {
                result = {};
            }

            // Parse OpenAI args to get invocation parameters
            let args = [];
            let invocationParams = {};
            try {
                args = JSON.parse(span.attributes?.["openai.args"] || "[]");
                invocationParams = args[0] || {};
            } catch (e) {
                invocationParams = {};
            }

            // Extract operation name from span name (e.g., "chat.completions.create" -> "chat")
            const operationName = span.name ? span.name.split('.')[0] : null;

            // Determine output type
            let outputType = null;
            const objectType = result.object;
            if (objectType) {
                if (objectType.includes('chat')) {
                    outputType = 'text';
                } else if (objectType.includes('embedding')) {
                    outputType = 'embedding';
                } else if (objectType.includes('image')) {
                    outputType = 'image';
                }
            }
            // Check for JSON mode
            if (invocationParams.response_format?.type === 'json_object') {
                outputType = 'json';
            }

            // Extract server address/port from resources
            const serverAddress = span.resource?.attributes?.['server.address'] || 'api.openai.com';
            const serverPort = span.resource?.attributes?.['server.port'] || 443;

            // Extract input messages - try multiple sources
            let inputMessages = invocationParams.messages || null;

            // Extract system instructions from messages
            let systemInstructions = null;
            if (inputMessages && Array.isArray(inputMessages)) {
                const systemMsg = inputMessages.find(m => m.role === 'system');
                if (systemMsg) {
                    systemInstructions = systemMsg.content;
                }
            }

            // Extract output messages from choices
            let outputMessages = null;
            if (result.choices && Array.isArray(result.choices)) {
                outputMessages = result.choices
                    .map(c => c.message)
                    .filter(Boolean);
                if (outputMessages.length === 0) {
                    outputMessages = null;
                }
            }

            // Extract tools from invocation params
            const tools = invocationParams.tools || null;

            const payload = {
                raw: JSON.stringify(result),
                from_source: "openAI_Node_Telemetry",
                name: span.name || null,
                trace_id: ctx.traceId || null,
                span_id: ctx.spanId || null,
                parent_id: span?.parentSpanId || null,
                trace_flags: ctx.traceFlags ? String(ctx.traceFlags) : null,
                trace_state: ctx.traceState?.serialize() || null,
                kind: span.kind || null,
                start_time: new Date(hrTimeToMillis(span.startTime)).toISOString(),
                end_time: new Date(hrTimeToMillis(span.endTime)).toISOString(),
                cvn1: hrTimeToMillis(span.startTime),
                cvn2: hrTimeToMillis(span.endTime),
                duration_ms:
                    hrTimeToMillis(span.endTime) - hrTimeToMillis(span.startTime),
                status: span.status || null,

                // --- General & System ---
                "gen_ai.system": "openai",
                "gen_ai.provider.name": "openai",
                "gen_ai.operation.name": operationName,
                "server.address": serverAddress,
                "server.port": serverPort,

                // --- Request Configuration (LLM) ---
                "gen_ai.request.model": invocationParams.model || null,
                "gen_ai.request.temperature": invocationParams.temperature ?? null,
                "gen_ai.request.top_p": invocationParams.top_p ?? null,
                "gen_ai.request.top_k": invocationParams.top_k ?? null,
                "gen_ai.request.max_tokens": invocationParams.max_tokens ?? null,
                "gen_ai.request.frequency_penalty": invocationParams.frequency_penalty ?? null,
                "gen_ai.request.presence_penalty": invocationParams.presence_penalty ?? null,
                "gen_ai.request.stop_sequences": invocationParams.stop ?? null,
                "gen_ai.request.seed": invocationParams.seed ?? null,
                "gen_ai.request.choice.count": invocationParams.n ?? null,

                // --- Response & Usage (LLM) ---
                "gen_ai.response.model": result.model || null,
                "gen_ai.response.id": result.id || null,
                "gen_ai.response.finish_reasons": result.choices?.map(c => c.finish_reason).filter(Boolean) || null,
                "gen_ai.usage.input_tokens": result.usage?.prompt_tokens ?? null,
                "gen_ai.usage.output_tokens": result.usage?.completion_tokens ?? null,
                "gen_ai.usage.total_tokens": result.usage?.total_tokens ?? null,
                "gen_ai.output.type": outputType,

                // --- Content & Messages (Opt-In) ---
                "gen_ai.input.messages": inputMessages,
                "gen_ai.output.messages": outputMessages,
                "gen_ai.system_instructions": systemInstructions,
                "gen_ai.tool.definitions": tools,

                // Legacy fields for backward compatibility
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
                resp_id: result.id || null,
                llm_model_name: result.model || null,
                llm_token_count: result.usage || null,
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

    const tracerProvider = new NodeTracerProvider({
        spanProcessors: [new SimpleSpanProcessor(new AnoSysExporter())]
    });
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
                    raw: JSON.stringify({
                        source,
                        input: args,
                        output,
                        name: original.name || "anonymous"
                    }),
                    from_source: source,
                    input: JSON.stringify(args),
                    output: JSON.stringify(output),
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
