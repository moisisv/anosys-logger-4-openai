
import sys
import os
import json
from unittest.mock import MagicMock

# Add the src directory to the path so we can import AnosysLoggers
sys.path.append(os.path.join(os.path.dirname(__file__), 'AnosysLoggers'))

# Mock dependencies that might be hard to import or setup
sys.modules['opentelemetry'] = MagicMock()
sys.modules['opentelemetry.trace'] = MagicMock()
sys.modules['opentelemetry.sdk.trace'] = MagicMock()
sys.modules['opentelemetry.sdk.trace.export'] = MagicMock()
sys.modules['traceai_openai'] = MagicMock()
sys.modules['requests'] = MagicMock()

# Now import the function to test
# We need to make sure we can import from AnosysLoggers
# The structure is python/src/AnosysLoggers
# So if we are in python/src, we can import AnosysLoggers
try:
    from AnosysLoggers.tracing import extract_span_info
except ImportError:
    # Try adding the current directory to path
    sys.path.append(os.getcwd())
    from AnosysLoggers.tracing import extract_span_info

def test_crash_with_list_output():
    print("Testing crash with output_attr as a list...")
    
    # Mock a span with output attribute as a list
    span = {
        'name': 'test_span',
        'context': {'trace_id': '123', 'span_id': '456'},
        'attributes': {
            'output': [{'some': 'value'}], # This is a list!
            'llm': {'model_name': 'gpt-4'}
        }
    }
    
    try:
        result = extract_span_info(span)
        print("Success! No crash.")
    except Exception as e:
        print(f"Crashed as expected: {e}")
        import traceback
        traceback.print_exc()

def test_crash_with_string_value_in_dict():
    print("\nTesting crash with output_attr['value'] as a string...")
    
    # Mock a span with output attribute as a dict, but value is a string
    span = {
        'name': 'test_span',
        'context': {'trace_id': '123', 'span_id': '456'},
        'attributes': {
            'output': {'value': 'some string value'}, 
            'llm': {'model_name': 'gpt-4'}
        }
    }
    
    try:
        result = extract_span_info(span)
        print("Success! No crash.")
    except Exception as e:
        print(f"Crashed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_crash_with_list_output()
    test_crash_with_string_value_in_dict()
