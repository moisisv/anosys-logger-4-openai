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
    "cvn1": "cvn1",
    "cvn2": "cvn2",
    "otel_resource": "otel_resource",
    "name": "otel_name",
    "trace_id": "otel_trace_id",
    "span_id": "otel_span_id",
    "trace_state": "otel_trace_flags",
    "parent_id": "otel_parent_span_id",
    "start_time": "otel_start_time",
    "end_time": "otel_end_time",
    "kind": "otel_kind",
    "resp_id": "otel_status_message",
    "status": "otel_status",
    "status_code": "otel_status_code",
    
    # --- General & System ---
    "gen_ai.system": "gen_ai_system",
    "gen_ai.provider.name": "gen_ai_provider_name",
    "gen_ai.operation.name": "gen_ai_operation_name",
    "server.address": "server_address",
    "server.port": "server_port",
    "error.type": "error_type",
    
    # --- Request Configuration (LLM) ---
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
    
    # --- Response & Usage (LLM) ---
    "gen_ai.response.model": "gen_ai_response_model",
    "gen_ai.response.id": "gen_ai_response_id",
    "gen_ai.response.finish_reasons": "gen_ai_response_finish_reasons",
    "gen_ai.usage.input_tokens": "gen_ai_usage_input_tokens",
    "gen_ai.usage.output_tokens": "gen_ai_usage_output_tokens",
    "gen_ai.usage.total_tokens": "gen_ai_usage_total_tokens",
    "gen_ai.output.type": "gen_ai_output_type",
    
    # --- Content & Messages (Opt-In) ---
    "gen_ai.input.messages": "gen_ai_input_messages",
    "gen_ai.output.messages": "gen_ai_output_messages",
    "gen_ai.system_instructions": "gen_ai_system_instructions",
    "gen_ai.tool.definitions": "gen_ai_tool_definitions",
    
    # --- Agents & Frameworks ---
    "gen_ai.agent.id": "gen_ai_agent_id",
    "gen_ai.agent.name": "gen_ai_agent_name",
    "gen_ai.agent.description": "gen_ai_agent_description",
    "gen_ai.conversation.id": "gen_ai_conversation_id",
    "gen_ai.data_source.id": "gen_ai_data_source_id",
    
    # --- Embeddings Specific ---
    "gen_ai.embeddings.dimension.count": "gen_ai_embeddings_dimension_count",
    
    # Legacy LLM fields (backward compatibility)
    "llm_tools": "llm_tools",
    "llm_system": "llm_system",
    "llm_input": "llm_input",
    "llm_output": "llm_output",
    "llm_model": "llm_model",
    "llm_invocation_parameters": "llm_invocation_parameters",
    "llm_token_count": "llm_token_count",
    "llm_input_messages": "cvs1",
    "llm_output_messages": "cvs2",
    "otel_duration_ms": "otel_duration_ms",
    
    # Decorator-specific fields
    "input": "cvs1",
    "output": "cvs2",
    "caller": "cvs4",
    "error": "cvs3",
    "cvs10": "cvs10",  # error_type - keeping for backward compatibility
    "error_message": "cvs11",
    "error_stack": "cvs12",
    
    # Source tracking
    "raw": "cvs199",
    "from_source": "cvs200",
    "is_streaming": "cvb2",
}


def _get_type_key(value: Any) -> str:
    """Map Python types to category keys."""
    if isinstance(value, bool):
        return "bool"
    elif isinstance(value, int) and not isinstance(value, bool):
        return "int"
    elif isinstance(value, float):
        return "float"
    elif isinstance(value, str):
        return "string"
    else:
        return "string"


def _get_prefix_and_index(value_type: str) -> tuple:
    """Return the appropriate prefix and index counter name for a type."""
    if value_type == "string":
        return "cvs", "string"
    elif value_type in ("int", "float"):
        return "cvn", "number"
    elif value_type == "bool":
        return "cvb", "bool"
    else:
        return "cvs", "string"


def reassign(data: Union[Dict, str], starting_index: Optional[Dict] = None) -> Dict:
    """
    Maps dictionary keys to unique 'cvs' variable names and returns a new dict.
    Lists and dicts are STRINGIFIED before sending.
    
    Args:
        data: Dictionary or JSON string to map
        starting_index: Optional custom starting indices per type
        
    Returns:
        Dictionary with keys mapped to CVS variables
    """
    global key_to_cvs, global_starting_indices
    cvs_vars = {}

    if isinstance(data, str):
        data = json.loads(data)

    if not isinstance(data, dict):
        raise ValueError("Input must be a dict or JSON string representing a dict")

    indices = starting_index if starting_index is not None else global_starting_indices.copy()

    for key, value in data.items():
        if value is None:
            continue
            
        value_type = _get_type_key(value)
        prefix, index_key = _get_prefix_and_index(value_type)

        if key not in key_to_cvs:
            key_to_cvs[key] = f"{prefix}{indices[index_key]}"
            indices[index_key] += 1

        cvs_var = key_to_cvs[key]

        # Stringify lists/dicts to ensure they are JSON strings in body
        if isinstance(value, (dict, list)):
            cvs_vars[cvs_var] = json.dumps(value)
        elif isinstance(value, (bool, int, float)):
            cvs_vars[cvs_var] = value
        else:
            cvs_vars[cvs_var] = str(value)

    # Update global indices
    if starting_index is None:
        global_starting_indices.update(indices)

    return cvs_vars


def to_json_fallback(resp: Any) -> str:
    """
    Safely converts object/response into JSON string.
    
    Args:
        resp: Any object to convert to JSON
        
    Returns:
        JSON string representation
    """
    try:
        if hasattr(resp, "model_dump_json"):
            return resp.model_dump_json(indent=2)
        elif hasattr(resp, "model_dump"):
            return json.dumps(resp.model_dump(), indent=2)
        elif isinstance(resp, dict):
            return json.dumps(resp, indent=2)
        try:
            json.loads(resp)
            return resp
        except Exception:
            return json.dumps({"output": str(resp)}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "output": str(resp)}, indent=2)


def to_str_or_none(val: Any) -> Optional[str]:
    """
    Convert value into string or JSON string if list/dict.
    
    Args:
        val: Value to convert
        
    Returns:
        String representation or None
    """
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return json.dumps(val)
    return str(val)


def assign(variables: Dict, variable: str, var_value: Any) -> None:
    """
    Safely assign variable values with JSON handling.
    
    Args:
        variables: Dictionary to assign to
        variable: Key name
        var_value: Value to assign
    """
    if var_value is None:
        variables[variable] = None
        return

    # If the value is already an int or float
    if isinstance(var_value, (int, float)) and not isinstance(var_value, bool):
        variables[variable] = var_value
        return

    # If the value is a boolean
    if isinstance(var_value, bool):
        variables[variable] = var_value
        return

    # If the value is a dict or list, store as JSON
    if isinstance(var_value, (dict, list)):
        variables[variable] = json.dumps(var_value)
        return

    # If it's a string, handle possible JSON or numeric content
    if isinstance(var_value, str):
        var_value = var_value.strip()

        # Try to parse as JSON if it looks like JSON
        if var_value.startswith(('{', '[')):
            try:
                parsed = json.loads(var_value)
                variables[variable] = json.dumps(parsed)
                return
            except json.JSONDecodeError:
                pass

        # Try to interpret numeric strings (integers or floats)
        try:
            if '.' in var_value:
                variables[variable] = float(var_value)
            else:
                variables[variable] = int(var_value)
            return
        except ValueError:
            pass

        # Default: store as plain string
        variables[variable] = var_value
        return

    # Fallback: store raw value
    variables[variable] = var_value
