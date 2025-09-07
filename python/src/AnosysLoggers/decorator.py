from functools import wraps
import os
import inspect
import sys, io, json, requests

# --- Global config ---
log_api_url = "https://www.anosys.ai"

# Separate index tracking for each type
global_starting_indices = {
    "string": 100,
    "number": 3,
    "bool": 1
}

# Known key mappings
key_to_cvs = {
    "input": "cvs14",
    "output": "cvs15",
    "source": "cvs200"
}

# --- Utility functions ---

def to_json_fallback(resp):
    """Safely converts object/response into JSON string."""
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


def _get_prefix_and_index(value_type: str):
    """Return the appropriate prefix and index counter name for a type."""
    if value_type == "string":
        return "cvs", "string"
    elif value_type in ("int", "float"):
        return "cvn", "number"
    elif value_type == "bool":
        return "cvb", "bool"
    else:
        return "cvs", "string"


def _get_type_key(value):
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


def reassign(data, starting_index=None):
    """
    Maps dictionary keys to unique 'cvs' variable names and returns a new dict.
    Lists and dicts are STRINGIFIED before sending.
    """
    global key_to_cvs, global_starting_indices
    cvs_vars = {}

    if isinstance(data, str):
        data = json.loads(data)

    if not isinstance(data, dict):
        raise ValueError("Input must be a dict or JSON string representing a dict")

    indices = starting_index if starting_index is not None else global_starting_indices.copy()

    for key, value in data.items():
        value_type = _get_type_key(value)
        prefix, index_key = _get_prefix_and_index(value_type)

        if key not in key_to_cvs:
            key_to_cvs[key] = f"{prefix}{indices[index_key]}"
            indices[index_key] += 1

        cvs_var = key_to_cvs[key]

        # ✅ Stringify lists/dicts to ensure they are JSON strings in body
        if isinstance(value, (dict, list)):
            cvs_vars[cvs_var] = json.dumps(value)
        elif isinstance(value, (bool, int, float)) or value is None:
            cvs_vars[cvs_var] = value
        else:
            cvs_vars[cvs_var] = str(value)

    return cvs_vars


def to_str_or_none(val):
    """Convert value into string or JSON string if list/dict."""
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return json.dumps(val)
    return str(val)


def assign(variables, variable, var_value):
    """Safely assign variable values with JSON handling."""
    if var_value is None:
        variables[variable] = None
    elif isinstance(var_value, str):
        var_value = var_value.strip()
        if var_value.startswith("{") or var_value.startswith("["):
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


# --- Decorator and raw logger ---
def anosys_logger(source=None):
    """Decorator to log function input/output to Anosys API,
       including who called the function.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            global key_to_cvs

            variables = {}

            # === detect caller ===
            stack = inspect.stack()
            caller = stack[1]  # the function that called this one
            caller_name = caller.function
            caller_line = caller.lineno
            caller_file = caller.filename

            print(f"[ANOSYS] Logger (source={source}) "
                  f"called from {caller_name} at {caller_file}:{caller_line}")

            # === capture printed output and return value ===
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                text = func(*args, **kwargs)
                printed_output = sys.stdout.getvalue()
            finally:
                sys.stdout = old_stdout

            output = text if text else printed_output.strip()
            print(f"[ANOSYS] Captured output: {output}")
            print(f"[ANOSYS] Captured caller: {caller}")

            # === prepare payload ===
            input_array = [to_str_or_none(arg) for arg in args]
            assign(variables, "source", to_str_or_none(source))
            assign(variables, "input", input_array)
            assign(variables, "output", to_json_fallback(output))
            assign(variables, "caller", {
                "function": caller_name,
                "file": caller_file,
                "line": caller_line,
            })

            # === send log ===
            try:
                response = requests.post(log_api_url, json=reassign(variables), timeout=5)
                response.raise_for_status()
                print(f"[ANOSYS] Mapper: {key_to_cvs}")
            except Exception as e:
                print(f"[ANOSYS]❌ POST failed: {e}")
                print(f"[ANOSYS]❌ Data: {json.dumps(variables, indent=2)}")

            return text
        return wrapper
    return decorator


def anosys_raw_logger(data=None):
    """Directly logs raw data dict/json to Anosys API (dicts/lists are stringified)."""
    global key_to_cvs
    if data is None:
        data = {}
    try:
        mapped_data = reassign(data)
        response = requests.post(log_api_url, json=mapped_data, timeout=5)
        response.raise_for_status()
        print(f"[ANOSYS] Logger: {data} Logged successfully, with mapping {json.dumps(key_to_cvs, indent=2)}.")
        return response
    except Exception as err:
        print(f"[ANOSYS]❌ POST failed: {err}")
        print("[ANOSYS]❌ Data:")
        print(json.dumps(mapped_data, indent=2))
        return None


def setup_decorator(path=None, starting_indices=None):
    """
    Setup logging decorator:
    - path: override Anosys API URL
    - starting_indices: dict of starting indices per type
    """
    global log_api_url, global_starting_indices

    if starting_indices:
        global_starting_indices.update(starting_indices)

    if path:
        log_api_url = path
        return

    api_key = os.getenv("ANOSYS_API_KEY")
    if api_key:
        try:
            response = requests.get(
                f"https://api.anosys.ai/api/resolveapikeys?apikey={api_key}",
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            log_api_url = data.get("url", "https://www.anosys.ai")
        except requests.RequestException as e:
            print(f"[ERROR]❌ Failed to resolve API key: {e}")
    else:
        print("[ERROR]‼️ ANOSYS_API_KEY not found. Please obtain your API key from "
              "https://console.anosys.ai/collect/integrationoptions")
