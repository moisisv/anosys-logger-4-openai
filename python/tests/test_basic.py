"""
Basic tests for AnosysLoggers package.
Tests utility functions, decorator, and raw logger.
"""
import pytest
import json
from unittest.mock import Mock, patch
from AnosysLoggers.utils import (
    _get_type_key,
    _get_prefix_and_index,
    reassign,
    to_json_fallback,
    to_str_or_none,
    assign,
    key_to_cvs,
)
from AnosysLoggers.decorator import anosys_logger, anosys_raw_logger


class TestUtils:
    """Test utility functions."""
    
    def test_get_type_key(self):
        """Test type detection."""
        assert _get_type_key(True) == "bool"
        assert _get_type_key(42) == "int"
        assert _get_type_key(3.14) == "float"
        assert _get_type_key("test") == "string"
        assert _get_type_key([1, 2]) == "string"
        assert _get_type_key({"a": 1}) == "string"
    
    def test_get_prefix_and_index(self):
        """Test prefix and index mapping."""
        assert _get_prefix_and_index("string") == ("cvs", "string")
        assert _get_prefix_and_index("int") == ("cvn", "number")
        assert _get_prefix_and_index("float") == ("cvn", "number")
        assert _get_prefix_and_index("bool") == ("cvb", "bool")
    
    def test_to_json_fallback(self):
        """Test JSON conversion."""
        # Dict conversion
        result = to_json_fallback({"key": "value"})
        assert json.loads(result) == {"key": "value"}
        
        # String that's already JSON
        result = to_json_fallback('{"key": "value"}')
        assert '"key"' in result
        
        # Object without model_dump
        result = to_json_fallback("plain string")
        assert "plain string" in result
    
    def test_to_str_or_none(self):
        """Test string conversion."""
        assert to_str_or_none(None) is None
        assert to_str_or_none("test") == "test"
        assert to_str_or_none(42) == "42"
        assert json.loads(to_str_or_none({"a": 1})) == {"a": 1}
        assert json.loads(to_str_or_none([1, 2])) == [1, 2]
    
    def test_assign(self):
        """Test variable assignment."""
        variables = {}
        
        # None value
        assign(variables, "null_var", None)
        assert variables["null_var"] is None
        
        # Integer
        assign(variables, "int_var", 42)
        assert variables["int_var"] == 42
        
        # Float
        assign(variables, "float_var", 3.14)
        assert variables["float_var"] == 3.14
        
        # Boolean
        assign(variables, "bool_var", True)
        assert variables["bool_var"] is True
        
        # Dict
        assign(variables, "dict_var", {"key": "value"})
        assert json.loads(variables["dict_var"]) == {"key": "value"}
        
        # List
        assign(variables, "list_var", [1, 2, 3])
        assert json.loads(variables["list_var"]) == [1, 2, 3]
    
    def test_reassign(self):
        """Test key reassignment to CVS variables."""
        data = {
            "test_string": "hello",
            "test_number": 42,
            "test_bool": True,
            "test_dict": {"nested": "value"}
        }
        
        result = reassign(data)
        
        # Check that keys were mapped
        assert "cvs100" in result or any(k.startswith("cvs") for k in result.keys())
        assert any(k.startswith("cvn") for k in result.keys())
        assert any(k.startswith("cvb") for k in result.keys())


class TestDecorator:
    """Test decorator functionality."""
    
    @patch('AnosysLoggers.decorator.requests.post')
    def test_sync_function_logging(self, mock_post):
        """Test logging of synchronous functions."""
        mock_post.return_value = Mock(status_code=200)
        
        @anosys_logger(source="test")
        def test_func(x, y):
            return x + y
        
        result = test_func(2, 3)
        
        assert result == 5
        assert mock_post.called
        
        # Verify payload structure
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert isinstance(payload, dict)
    
    @patch('AnosysLoggers.decorator.requests.post')
    @pytest.mark.asyncio
    async def test_async_function_logging(self, mock_post):
        """Test logging of asynchronous functions."""
        mock_post.return_value = Mock(status_code=200)
        
        @anosys_logger(source="test_async")
        async def test_async_func(x):
            return x * 2
        
        result = await test_async_func(5)
        
        assert result == 10
        assert mock_post.called
    
    @patch('AnosysLoggers.decorator.requests.post')
    def test_error_logging(self, mock_post):
        """Test logging when function raises an error."""
        mock_post.return_value = Mock(status_code=200)
        
        @anosys_logger(source="test_error")
        def error_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            error_func()
        
        # Should still log despite error
        assert mock_post.called
        
        # Check that error info was logged
        payload = mock_post.call_args[1]['json']
        # Error fields should be present
        assert any('error' in str(k).lower() for k in payload.keys())


class TestRawLogger:
    """Test raw logger functionality."""
    
    @patch('AnosysLoggers.decorator.requests.post')
    def test_raw_logger_success(self, mock_post):
        """Test raw logger with successful post."""
        mock_post.return_value = Mock(status_code=200)
        
        data = {"test_key": "test_value", "number": 42}
        response = anosys_raw_logger(data)
        
        assert response is not None
        assert mock_post.called
        
        payload = mock_post.call_args[1]['json']
        assert isinstance(payload, dict)
    
    @patch('AnosysLoggers.decorator.requests.post')
    def test_raw_logger_failure(self, mock_post):
        """Test raw logger with failed post."""
        mock_post.side_effect = Exception("Network error")
        
        data = {"test_key": "test_value"}
        response = anosys_raw_logger(data)
        
        assert response is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
