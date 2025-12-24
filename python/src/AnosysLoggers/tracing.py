from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, Status, StatusCode
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor, 
    BatchSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from traceai_openai import OpenAIInstrumentor
import threading
import json
import os
from datetime import datetime
import requests

# Import shared utilities
from .utils import (
    key_to_cvs,
    reassign,
    to_str_or_none,
    assign,
    to_json_fallback,
)

# Prevent re-initialization
_lock = threading.Lock()
log_api_url = "https://www.anosys.ai"


def get_env_bool(var_name: str) -> bool:
    """
    Returns True if the environment variable doesn't exist,
    otherwise converts its value to a boolean.
    """
    value = os.getenv(var_name)

    if value is None:
        return True  # Default to True if variable not set

    # Normalize and convert string to boolean
    value_str = value.strip().lower()
    if value_str in ('1', 'true', 'yes', 'on'):
        return True
    elif value_str in ('0', 'false', 'no', 'off'):
        return False
    else:
        # If it's an unexpected string, still try bool() fallback
        return bool(value_str)


def _to_timestamp(dt_str):
    """Convert ISO datetime string to milliseconds timestamp."""
    if not dt_str:
        return None
    try:
        return int(datetime.fromisoformat(dt_str.replace('Z', '+00:00')).timestamp() * 1000)
    except (ValueError, AttributeError):
        return None


def extract_span_info(span):
    """
    Extract and transform span information into Anosys format.
    Includes OpenTelemetry semantic conventions for Gen AI.
    """
    variables = {}

    # Top-level metadata
    assign(variables, 'otel_record_type', 'AnoSys Trace')
    assign(variables, 'custom_mapping', json.dumps(key_to_cvs, indent=4))
    assign(variables, 'otel_observed_timestamp', datetime.utcnow().isoformat() + "Z")
    assign(variables, 'name', to_str_or_none(span.get('name')))
    assign(variables, 'trace_id', to_str_or_none(span.get('context', {}).get('trace_id')))
    assign(variables, 'span_id', to_str_or_none(span.get('context', {}).get('span_id')))
    assign(variables, 'trace_state', to_str_or_none(span.get('context', {}).get('trace_state')))
    assign(variables, 'parent_id', to_str_or_none(span.get('parent_id')))
    assign(variables, 'start_time', to_str_or_none(span.get('start_time')))
    assign(variables, 'cvn1', _to_timestamp(span.get('start_time')))
    assign(variables, 'end_time', to_str_or_none(span.get('end_time')))
    assign(variables, 'cvn2', _to_timestamp(span.get('end_time')))
    
    # Duration calculation
    start_ts = _to_timestamp(span.get('start_time'))
    end_ts = _to_timestamp(span.get('end_time'))
    if start_ts and end_ts:
        assign(variables, 'otel_duration_ms', end_ts - start_ts)

    # Status information
    status = span.get('status', {})
    if status:
        assign(variables, 'status', to_str_or_none(status))
        status_code = status.get('status_code')
        if status_code:
            # Map OpenTelemetry status codes to string
            status_map = {0: 'UNSET', 1: 'OK', 2: 'ERROR'}
            assign(variables, 'status_code', status_map.get(status_code, str(status_code)))

    # Attributes
    attributes = span.get('attributes', {})

    # OpenTelemetry Semantic Conventions for Gen AI
    # Reference: https://opentelemetry.io/docs/specs/semconv/gen-ai/
    
    # --- General & System ---
    # System is always "openai" for this instrumentor
    assign(variables, 'gen_ai.system', 'openai')
    # Provider name (e.g., openai, aws.bedrock)
    assign(variables, 'gen_ai.provider.name', 'openai')
    
    # Operation name from span name (e.g., "chat", "embeddings.create")
    span_name = span.get('name', '')
    if span_name:
        # Extract operation from span name (e.g., "chat.completions.create" -> "chat")
        operation = span_name.split('.')[0] if '.' in span_name else span_name
        assign(variables, 'gen_ai.operation.name', operation)
    
    # Server address from resource or default
    resource_attrs = span.get('resource', {}).get('attributes', {})
    server_addr = resource_attrs.get('server.address') or 'api.openai.com'
    server_port = resource_attrs.get('server.port') or 443
    assign(variables, 'server.address', server_addr)
    assign(variables, 'server.port', server_port)
    
    # Extract model information from invocation parameters or result
    llm_attrs = attributes.get('llm', {})
    invocation_params = llm_attrs.get('invocation_parameters', {})
    
    if isinstance(invocation_params, str):
        try:
            invocation_params = json.loads(invocation_params)
        except:
            invocation_params = {}
    
    # --- Request Configuration (LLM) ---
    model_name = llm_attrs.get('model_name')
    if model_name:
        assign(variables, 'gen_ai.request.model', to_str_or_none(model_name))
    
    if isinstance(invocation_params, dict):
        # Core parameters
        temperature = invocation_params.get('temperature')
        max_tokens = invocation_params.get('max_tokens')
        top_p = invocation_params.get('top_p')
        top_k = invocation_params.get('top_k')
        frequency_penalty = invocation_params.get('frequency_penalty')
        presence_penalty = invocation_params.get('presence_penalty')
        stop_sequences = invocation_params.get('stop')
        seed = invocation_params.get('seed')
        n = invocation_params.get('n')  # number of choices
        response_format = invocation_params.get('response_format')
        
        if temperature is not None:
            assign(variables, 'gen_ai.request.temperature', temperature)
        if max_tokens is not None:
            assign(variables, 'gen_ai.request.max_tokens', max_tokens)
        if top_p is not None:
            assign(variables, 'gen_ai.request.top_p', top_p)
        if top_k is not None:
            assign(variables, 'gen_ai.request.top_k', top_k)
        if frequency_penalty is not None:
            assign(variables, 'gen_ai.request.frequency_penalty', frequency_penalty)
        if presence_penalty is not None:
            assign(variables, 'gen_ai.request.presence_penalty', presence_penalty)
        if stop_sequences is not None:
            assign(variables, 'gen_ai.request.stop_sequences', stop_sequences)
        if seed is not None:
            assign(variables, 'gen_ai.request.seed', seed)
        if n is not None:
            assign(variables, 'gen_ai.request.choice.count', n)
    
    # --- Extract output information ---
    output_attr = attributes.get('output', {})
    response_model = None
    response_id = None
    finish_reasons = []
    output_type = None
    
    if isinstance(output_attr, dict):
        output_value = output_attr.get('value') or {}
        if isinstance(output_value, str):
            try:
                output_value = json.loads(output_value)
            except:
                pass
        
        if isinstance(output_value, dict):
            response_id = output_value.get('id')
            response_model = output_value.get('model')
            object_type = output_value.get('object')
            
            # Determine output type from response
            if object_type:
                if 'chat' in object_type:
                    output_type = 'text'
                elif 'embedding' in object_type:
                    output_type = 'embedding'
                elif 'image' in object_type:
                    output_type = 'image'
            
            # Check for JSON mode
            if invocation_params.get('response_format', {}).get('type') == 'json_object':
                output_type = 'json'
            
            # Extract finish reasons
            choices = output_value.get('choices', [])
            if isinstance(choices, list):
                for choice in choices:
                    if isinstance(choice, dict):
                        finish_reason = choice.get('finish_reason')
                        if finish_reason:
                            finish_reasons.append(finish_reason)
    
    # --- Response & Usage (LLM) ---
    if response_model:
        assign(variables, 'gen_ai.response.model', to_str_or_none(response_model))
    
    if response_id:
        assign(variables, 'gen_ai.response.id', to_str_or_none(response_id))
    
    if finish_reasons:
        assign(variables, 'gen_ai.response.finish_reasons', finish_reasons)
    
    if output_type:
        assign(variables, 'gen_ai.output.type', output_type)
    
    # Token usage (semantic conventions)
    token_count = llm_attrs.get('token_count', {})
    if isinstance(token_count, str):
        try:
            token_count = json.loads(token_count)
        except:
            token_count = {}
    
    if isinstance(token_count, dict):
        input_tokens = token_count.get('prompt_tokens') or token_count.get('input_tokens')
        output_tokens = token_count.get('completion_tokens') or token_count.get('output_tokens')
        total_tokens = token_count.get('total_tokens')
        
        if input_tokens is not None:
            assign(variables, 'gen_ai.usage.input_tokens', input_tokens)
        if output_tokens is not None:
            assign(variables, 'gen_ai.usage.output_tokens', output_tokens)
        if total_tokens is not None:
            assign(variables, 'gen_ai.usage.total_tokens', total_tokens)
        elif input_tokens is not None and output_tokens is not None:
            # Calculate total if not provided
            assign(variables, 'gen_ai.usage.total_tokens', input_tokens + output_tokens)
    
    # --- Content & Messages (Opt-In) ---
    # Extract input messages - try multiple sources
    input_messages = None
    
    # Try from input_messages attribute
    input_msg_attr = llm_attrs.get('input_messages', {})
    if isinstance(input_msg_attr, dict):
        input_messages = input_msg_attr.get('input_messages')
    
    # Try from invocation_parameters.messages
    if not input_messages and isinstance(invocation_params, dict):
        messages = invocation_params.get('messages')
        if messages:
            input_messages = messages
    
    if input_messages:
        assign(variables, 'gen_ai.input.messages', to_str_or_none(input_messages))
    
    # Extract output messages from choices
    output_messages = None
    output_msg_attr = llm_attrs.get('output_messages', {})
    if isinstance(output_msg_attr, dict):
        output_messages = output_msg_attr.get('output_messages')
    
    # Also try from output_value.choices
    if not output_messages and isinstance(output_value, dict):
        choices = output_value.get('choices', [])
        if choices:
            messages = [choice.get('message') for choice in choices if choice.get('message')]
            if messages:
                output_messages = messages
    
    if output_messages:
        assign(variables, 'gen_ai.output.messages', to_str_or_none(output_messages))
    
    # System instructions - extract from messages array
    system_content = llm_attrs.get('system')
    if not system_content and input_messages:
        # Try to find system message in input messages
        if isinstance(input_messages, list):
            for msg in input_messages:
                if isinstance(msg, dict) and msg.get('role') == 'system':
                    system_content = msg.get('content')
                    break
        elif isinstance(input_messages, str):
            try:
                parsed_messages = json.loads(input_messages)
                if isinstance(parsed_messages, list):
                    for msg in parsed_messages:
                        if isinstance(msg, dict) and msg.get('role') == 'system':
                            system_content = msg.get('content')
                            break
            except:
                pass
    
    if system_content:
        assign(variables, 'gen_ai.system_instructions', to_str_or_none(system_content))
    
    # Tool definitions (if available)
    tools = llm_attrs.get('tools')
    if not tools and isinstance(invocation_params, dict):
        tools = invocation_params.get('tools')
    
    if tools:
        assign(variables, 'gen_ai.tool.definitions', to_str_or_none(tools))
    
    # Legacy LLM fields (backward compatibility)
    assign(variables, 'llm_tools', to_str_or_none(llm_attrs.get('tools')))
    assign(variables, 'llm_token_count', to_str_or_none(llm_attrs.get('token_count')))
    assign(variables, 'llm_output_messages', to_str_or_none(
        llm_attrs.get('output_messages', {}).get('output_messages')))
    assign(variables, 'llm_input_messages', to_str_or_none(
        llm_attrs.get('input_messages', {}).get('input_messages')))
    assign(variables, 'llm_model', to_str_or_none(model_name))
    assign(variables, 'llm_invocation_parameters', to_str_or_none(invocation_params))
    assign(variables, 'llm_system', to_str_or_none(llm_attrs.get('system')))
    assign(variables, 'llm_input', to_str_or_none(attributes.get('input', {}).get('value')))
    # Safe extraction of llm_output
    llm_output_val = output_attr.get('value') if isinstance(output_attr, dict) else output_attr
    assign(variables, 'llm_output', to_str_or_none(llm_output_val))
    assign(variables, 'kind', to_str_or_none(attributes.get('fi', {}).get('span', {}).get('kind')))
    
    # Resource attributes
    # assign(variables, 'otel_resource', to_str_or_none(span.get('resource', {}).get('attributes')))
    assign(variables, 'otel_resource', json.dumps(span.get('resource', {}).get('attributes'), default=str))
    assign(variables, 'from_source', "openAI_Python_Telemetry")
    
    # Response ID for linking
    assign(variables, 'resp_id', to_str_or_none(response_id))
    
    # Check if streaming
    is_streaming = invocation_params.get('stream', False) if isinstance(invocation_params, dict) else False
    if is_streaming:
        assign(variables, 'is_streaming', True)
    
    # Debug raw data if enabled
    assign(variables, "raw", json.dumps(span, default=str))
    
    return reassign(variables)


def set_nested(obj, path, value):
    """Helper to set nested dictionary values from dotted paths."""
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
    """Deserialize flattened attributes into nested structure."""
    flat_attrs = obj.get("attributes", {})
    new_attrs = {}
    for key, value in flat_attrs.items():
        set_nested(new_attrs, key, value)
    obj["attributes"] = new_attrs
    return obj


class CustomConsoleExporter(SpanExporter):
    """Custom exporter to send spans to Anosys API."""
    
    def export(self, spans) -> SpanExportResult:
        """Export spans to Anosys API."""
        for span in spans:
            try:
                span_json = json.loads(span.to_json(indent=2))
                deserialized = deserialize_attributes(span_json)
                data = extract_span_info(deserialized)
                
                # Log source to help identify non-OpenAI spans
                span_source = data.get("cvs200") or "unknown_source"  # from_source maps to cvs200
                span_name = data.get("otel_name") or "unknown"
                print(f"[ANOSYS]📡 Exporting span from: {span_source} | Name: {span_name}")
                
                response = requests.post(log_api_url, json=data, timeout=5)
                response.raise_for_status()

            except Exception as e:
                print(f"[ANOSYS]❌ Export failed: {e}")
                try:
                    print(f"[ANOSYS]❌ Data: {json.dumps(data, indent=2)}")
                except Exception:
                    pass
        return SpanExportResult.SUCCESS


def setup_tracing(api_url, use_batch_processor=False):
    """
    Initialize tracing for OpenAI and ALL other OpenTelemetry sources.

    Args:
        api_url (str): URL to post telemetry data.
        use_batch_processor (bool): If True, use BatchSpanProcessor; otherwise, SimpleSpanProcessor.
    """
    global log_api_url
    log_api_url = api_url

    with _lock:
        # Global TracerProvider applies to all OTEL instrumented libraries
        trace_provider = TracerProvider()

        exporter = CustomConsoleExporter()
        if use_batch_processor:
            span_processor = BatchSpanProcessor(
                exporter,
                schedule_delay_millis=1000,
                max_queue_size=2048,
                max_export_batch_size=512
            )
            print("[ANOSYS] Using BatchSpanProcessor for spans")
        else:
            span_processor = SimpleSpanProcessor(exporter)
            print("[ANOSYS] Using SimpleSpanProcessor for spans")

        # Register the global provider
        trace_provider.add_span_processor(span_processor)
        trace.set_tracer_provider(trace_provider)

        # Instrument OpenAI
        instrumentor = OpenAIInstrumentor()
        try:
            if getattr(instrumentor, "_is_instrumented_by_opentelemetry", False):
                instrumentor.uninstrument()
        except Exception as e:
            print(f"[ANOSYS]⚠️ Uninstrument warning: {e}")

        instrumentor.instrument(tracer_provider=trace_provider)

        print("[ANOSYS]✅ AnoSys Instrumented OpenAI and all OpenTelemetry traces")

        # Optional: Print active tracer info to confirm global registration
        active_provider = trace.get_tracer_provider()
        print(f"[ANOSYS] Active global tracer provider: {active_provider.__class__.__name__}")
