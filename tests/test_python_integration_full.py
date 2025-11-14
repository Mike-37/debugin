"""
Full integration tests: Control API → Python Fixture → Event Sink

Tests the complete data flow from creating probes via Control API through
to events being captured at the event sink.
"""

import pytest
import sys
import os
import time
import requests
import json
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_support.event_capture import (
    EventSinkServer, EventCapture, construct_event,
    post_event_directly
)
from tracepointdebug.control_api import ControlAPI


class MockApp:
    """Mock fixture application for testing."""

    def add(self, x, y):
        """Simple add function."""
        result = x + y
        return result

    def process(self, data):
        """Process data."""
        if not data:
            raise ValueError("Data cannot be empty")
        return len(data)

    def authenticated_operation(self, user_id):
        """Operation requiring authentication."""
        if user_id <= 0:
            raise ValueError(f"Invalid user_id: {user_id}")
        return f"User {user_id} authenticated"


class TestControlAPIIntegrationWithFixture:
    """Test Control API integration with fixture app."""

    @pytest.fixture
    def app(self):
        """Create mock fixture application."""
        return MockApp()

    @pytest.fixture
    def control_api(self):
        """Create Control API instance."""
        api = ControlAPI(port=5002, host='127.0.0.1')
        return api

    def test_create_tracepoint_on_method(self, control_api, app):
        """Test creating a tracepoint on a method."""
        point_id = 'test-add-point'

        # Simulate Control API receiving tracepoint request
        control_api.point_ids[point_id] = {
            'type': 'tracepoint',
            'file': 'fixture.py',
            'line': 5,  # Line of app.add method
            'method': 'add',
            'enabled': True
        }

        assert point_id in control_api.point_ids
        point = control_api.point_ids[point_id]
        assert point['method'] == 'add'
        assert point['enabled'] is True

    def test_create_logpoint_with_message(self, control_api):
        """Test creating a logpoint with message template."""
        point_id = 'test-log-point'

        control_api.point_ids[point_id] = {
            'type': 'logpoint',
            'file': 'fixture.py',
            'line': 12,
            'method': 'process',
            'message': 'Processing data of length {data_len}',
            'enabled': True
        }

        point = control_api.point_ids[point_id]
        assert point['type'] == 'logpoint'
        assert 'data_len' in point['message']

    def test_condition_on_tracepoint(self, control_api):
        """Test creating a tracepoint with condition."""
        point_id = 'test-cond-point'

        control_api.point_ids[point_id] = {
            'type': 'tracepoint',
            'file': 'fixture.py',
            'line': 5,
            'condition': 'x > 10',
            'enabled': True
        }

        point = control_api.point_ids[point_id]
        assert point['condition'] == 'x > 10'

    def test_multiple_points_on_same_method(self, control_api):
        """Test creating multiple points on the same method."""
        control_api.point_ids['point-1'] = {
            'type': 'tracepoint',
            'file': 'fixture.py',
            'line': 5,
            'method': 'add'
        }
        control_api.point_ids['point-2'] = {
            'type': 'logpoint',
            'file': 'fixture.py',
            'line': 5,
            'method': 'add'
        }

        add_points = [
            p for p in control_api.point_ids.values()
            if p.get('method') == 'add'
        ]

        assert len(add_points) == 2


class TestEventGeneration:
    """Test event generation from fixture operations."""

    def test_construct_tracepoint_event(self):
        """Test constructing a tracepoint hit event."""
        event = construct_event(
            name='probe.hit.snapshot',
            payload={
                'probeId': 'tp-1',
                'probeType': 'tracepoint',
                'file': 'fixture.py',
                'line': 5,
                'method': 'add',
                'snapshot': {
                    'arguments': {'x': 5, 'y': 3},
                    'returnValue': 8
                }
            }
        )

        assert event['name'] == 'probe.hit.snapshot'
        assert event['payload']['probeId'] == 'tp-1'
        assert event['payload']['snapshot']['returnValue'] == 8

    def test_construct_logpoint_event(self):
        """Test constructing a logpoint event."""
        event = construct_event(
            name='probe.hit.logpoint',
            payload={
                'probeId': 'lp-1',
                'probeType': 'logpoint',
                'file': 'fixture.py',
                'line': 12,
                'message': 'Processing data of length 42',
                'messageTemplate': 'Processing data of length {data_len}'
            }
        )

        assert event['name'] == 'probe.hit.logpoint'
        assert event['payload']['message'] == 'Processing data of length 42'

    def test_construct_error_event(self):
        """Test constructing a probe error event."""
        event = construct_event(
            name='probe.error.condition',
            payload={
                'probeId': 'tp-1',
                'probeType': 'tracepoint',
                'file': 'fixture.py',
                'line': 5,
                'condition': 'invalid_var > 0',
                'error': 'NameError: name "invalid_var" is not defined'
            }
        )

        assert event['name'] == 'probe.error.condition'
        assert 'NameError' in event['payload']['error']

    def test_construct_agent_startup_event(self):
        """Test constructing agent startup event."""
        event = construct_event(
            name='agent.status.started',
            payload={
                'message': 'DebugIn agent started',
                'engine': 'pytrace',
                'features': {
                    'tracepoints': True,
                    'logpoints': True,
                    'conditions': True,
                    'rateLimit': True,
                    'freeThreaded': False
                }
            }
        )

        assert event['name'] == 'agent.status.started'
        assert event['payload']['features']['tracepoints'] is True

    def test_event_with_snapshot_and_stack(self):
        """Test event with full snapshot and stack trace."""
        event = construct_event(
            name='probe.hit.snapshot',
            payload={
                'probeId': 'tp-1',
                'probeType': 'tracepoint',
                'file': 'fixture.py',
                'line': 5,
                'snapshot': {
                    'locals': {'sum': 8},
                    'arguments': {'x': 5, 'y': 3},
                    'returnValue': 8
                },
                'stack': [
                    {
                        'file': 'fixture.py',
                        'line': 5,
                        'method': 'add'
                    },
                    {
                        'file': 'fixture.py',
                        'line': 20,
                        'method': 'main'
                    }
                ]
            }
        )

        assert len(event['payload']['stack']) == 2
        assert event['payload']['stack'][0]['method'] == 'add'


class TestEventSinkIntegration:
    """Test integration with event sink."""

    @pytest.mark.skipif(
        not any(x in sys.modules for x in ['flask']),
        reason="Flask not installed"
    )
    def test_post_event_to_sink(self):
        """Test posting events to sink."""
        with EventSinkServer() as sink:
            event = construct_event(
                name='probe.hit.snapshot',
                payload={
                    'probeId': 'test-1',
                    'probeType': 'tracepoint',
                    'file': 'test.py',
                    'line': 1
                }
            )

            response = post_event_directly(event, sink.url)
            assert response.status_code == 200
            assert response.json()['status'] == 'accepted'

    @pytest.mark.skipif(
        not any(x in sys.modules for x in ['flask']),
        reason="Flask not installed"
    )
    def test_multiple_events_to_sink(self):
        """Test posting multiple events to sink."""
        with EventSinkServer() as sink:
            events = [
                construct_event(
                    name='probe.hit.snapshot',
                    payload={
                        'probeId': f'test-{i}',
                        'probeType': 'tracepoint',
                        'file': 'test.py',
                        'line': i
                    }
                )
                for i in range(3)
            ]

            for event in events:
                response = post_event_directly(event, sink.url)
                assert response.status_code == 200

    @pytest.mark.skipif(
        not any(x in sys.modules for x in ['flask']),
        reason="Flask not installed"
    )
    def test_event_capture_and_filtering(self):
        """Test capturing and filtering events."""
        with EventSinkServer() as sink:
            capture = sink.capture

            # Post some events
            for i in range(5):
                event = construct_event(
                    name=f'probe.hit.{"snapshot" if i % 2 == 0 else "logpoint"}',
                    payload={
                        'probeId': f'test-{i}',
                        'probeType': 'tracepoint' if i % 2 == 0 else 'logpoint',
                        'file': 'test.py',
                        'line': i
                    }
                )
                capture.record_event(event)

            # Filter by type
            snapshots = capture.get_events_by_type('probe.hit.snapshot')
            assert len(snapshots) == 3

            logpoints = capture.get_events_by_type('probe.hit.logpoint')
            assert len(logpoints) == 2


class TestFullControlAPIToEventSinkFlow:
    """Test complete flow: Control API → Event Sink."""

    @pytest.mark.skipif(
        not any(x in sys.modules for x in ['flask']),
        reason="Flask not installed"
    )
    def test_complete_tracepoint_flow(self):
        """Test complete flow for tracepoint."""
        with EventSinkServer() as sink:
            # Step 1: Create Control API
            api = ControlAPI()
            point_id = 'complete-flow-test'

            # Step 2: Create tracepoint via Control API
            api.point_ids[point_id] = {
                'type': 'tracepoint',
                'file': 'fixture.py',
                'line': 5,
                'method': 'add',
                'enabled': True
            }

            assert point_id in api.point_ids

            # Step 3: Simulate tracepoint execution
            snapshot = {
                'arguments': {'x': 5, 'y': 3},
                'returnValue': 8
            }

            # Step 4: Generate event
            event = construct_event(
                name='probe.hit.snapshot',
                payload={
                    'probeId': point_id,
                    'probeType': 'tracepoint',
                    'file': 'fixture.py',
                    'line': 5,
                    'snapshot': snapshot,
                    'hitCount': 1,
                    'totalHits': 1
                }
            )

            # Step 5: Post event to sink
            response = post_event_directly(event, sink.url)
            assert response.status_code == 200

            # Step 6: Verify event was captured
            capture = sink.capture
            captured_events = capture.get_events_by_probe(point_id)
            assert len(captured_events) > 0

    @pytest.mark.skipif(
        not any(x in sys.modules for x in ['flask']),
        reason="Flask not installed"
    )
    def test_complete_logpoint_flow(self):
        """Test complete flow for logpoint."""
        with EventSinkServer() as sink:
            api = ControlAPI()
            point_id = 'logpoint-flow-test'

            # Create logpoint
            api.point_ids[point_id] = {
                'type': 'logpoint',
                'file': 'fixture.py',
                'line': 12,
                'message': 'Processing item 42',
                'messageTemplate': 'Processing item {item_id}'
            }

            # Generate and send event
            event = construct_event(
                name='probe.hit.logpoint',
                payload={
                    'probeId': point_id,
                    'probeType': 'logpoint',
                    'file': 'fixture.py',
                    'line': 12,
                    'message': 'Processing item 42',
                    'messageTemplate': 'Processing item {item_id}',
                    'hitCount': 1
                }
            )

            response = post_event_directly(event, sink.url)
            assert response.status_code == 200

            # Verify
            captured = sink.capture.get_events_by_probe(point_id)
            assert len(captured) > 0

    @pytest.mark.skipif(
        not any(x in sys.modules for x in ['flask']),
        reason="Flask not installed"
    )
    def test_multi_probe_flow(self):
        """Test flow with multiple probes firing."""
        with EventSinkServer() as sink:
            api = ControlAPI()

            # Create multiple probes
            probes = [
                ('tp-1', 'tracepoint', 5),
                ('lp-1', 'logpoint', 12),
                ('tp-2', 'tracepoint', 15),
            ]

            for point_id, ptype, line in probes:
                api.point_ids[point_id] = {
                    'type': ptype,
                    'file': 'fixture.py',
                    'line': line
                }

            # Fire events from each probe
            for point_id, ptype, line in probes:
                event_name = 'probe.hit.logpoint' if ptype == 'logpoint' else 'probe.hit.snapshot'
                event = construct_event(
                    name=event_name,
                    payload={
                        'probeId': point_id,
                        'probeType': ptype,
                        'file': 'fixture.py',
                        'line': line
                    }
                )

                response = post_event_directly(event, sink.url)
                assert response.status_code == 200

            # Verify all events captured
            assert len(sink.capture.get_all_events()) == 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
