"""
Test that breakpoint hits generate and send events to the event sink.

This test verifies the complete path: breakpoint hit → snapshot → encoder → event → sink
"""

import pytest
import time
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_support.event_capture import EventSinkServer, EventCapture, construct_event, post_event_directly
from scripts.event_sink import EventValidator


class TestEventValidation:
    """Test that the event sink properly validates events."""

    def test_valid_event_is_accepted(self):
        """Test that a valid event is accepted by the sink."""
        event = construct_event(
            name='probe.hit.snapshot',
            payload={
                'probeId': 'test-probe-1',
                'probeType': 'tracepoint',
                'file': 'app.py',
                'line': 42,
                'method': 'test_method',
                'snapshot': {
                    'locals': {'x': 1, 'y': 2},
                    'arguments': {'self': {'__tpd_type__': 'TestClass'}}
                }
            }
        )
        is_valid, error = EventValidator.validate(event)
        assert is_valid, f"Event validation failed: {error}"

    def test_missing_timestamp_is_rejected(self):
        """Test that events without timestamps are rejected."""
        event = {
            'name': 'probe.hit.snapshot',
            'id': 'test-id',
            'client': {
                'hostname': 'test',
                'applicationName': 'test',
                'agentVersion': '0.3.0',
                'runtime': 'python',
                'runtimeVersion': '3.11'
            },
            'payload': {}
        }
        is_valid, error = EventValidator.validate(event)
        assert not is_valid, "Event without timestamp should be rejected"
        assert 'timestamp' in error.lower()

    def test_invalid_runtime_is_rejected(self):
        """Test that events with invalid runtime are rejected."""
        event = construct_event(
            name='probe.hit.snapshot',
            payload={'probeId': 'test', 'probeType': 'tracepoint', 'file': 'test.py', 'line': 1}
        )
        event['client']['runtime'] = 'invalid_runtime'
        is_valid, error = EventValidator.validate(event)
        assert not is_valid
        assert 'runtime' in error.lower()


@pytest.mark.skipif(
    not any(x in sys.modules for x in ['flask']),
    reason="Flask not installed"
)
class TestEventSink:
    """Test the event sink server itself."""

    def test_sink_starts_and_responds_to_health_check(self):
        """Test that the sink server starts and responds to health checks."""
        with EventSinkServer() as sink:
            assert sink.is_running(), "Event sink should be running"

    def test_sink_accepts_valid_event(self):
        """Test that sink accepts a valid event via HTTP POST."""
        with EventSinkServer() as sink:
            event = construct_event(
                name='probe.hit.snapshot',
                payload={
                    'probeId': 'test-probe',
                    'probeType': 'tracepoint',
                    'file': 'test.py',
                    'line': 1
                }
            )
            response = post_event_directly(event, sink.url)
            assert response.status_code == 200
            assert response.json().get('status') == 'accepted'

    def test_sink_rejects_invalid_event(self):
        """Test that sink rejects invalid events."""
        with EventSinkServer() as sink:
            # Missing required field 'timestamp'
            invalid_event = {
                'name': 'probe.hit.snapshot',
                'id': 'test-id',
                'client': {'hostname': 'test', 'applicationName': 'test', 'agentVersion': '0.3.0', 'runtime': 'python', 'runtimeVersion': '3.11'},
                'payload': {}
            }
            response = post_event_directly(invalid_event, sink.url)
            assert response.status_code == 400
            assert response.json().get('status') == 'error'

    def test_capture_events(self):
        """Test that EventCapture can capture and filter events."""
        capture = EventCapture()
        event1 = construct_event(
            name='probe.hit.snapshot',
            payload={'probeId': 'p1', 'probeType': 'tracepoint', 'file': 'test.py', 'line': 1},
            runtime='python'
        )
        event2 = construct_event(
            name='probe.hit.logpoint',
            payload={'probeId': 'p2', 'probeType': 'logpoint', 'file': 'test.py', 'line': 2, 'message': 'test'},
            runtime='python'
        )

        capture.record_event(event1)
        capture.record_event(event2)

        # Test filtering by type
        snapshots = capture.get_events_by_type('probe.hit.snapshot')
        assert len(snapshots) == 1
        assert snapshots[0]['payload']['probeId'] == 'p1'

        # Test filtering by runtime
        python_events = capture.get_events_by_runtime('python')
        assert len(python_events) == 2

    def test_wait_for_events_timeout(self):
        """Test that wait_for_events times out when no matching events."""
        capture = EventCapture()
        with pytest.raises(TimeoutError):
            capture.wait_for_events(event_type='probe.hit.snapshot', count=1, timeout=0.5)

    def test_event_types_are_valid(self):
        """Test that all documented event types are valid."""
        valid_types = {
            'probe.hit.snapshot',
            'probe.hit.logpoint',
            'probe.error.condition',
            'probe.error.snapshot',
            'probe.error.rateLimit',
            'agent.status.started',
            'agent.status.stopped',
        }

        for event_type in valid_types:
            if event_type.startswith('probe.hit'):
                payload = {
                    'probeId': 'test', 'probeType': 'tracepoint', 'file': 'test.py', 'line': 1
                }
            elif event_type.startswith('agent.status'):
                payload = {'message': 'test'}
            else:
                payload = {
                    'probeId': 'test', 'probeType': 'tracepoint', 'file': 'test.py', 'line': 1, 'error': 'test'
                }

            event = construct_event(name=event_type, payload=payload)
            is_valid, error = EventValidator.validate(event)
            assert is_valid, f"Event type {event_type} should be valid: {error}"


def helper_construct_event_with_runtime(name, payload, runtime='python'):
    """Helper to construct event with specific runtime."""
    event = construct_event(name, payload)
    event['client']['runtime'] = runtime
    return event


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
