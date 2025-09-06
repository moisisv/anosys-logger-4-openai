from functools import wraps
import io
import sys
import json
import requests

log_api_url="https://www.anosys.ai"

key_to_cvs = {
    "input": "cvs14",
    "output": "cvs15",
    "source": "cvs200"
}

def to_json_fallback(resp):
    """
    Converts a given response object to a JSON-formatted string.
    
    Handles multiple cases:
    1. Object has 'model_dump_json' method (e.g., Pydantic/OpenAI response).
    2. Object has 'model_dump' method.
    3. Object is already a dict.
    4. Object is a JSON string.
    5. Fallback: treat as a plain string.

    Returns a JSON string with indentation.
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

def reassign(data, starting_index=100):
    """
    Maps dictionary keys to unique 'cvs' variable names and returns a new dict.
    
    Parameters:
    - data: dict or JSON string to be mapped.
    - starting_index: starting number for generating new 'cvs' variable names.

    Updates the global key_to_cvs mapping for unknown keys.
    Returns a dictionary where keys are 'cvs' variables and values are strings.
    """
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
        cvs_vars[cvs_var] = str(value) if value is not None else None

    return cvs_vars

def to_str_or_none(val):
    """
    Converts a value to a string, or returns None if the value is None.
    
    If the value is a dict or list, converts it to a JSON string.
    """
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return json.dumps(val)
    return str(val)

def assign(variables, variable, var_value):
    """
    Assigns a value to a variable in a dictionary with proper handling of types.
    
    - If the value is None, sets it to None.
    - If the value is a string representing JSON, parses and re-serializes it.
    - If the value is a dict or list, serializes it to JSON string.
    - Otherwise, assigns the value as-is.
    """
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

def anosys_logger(source=None):
    """
    Decorator to log function input, output, and metadata to the Anosys API.
    
    Captures:
    - Function arguments
    - Printed output
    - Return value

    Sends data to the configured Anosys logging API.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            variables = {}
            print(f"[ANOSYS] Logger: {source}] Starting...")
            print(f"[ANOSYS] Logger: {source}] Input args: {args}, kwargs: {kwargs}")

            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                text = func(*args, **kwargs)
                printed_output = sys.stdout.getvalue()
            finally:
                sys.stdout = old_stdout

            output = text if text else printed_output.strip()

            print(f"[ANOSYS] Logger: {source}] Captured output: {output}")

            input_array = [to_str_or_none(arg) for arg in args]

            assign(variables, "source", to_str_or_none(source))
            assign(variables, "input", input_array)
            assign(variables, "output", to_json_fallback(output))

            try:
                response = requests.post(log_api_url, json=reassign(variables), timeout=5)
                response.raise_for_status()
            except Exception as e:
                print(f"[ANOSYS] POST failed: {e}")
                print(f"[ANOSYS] Data: {json.dumps(variables, indent=2)}")

            return text

        return wrapper

    return decorator

def anosys_raw_logger(data=None):
    """
    Logs raw data to the Anosys API without wrapping a function.

    Parameters:
    - data: dictionary of data to log (default empty dict)

    Maps keys to 'cvs' variables and sends them to the Anosys logging API.
    """
    if data is None:
        data = {}

    print("[ANOSYS] anosys_raw_logger")
    print("[ANOSYS] data:", json.dumps(data, indent=2))

    try:
        mapped_data = reassign(data)
        response = requests.post(log_api_url, json=mapped_data, timeout=5)
        response.raise_for_status()
        print(f"[ANOSYS] Logger: {data} Logged successfully, with mapping {json.dumps(key_to_cvs, indent=2)}.")
        return response
    except Exception as err:
        print(f"[ANOSYS] POST failed: {err}")
        print("[ANOSYS] Data:")
        print(json.dumps(data, indent=2))
        return None

def setup_decorator(path=None):
    """
    Sets up the logging decorator by configuring the Anosys API endpoint.

    Parameters:
    - path: optional API URL to override the default

    If no path is provided, attempts to resolve the API key from environment
    variable 'ANOSYS_API_KEY' and fetch the endpoint from the Anosys API.
    """
    global log_api_url

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
            print(f"[ERROR] Failed to resolve API key: {e}")
    else:
        print("[ERROR] ANOSYS_API_KEY not found. Please obtain your API key from "
              "https://console.anosys.ai/collect/integrationoptions")
