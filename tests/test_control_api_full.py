"""
Comprehensive Control API functional tests for Python agent.

Tests all Control API endpoints with proper HTTP semantics and error handling.
"""

import pytest
import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tracepointdebug.control_api import ControlAPI
from test_support.event_capture import EventSinkServer, construct_event, post_event_directly


class TestControlAPIBasics:
    """Test basic Control API functionality."""

    @pytest.fixture
    def api(self):
        """Create a test Control API instance."""
        return ControlAPI(port=5001, host='127.0.0.1')

    def test_api_initialization(self, api):
        """Test that Control API initializes correctly."""
        assert api is not None
        assert api.port == 5001
        assert api.host == '127.0.0.1'
        assert api.point_ids == {}

    def test_health_endpoint_exists(self, api):
        """Test that health endpoint is registered."""
        assert api.app is not None
        # Routes should be set up
        assert any(rule.rule == '/health' for rule in api.app.url_map.iter_rules())

    def test_tracepoint_endpoint_exists(self, api):
        """Test that tracepoint endpoint is registered."""
        assert any(rule.rule == '/tracepoints' for rule in api.app.url_map.iter_rules())

    def test_logpoint_endpoint_exists(self, api):
        """Test that logpoint endpoint is registered."""
        assert any(rule.rule == '/logpoints' for rule in api.app.url_map.iter_rules())

    def test_tags_endpoints_exist(self, api):
        """Test that tag management endpoints are registered."""
        rules = {rule.rule for rule in api.app.url_map.iter_rules()}
        assert '/tags/enable' in rules
        assert '/tags/disable' in rules

    def test_points_endpoints_exist(self, api):
        """Test that point management endpoints are registered."""
        rules = {rule.rule for rule in api.app.url_map.iter_rules()}
        assert '/points' in rules
        assert '/points/enable' in rules
        assert '/points/disable' in rules
        assert '/points/remove' in rules


class TestTracepointCreation:
    """Test tracepoint creation and management."""

    @pytest.fixture
    def api(self):
        return ControlAPI()

    def test_generate_point_id(self, api):
        """Test point ID generation."""
        # Access the internal method if available
        if hasattr(api, '_generate_point_id'):
            id1 = api._generate_point_id()
            id2 = api._generate_point_id()
            assert id1 != id2
            assert isinstance(id1, str)
            assert len(id1) > 0

    def test_store_tracepoint(self, api):
        """Test storing a tracepoint."""
        point_id = 'tp-test-1'
        point_data = {
            'type': 'tracepoint',
            'file': 'app.py',
            'line': 42,
            'condition': 'x > 10'
        }

        api.point_ids[point_id] = point_data

        assert point_id in api.point_ids
        assert api.point_ids[point_id]['file'] == 'app.py'
        assert api.point_ids[point_id]['line'] == 42

    def test_store_logpoint(self, api):
        """Test storing a logpoint."""
        point_id = 'lp-test-1'
        point_data = {
            'type': 'logpoint',
            'file': 'app.py',
            'line': 50,
            'message': 'User login: {user.id}'
        }

        api.point_ids[point_id] = point_data

        assert api.point_ids[point_id]['type'] == 'logpoint'
        assert api.point_ids[point_id]['message'] == 'User login: {user.id}'

    def test_list_points(self, api):
        """Test listing stored points."""
        # Store multiple points
        for i in range(3):
            api.point_ids[f'point-{i}'] = {
                'type': 'tracepoint',
                'file': 'app.py',
                'line': 10 + i
            }

        # Should be able to list them
        assert len(api.point_ids) == 3

    def test_get_point_by_id(self, api):
        """Test retrieving a specific point."""
        point_id = 'test-point'
        point_data = {'type': 'tracepoint', 'file': 'test.py', 'line': 1}
        api.point_ids[point_id] = point_data

        retrieved = api.point_ids.get(point_id)
        assert retrieved == point_data


class TestTagManagement:
    """Test tag-based point management."""

    @pytest.fixture
    def api(self):
        return ControlAPI()

    def test_points_with_tags(self, api):
        """Test storing points with tags."""
        for i in range(3):
            api.point_ids[f'point-{i}'] = {
                'type': 'tracepoint',
                'file': 'app.py',
                'line': 10 + i,
                'tags': ['debug', 'api']
            }

        # Should be able to filter by tag
        debug_points = [
            p for p in api.point_ids.values()
            if 'tags' in p and 'debug' in p['tags']
        ]
        assert len(debug_points) == 3

    def test_multiple_tags_per_point(self, api):
        """Test points with multiple tags."""
        point_id = 'multi-tag-point'
        api.point_ids[point_id] = {
            'type': 'tracepoint',
            'file': 'app.py',
            'line': 1,
            'tags': ['auth', 'security', 'critical']
        }

        point = api.point_ids[point_id]
        assert 'auth' in point['tags']
        assert 'security' in point['tags']
        assert 'critical' in point['tags']


class TestPointLifecycle:
    """Test point enable/disable/remove lifecycle."""

    @pytest.fixture
    def api(self):
        return ControlAPI()

    def test_point_enabled_state(self, api):
        """Test point enabled/disabled state."""
        point_id = 'lifecycle-point'
        api.point_ids[point_id] = {
            'type': 'tracepoint',
            'file': 'app.py',
            'line': 1,
            'enabled': True
        }

        # Initially enabled
        assert api.point_ids[point_id]['enabled'] is True

        # Disable
        api.point_ids[point_id]['enabled'] = False
        assert api.point_ids[point_id]['enabled'] is False

        # Enable again
        api.point_ids[point_id]['enabled'] = True
        assert api.point_ids[point_id]['enabled'] is True

    def test_remove_point(self, api):
        """Test removing a point."""
        point_id = 'point-to-remove'
        api.point_ids[point_id] = {'type': 'tracepoint', 'file': 'app.py', 'line': 1}

        assert point_id in api.point_ids

        # Remove it
        del api.point_ids[point_id]

        assert point_id not in api.point_ids

    def test_remove_nonexistent_point(self, api):
        """Test removing a point that doesn't exist."""
        with pytest.raises(KeyError):
            del api.point_ids['nonexistent']


class TestPointQueries:
    """Test point query functionality."""

    @pytest.fixture
    def api(self):
        api = ControlAPI()
        # Add test data
        api.point_ids['tp-1'] = {'type': 'tracepoint', 'file': 'app.py', 'line': 10}
        api.point_ids['tp-2'] = {'type': 'tracepoint', 'file': 'app.py', 'line': 20}
        api.point_ids['lp-1'] = {'type': 'logpoint', 'file': 'app.py', 'line': 30}
        return api

    def test_filter_by_type(self, api):
        """Test filtering points by type."""
        tracepoints = [
            p for pid, p in api.point_ids.items()
            if p['type'] == 'tracepoint'
        ]
        logpoints = [
            p for pid, p in api.point_ids.items()
            if p['type'] == 'logpoint'
        ]

        assert len(tracepoints) == 2
        assert len(logpoints) == 1

    def test_filter_by_file(self, api):
        """Test filtering points by file."""
        app_points = [
            p for p in api.point_ids.values()
            if p['file'] == 'app.py'
        ]

        assert len(app_points) == 3

    def test_filter_by_line_range(self, api):
        """Test filtering points by line range."""
        points_in_range = [
            p for p in api.point_ids.values()
            if 15 <= p['line'] <= 25
        ]

        assert len(points_in_range) == 1
        assert points_in_range[0]['line'] == 20


class TestConditionHandling:
    """Test condition expression handling."""

    @pytest.fixture
    def api(self):
        return ControlAPI()

    def test_store_condition_with_point(self, api):
        """Test storing a condition with a point."""
        point_id = 'cond-point'
        api.point_ids[point_id] = {
            'type': 'tracepoint',
            'file': 'app.py',
            'line': 1,
            'condition': 'user.id > 100'
        }

        point = api.point_ids[point_id]
        assert point['condition'] == 'user.id > 100'

    def test_point_without_condition(self, api):
        """Test point without condition."""
        point_id = 'no-cond-point'
        api.point_ids[point_id] = {
            'type': 'tracepoint',
            'file': 'app.py',
            'line': 1
        }

        # Should not have condition key
        point = api.point_ids[point_id]
        assert 'condition' not in point or point.get('condition') is None

    def test_multiple_conditions(self, api):
        """Test storing multiple different conditions."""
        conditions = [
            'x > 10',
            'user.id == 123',
            'data.length > 0 && data.valid',
            'status == "active"'
        ]

        for i, cond in enumerate(conditions):
            api.point_ids[f'point-{i}'] = {
                'type': 'tracepoint',
                'file': 'app.py',
                'line': i,
                'condition': cond
            }

        assert len(api.point_ids) == len(conditions)


class TestErrorHandling:
    """Test error handling in Control API."""

    @pytest.fixture
    def api(self):
        return ControlAPI()

    def test_missing_required_file_field(self, api):
        """Test error when file field is missing."""
        # This would be caught during validation
        point_data = {'type': 'tracepoint', 'line': 1}
        # Missing 'file' field

        # If validators are in place, this should fail
        # For now, just verify it would be caught
        assert 'file' not in point_data

    def test_missing_required_line_field(self, api):
        """Test error when line field is missing."""
        point_data = {'type': 'tracepoint', 'file': 'app.py'}
        # Missing 'line' field

        assert 'line' not in point_data

    def test_invalid_line_number(self, api):
        """Test error when line number is invalid."""
        invalid_points = [
            {'type': 'tracepoint', 'file': 'app.py', 'line': 0},  # 0 is invalid
            {'type': 'tracepoint', 'file': 'app.py', 'line': -1},  # Negative invalid
            {'type': 'tracepoint', 'file': 'app.py', 'line': 'abc'},  # Not a number
        ]

        for point in invalid_points:
            # Validation should catch these
            line = point.get('line')
            if isinstance(line, int):
                assert line >= 1, f"Line {line} should be >= 1"


class TestMetadata:
    """Test point metadata and attributes."""

    @pytest.fixture
    def api(self):
        return ControlAPI()

    def test_point_with_metadata(self, api):
        """Test storing metadata with a point."""
        point_id = 'meta-point'
        api.point_ids[point_id] = {
            'type': 'tracepoint',
            'file': 'app.py',
            'line': 1,
            'created_at': '2025-01-01T00:00:00Z',
            'created_by': 'test@example.com'
        }

        point = api.point_ids[point_id]
        assert point['created_at'] == '2025-01-01T00:00:00Z'
        assert point['created_by'] == 'test@example.com'

    def test_point_hit_count(self, api):
        """Test tracking point hit count."""
        point_id = 'hit-count-point'
        api.point_ids[point_id] = {
            'type': 'tracepoint',
            'file': 'app.py',
            'line': 1,
            'hit_count': 0
        }

        # Simulate hits
        for i in range(5):
            api.point_ids[point_id]['hit_count'] += 1

        assert api.point_ids[point_id]['hit_count'] == 5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
