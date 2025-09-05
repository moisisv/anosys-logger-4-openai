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
    try:
        # Case 1: object supports model_dump_json (pydantic-like OpenAI response)
        if hasattr(resp, "model_dump_json"):
            return resp.model_dump_json(indent=2)
        # Case 2: object supports model_dump (dict)
        elif hasattr(resp, "model_dump"):
            return json.dumps(resp.model_dump(), indent=2)
        # Case 3: object is already a dict
        elif isinstance(resp, dict):
            return json.dumps(resp, indent=2)
        # Case 4: maybe already JSON string
        try:
            json.loads(resp)  # test if valid JSON
            return resp  # it’s already JSON
        except Exception:
            # fallback → treat as plain string
            return json.dumps({"output": str(resp)}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "output": str(resp)}, indent=2)

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
        cvs_vars[cvs_var] = str(value) if value is not None else None

    return cvs_vars


def to_str_or_none(val):
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return json.dumps(val)
    return str(val)


def assign(variables, variable, var_value):
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
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            variables = {}
            print(f"[ANOSYS Logger: {source}] Starting...")
            print(f"[ANOSYS Logger: {source}] Input args: {args}, kwargs: {kwargs}")

            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                text = func(*args, **kwargs)
                printed_output = sys.stdout.getvalue()
            finally:
                sys.stdout = old_stdout

            output = text if text else printed_output.strip()

            print(f"[ANOSYS Logger: {source}] Captured output: {output}")

            input_array = [to_str_or_none(arg) for arg in args]

            assign(variables, "source", to_str_or_none(source))
            assign(variables, "input", input_array)
            assign(variables, "output", to_json_fallback(output))

            try:
                response = requests.post(log_api_url, json=reassign(variables), timeout=5)
                response.raise_for_status()  # Raises HTTPError for bad responses (e.g., 4xx/5xx)
            except Exception as e:
                print(f"[ANOSYS] POST failed: {e}")
                print(f"[ANOSYS] Data: {json.dumps(variables, indent=2)}")

            return text

        return wrapper

    return decorator

def setup_decorator(api_url):
    global log_api_url
    log_api_url = api_url