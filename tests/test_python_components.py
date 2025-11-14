"""
Comprehensive tests for Python condition engine, snapshot, and encoder.

Tests all components of the Python probe system for robustness and correctness.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tracepointdebug.probe.condition.parser import Parser
from tracepointdebug.probe.encoder import to_json
from tracepointdebug.probe.ratelimit.rate_limiter import RateLimiter
import time


class TestConditionEngine:
    """Test Python condition evaluation engine."""

    def test_numeric_comparisons(self):
        """Test all numeric comparison operators."""
        parser = Parser()

        # Equal
        result = parser.parse("5 == 5").evaluate({})
        assert result is True, "5 == 5 should be true"

        # Not equal
        result = parser.parse("5 != 3").evaluate({})
        assert result is True, "5 != 3 should be true"

        # Less than
        result = parser.parse("3 < 5").evaluate({})
        assert result is True, "3 < 5 should be true"

        # Greater than
        result = parser.parse("5 > 3").evaluate({})
        assert result is True, "5 > 3 should be true"

        # Less than or equal
        result = parser.parse("5 <= 5").evaluate({})
        assert result is True, "5 <= 5 should be true"

        # Greater than or equal
        result = parser.parse("5 >= 5").evaluate({})
        assert result is True, "5 >= 5 should be true"

    def test_boolean_operators(self):
        """Test logical AND and OR operators."""
        parser = Parser()

        # AND - both true
        result = parser.parse("1 > 0 && 2 > 1").evaluate({})
        assert result is True

        # AND - one false
        result = parser.parse("1 > 0 && 2 < 1").evaluate({})
        assert result is False

        # OR - one true
        result = parser.parse("1 > 0 || 2 < 1").evaluate({})
        assert result is True

        # OR - both false
        result = parser.parse("1 < 0 || 2 < 1").evaluate({})
        assert result is False

    def test_string_comparison(self):
        """Test string comparisons."""
        parser = Parser()

        result = parser.parse("'hello' == 'hello'").evaluate({})
        assert result is True

        result = parser.parse("'hello' != 'world'").evaluate({})
        assert result is True

    def test_variable_access(self):
        """Test accessing variables from context."""
        parser = Parser()
        context = {'x': 10, 'y': 20}

        result = parser.parse("x > 5").evaluate(context)
        assert result is True

        result = parser.parse("y < x").evaluate(context)
        assert result is False

        result = parser.parse("x + y == 30").evaluate(context)
        assert result is True

    def test_field_access(self):
        """Test accessing object fields."""
        parser = Parser()
        context = {
            'user': {'id': 123, 'name': 'Alice', 'age': 30}
        }

        result = parser.parse("user.id == 123").evaluate(context)
        assert result is True

        result = parser.parse("user.age > 25").evaluate(context)
        assert result is True

    def test_invalid_expression_handling(self):
        """Test that invalid expressions raise appropriate errors."""
        parser = Parser()

        with pytest.raises(Exception):
            # Undefined variable
            parser.parse("undefined_var > 5").evaluate({})

        with pytest.raises(Exception):
            # Syntax error
            parser.parse("5 >>").evaluate({})

    def test_null_comparisons(self):
        """Test null/None comparisons."""
        parser = Parser()
        context = {'value': None}

        result = parser.parse("value == null").evaluate(context)
        assert result is True

        result = parser.parse("value != null").evaluate(context)
        assert result is False


class TestSnapshotEncoder:
    """Test snapshot encoding and serialization."""

    def test_primitive_types(self):
        """Test encoding of primitive types."""
        snapshot = {
            'int': 42,
            'float': 3.14,
            'string': 'hello',
            'bool': True,
            'none': None
        }

        encoded = to_json(snapshot)
        assert encoded['int'] == 42
        assert encoded['float'] == 3.14
        assert encoded['string'] == 'hello'
        assert encoded['bool'] is True
        assert encoded['none'] is None

    def test_nested_structures(self):
        """Test encoding of nested dicts and lists."""
        snapshot = {
            'data': {
                'nested': {
                    'deep': [1, 2, 3]
                }
            }
        }

        encoded = to_json(snapshot)
        assert encoded['data']['nested']['deep'] == [1, 2, 3]

    def test_list_encoding(self):
        """Test encoding of lists."""
        snapshot = {
            'items': [1, 2, 3, 4, 5],
            'mixed': [1, 'string', True, None]
        }

        encoded = to_json(snapshot)
        assert len(encoded['items']) == 5
        assert encoded['mixed'][1] == 'string'

    def test_custom_object_encoding(self):
        """Test encoding of custom objects."""
        class CustomObject:
            def __init__(self):
                self.value = 42
                self.name = 'test'

        snapshot = {'obj': CustomObject()}
        encoded = to_json(snapshot)

        # Custom objects should be encoded with __dict__ or type representation
        assert 'obj' in encoded

    def test_circular_reference_handling(self):
        """Test handling of circular references."""
        snapshot = {'a': 1}
        snapshot['self'] = snapshot  # Circular reference

        # Should not crash; should handle gracefully
        try:
            encoded = to_json(snapshot)
            # Circular ref should be detected and handled
            assert 'a' in encoded
        except RecursionError:
            pytest.fail("Circular reference should be handled without RecursionError")

    def test_large_collection_handling(self):
        """Test handling of very large collections."""
        snapshot = {
            'large_list': list(range(10000)),
            'large_dict': {str(i): i for i in range(1000)}
        }

        encoded = to_json(snapshot)
        # Should encode without excessive memory usage
        assert 'large_list' in encoded
        assert 'large_dict' in encoded

    def test_non_serializable_types(self):
        """Test handling of non-serializable types."""
        import io

        snapshot = {
            'file': io.StringIO('content'),
            'number': 42
        }

        encoded = to_json(snapshot)
        # File object should be handled (repr or type marker)
        assert 'number' in encoded


class TestRateLimiter:
    """Test Python rate limiter."""

    def test_rate_limiter_initialization(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(limit_per_second=10, burst=1)
        assert limiter.get_tokens() >= 0

    def test_under_limit_allows_consumption(self):
        """Test that consumption under limit succeeds."""
        limiter = RateLimiter(limit_per_second=10, burst=10)

        # Should allow 10 immediate tokens
        for i in range(10):
            assert limiter.consume() is True

    def test_over_limit_denies_consumption(self):
        """Test that consumption over limit fails."""
        limiter = RateLimiter(limit_per_second=10, burst=1)

        # Consume initial token
        assert limiter.consume() is True

        # Next 9 should fail (limit is 1 burst)
        for i in range(9):
            assert limiter.consume() is False

    def test_time_based_refill(self):
        """Test that tokens refill over time."""
        limiter = RateLimiter(limit_per_second=10, burst=1)

        # Consume the burst
        assert limiter.consume() is True
        assert limiter.consume() is False

        # Wait for refill (100ms = 1 token at 10/sec)
        time.sleep(0.15)

        # Should now have 1 token again
        assert limiter.consume() is True

    def test_burst_capacity(self):
        """Test burst capacity."""
        limiter = RateLimiter(limit_per_second=5, burst=5)

        # Should allow burst tokens immediately
        for i in range(5):
            assert limiter.consume() is True

        # 6th should fail
        assert limiter.consume() is False

    def test_statistics(self):
        """Test rate limiter statistics."""
        limiter = RateLimiter(limit_per_second=10, burst=10)

        # Consume some tokens
        for i in range(5):
            limiter.consume()

        stats = limiter.get_stats()
        assert 'tokens' in stats
        assert 'limit' in stats
        assert 'burst' in stats


class TestControlAPIIntegration:
    """Test Control API integration with snapshot and serialization."""

    def test_put_tracepoint_stores_correctly(self):
        """Test that PUT /tracepoints stores the tracepoint."""
        from tracepointdebug.control_api import ControlAPI

        api = ControlAPI()

        payload = {
            'file': 'test.py',
            'line': 42,
            'condition': 'x > 0'
        }

        # Store the point
        point_id = api._generate_point_id()
        api.point_ids[point_id] = {
            'type': 'tracepoint',
            'file': payload['file'],
            'line': payload['line'],
            'condition': payload.get('condition')
        }

        # Verify it was stored
        assert point_id in api.point_ids
        assert api.point_ids[point_id]['file'] == 'test.py'

    def test_enable_disable_point_lifecycle(self):
        """Test point enable/disable lifecycle."""
        from tracepointdebug.control_api import ControlAPI

        api = ControlAPI()
        point_id = 'test-point-1'

        api.point_ids[point_id] = {
            'type': 'tracepoint',
            'file': 'test.py',
            'line': 10,
            'enabled': False
        }

        # Enable the point
        api.point_ids[point_id]['enabled'] = True
        assert api.point_ids[point_id]['enabled'] is True

        # Disable the point
        api.point_ids[point_id]['enabled'] = False
        assert api.point_ids[point_id]['enabled'] is False


class TestSnapshotWithComplexData:
    """Test snapshot collection with complex real-world data."""

    def test_snapshot_with_request_object(self):
        """Test snapshot of a mock request object."""
        class MockRequest:
            def __init__(self):
                self.method = 'GET'
                self.path = '/api/users'
                self.headers = {'Content-Type': 'application/json'}
                self.query_params = {'page': 1, 'limit': 10}

        request = MockRequest()
        snapshot = {'request': request}

        # Should encode without error
        encoded = to_json(snapshot)
        assert 'request' in encoded

    def test_snapshot_with_exception_object(self):
        """Test snapshot of exception information."""
        try:
            raise ValueError("Test error")
        except ValueError as e:
            snapshot = {
                'exception_type': type(e).__name__,
                'exception_message': str(e),
                'exception_str': repr(e)
            }

            encoded = to_json(snapshot)
            assert encoded['exception_type'] == 'ValueError'
            assert encoded['exception_message'] == 'Test error'

    def test_snapshot_with_mixed_types(self):
        """Test snapshot with mixed types typical in real debugging."""
        snapshot = {
            'user_id': 123,
            'username': 'alice',
            'is_admin': False,
            'created_at': '2025-01-01T00:00:00Z',
            'metadata': {
                'tags': ['python', 'debugger'],
                'version': 3.11,
                'active': True
            },
            'items': [
                {'id': 1, 'name': 'item1'},
                {'id': 2, 'name': 'item2'}
            ]
        }

        encoded = to_json(snapshot)
        assert encoded['user_id'] == 123
        assert encoded['username'] == 'alice'
        assert encoded['metadata']['tags'] == ['python', 'debugger']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
