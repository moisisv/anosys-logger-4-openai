
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from traceai_openai import OpenAIInstrumentor
import threading
import json
from datetime import datetime
import requests

# Prevent re-initialization
_lock = threading.Lock()
log_api_url="https://www.anosys.ai"

def _to_timestamp(dt_str):
    if not dt_str:
        return None
    try:
        return int(datetime.fromisoformat(dt_str).timestamp() )
    except ValueError:
        return None

key_to_cvs = {
  "name": "cvs1",
  "trace_id": "cvs2",
  "span_id": "cvs3",
  "trace_state": "cvs4",
  "parent_id": "cvs5",
  "start_time": "cvs6",
  "cvn1": "cvn1",
  "end_time": "cvs7",
  "cvn2": "cvn2",
  "llm_tools": "cvs8",
  "llm_token_count": "cvs9",
  "llm_output_messages": "cvs10",
  "llm_input_messages": "cvs11",
  "llm_model_name": "cvs12",
  "llm_invocation_parameters": "cvs13",
  "input": "cvs14",
  "output": "cvs15",
  "tool": "cvs16",
  "kind": "cvs17",
  "resp_id":"cvs18",
  "from_source": "cvs200"
}

def reassign(data, starting_index=100):
    global key_to_cvs
    cvs_vars = {}

    if isinstance(data, str):
        data = json.loads(data)

    if not isinstance(data, dict):
        raise ValueError("Input must be a dict or JSON string representing a dict")

    cvs_index = starting_index

    for key, value in data.items():
        if key not in key_to_cvs:
            key_to_cvs[key] = f"cvs{cvs_index}"
            cvs_index += 1
        cvs_var = key_to_cvs[key]
        # Only convert to string if value is not None
        cvs_vars[cvs_var] = str(value) if value is not None else None

    return cvs_vars

def extract_span_info(span):
    variables = {}

    def to_str_or_none(val):
        if val is None:
            return None
        if isinstance(val, (dict, list)):
            return json.dumps(val)
        return str(val)

    def assign(variable, var_value):
        if var_value is None:
            variables[variable] = None
        elif isinstance(var_value, str):
            var_value = var_value.strip()
            # Try to parse JSON strings if they look like objects/arrays
            if var_value.startswith('{') or var_value.startswith('['):
                try:
                    parsed = json.loads(var_value)
                    variables[variable] = json.dumps(parsed)
                    return
                except json.JSONDecodeError:
                    pass
            variables[variable] = var_value
        elif isinstance(var_value, (dict, list)):
            variables[variable] = json.dumps(var_value)
        else:
            variables[variable] = var_value

    # Top-level keys (convert string-type fields)
    assign('name', to_str_or_none(span.get('name')))
    assign('trace_id', to_str_or_none(span.get('context', {}).get('trace_id')))
    assign('span_id', to_str_or_none(span.get('context', {}).get('span_id')))
    assign('trace_state', to_str_or_none(span.get('context', {}).get('trace_state')))
    assign('parent_id', to_str_or_none(span.get('parent_id')))
    assign('start_time', to_str_or_none(span.get('start_time')))
    assign('cvn1', _to_timestamp(span.get('start_time')))
    assign('end_time', to_str_or_none(span.get('end_time')))
    assign('cvn2', _to_timestamp(span.get('end_time')))

    # Attributes section
    attributes = span.get('attributes', {})

    assign('llm_tools', to_str_or_none(attributes.get('llm', {}).get('tools')))
    assign('llm_token_count', to_str_or_none(attributes.get('llm', {}).get('token_count')))
    assign('llm_output_messages', to_str_or_none(
        attributes.get('llm', {}).get('output_messages', {}).get('output_messages')))
    assign('llm_input_messages', to_str_or_none(
        attributes.get('llm', {}).get('input_messages', {}).get('input_messages')))
    assign('llm_model_name', to_str_or_none(attributes.get('llm', {}).get('model_name')))
    assign('llm_invocation_parameters', to_str_or_none(attributes.get('llm', {}).get('invocation_parameters')))

    assign('input', to_str_or_none(attributes.get('input', {}).get('value')))
    assign('output', to_str_or_none(attributes.get('output', {}).get('value')))
    assign('tool', to_str_or_none(attributes.get('tool', {})))
    assign('kind', to_str_or_none(attributes.get('fi', {}).get('span', {}).get('kind')))
    assign('from_source', "openAI_Telemetry")

    response_id = (attributes.get('output') or {}).get('value', {}).get('id')
    assign('resp_id', to_str_or_none(response_id)) #for link with agentsAI records

    return reassign(variables)

def set_nested(obj, path, value):
    parts = path.split(".")
    current = obj
    for i, part in enumerate(parts[:-1]):
        try:
            idx = int(part)
            if not isinstance(current, list):
                current_parent = current
                current = []
                if isinstance(current_parent, dict):
                    current_parent[parts[i - 1]] = current
            while len(current) <= idx:
                current.append({})
            current = current[idx]
        except ValueError:
            if part not in current or not isinstance(current[part], (dict, list)):
                current[part] = {}
            current = current[part]
    final_key = parts[-1]
    try:
        final_key = int(final_key)
        if not isinstance(current, list):
            current_parent = current
            current = []
            if isinstance(current_parent, dict):
                current_parent[parts[-2]] = current
        while len(current) <= final_key:
            current.append(None)
    except ValueError:
        pass
    # Try JSON parsing
    if isinstance(value, str) and value.strip().startswith(("{", "[")):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
    if isinstance(final_key, int):
        current[final_key] = value
    else:
        current[final_key] = value

def deserialize_attributes(obj):
    flat_attrs = obj.get("attributes", {})
    new_attrs = {}
    for key, value in flat_attrs.items():
        set_nested(new_attrs, key, value)
    obj["attributes"] = new_attrs
    return obj

class CustomConsoleExporter(SpanExporter):
    def export(self, spans) -> SpanExportResult:
        for span in spans:
            span_json = json.loads(span.to_json(indent=2))
            deserialized = deserialize_attributes(span_json)
            data=extract_span_info(deserialized)
            try:
                response = requests.post(log_api_url, json=data, timeout=5)
                response.raise_for_status()  # Raises HTTPError for bad responses (e.g., 4xx/5xx)
            except Exception as e:
                print(f"[ANOSYS]❌ POST failed: {e}")
                print(f"[ANOSYS]❌ Data: {json.dumps(data, indent=2)}")
        return SpanExportResult.SUCCESS

def setup_tracing(api_url):
    global log_api_url
    log_api_url = api_url

    with _lock:
        # Setup provider + console exporter
        trace_provider = TracerProvider()
        trace_provider.add_span_processor(SimpleSpanProcessor(CustomConsoleExporter()))
        trace.set_tracer_provider(trace_provider)

        # Re-instrument OpenAI Instrumentor
        instrumentor = OpenAIInstrumentor()
        try:
            if instrumentor._is_instrumented_by_opentelemetry:
                instrumentor.uninstrument()
        except Exception as e:
            print(f"[ANOSYS]❌ Uninstrument error (safe to ignore if first call): {e}")
        instrumentor.instrument(tracer_provider=trace_provider)

        print("[ANOSYS] AnoSys Instrumented OpenAI agents with custom tracer")