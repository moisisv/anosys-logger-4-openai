from functools import wraps
import os
import inspect
import sys
import json
import requests
import traceback
import asyncio

# Import shared utilities
from .utils import (
    key_to_cvs,
    reassign,
    to_str_or_none,
    assign,
    to_json_fallback,
)

# --- Global config ---
log_api_url = "https://www.anosys.ai"


def anosys_logger(source=None):
    """
    Decorator to log function input/output to Anosys API.
    Supports both sync and async functions.
    Includes caller information and error handling.
    
    Args:
        source: Source identifier for the logged function
        
    Returns:
        Decorated function
    """
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
            
            print(f"[ANOSYS] Logger (source={source}) "
                  f"called from {caller_info['function']} "
                  f"at {caller_info['file']}:{caller_info['line']}")
            
            # Capture result
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
                print(f"[ANOSYS] Error in {func.__name__}: {error_info['type']}: {error_info['message']}")
                raise
            finally:
                # Prepare payload
                input_array = [to_str_or_none(arg) for arg in args]
                if kwargs:
                    input_array.append({"kwargs": kwargs})
                
                assign(variables, "source", to_str_or_none(source))
                assign(variables, 'custom_mapping', json.dumps(key_to_cvs, indent=4))
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
                try:
                    response = requests.post(log_api_url, json=reassign(variables), timeout=5)
                    response.raise_for_status()
                    print(f"[ANOSYS] Logged successfully")
                except Exception as e:
                    print(f"[ANOSYS]❌ POST failed: {e}")
                    print(f"[ANOSYS]❌ Data: {json.dumps(variables, indent=2)}")
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
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
            
            print(f"[ANOSYS] Logger (source={source}) "
                  f"called from {caller_info['function']} "
                  f"at {caller_info['file']}:{caller_info['line']}")
            
            # Capture result
            error_occurred = False
            result = None
            error_info = None
            
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                error_occurred = True
                error_info = {
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": traceback.format_exc()
                }
                print(f"[ANOSYS] Error in {func.__name__}: {error_info['type']}: {error_info['message']}")
                raise
            finally:
                # Prepare payload
                input_array = [to_str_or_none(arg) for arg in args]
                if kwargs:
                    input_array.append({"kwargs": kwargs})
                
                assign(variables, "source", to_str_or_none(source))
                assign(variables, 'custom_mapping', json.dumps(key_to_cvs, indent=4))
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
                try:
                    response = requests.post(log_api_url, json=reassign(variables), timeout=5)
                    response.raise_for_status()
                    print(f"[ANOSYS] Logged successfully")
                except Exception as e:
                    print(f"[ANOSYS]❌ POST failed: {e}")
                    print(f"[ANOSYS]❌ Data: {json.dumps(variables, indent=2)}")
            
            return result
        
        return async_wrapper if is_async else sync_wrapper
    return decorator


def anosys_raw_logger(data=None):
    """
    Directly logs raw data dict/json to Anosys API.
    Dicts/lists are stringified.
    
    Args:
        data: Dictionary or None to log
        
    Returns:
        Response object or None on error
    """
    global key_to_cvs
    if data is None:
        data = {}
    try:
        mapped_data = reassign(data)
        response = requests.post(log_api_url, json=mapped_data, timeout=5)
        response.raise_for_status()
        print(f"[ANOSYS] Raw logger: Data logged successfully")
        return response
    except Exception as err:
        print(f"[ANOSYS]❌ POST failed: {err}")
        print(f"[ANOSYS]❌ Data: {json.dumps(data, indent=2)}")
        return None


def setup_decorator(path=None, starting_indices=None):
    """
    Setup logging decorator:
    - path: override Anosys API URL
    - starting_indices: dict of starting indices per type (not recommended)
    
    Args:
        path: Custom API endpoint URL
        starting_indices: Custom starting indices (deprecated)
    """
    global log_api_url
    from .utils import global_starting_indices
    
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
