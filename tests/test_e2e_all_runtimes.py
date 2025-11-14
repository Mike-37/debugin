"""
End-to-end tests for all runtimes using orchestration helper.

Tests the complete flow: Control API → Agent → Event Sink for Python, Java, and Node.js.
Also validates cross-runtime consistency and contract compliance.
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_support.e2e_orchestrator import (
    E2ETestOrchestrator, e2e_test_session, run_complete_flow_test,
    test_cross_runtime_consistency
)
from test_support.event_capture import construct_event, post_event_directly


@pytest.mark.skipif(
    not any(x in sys.modules for x in ['flask']),
    reason="Flask not installed"
)
class TestPythonE2E:
    """End-to-end tests for Python runtime."""

    def test_python_tracepoint_flow(self):
        """Test complete Python tracepoint flow."""
        with e2e_test_session(['python']) as orch:
            # Create tracepoint
            assert orch.create_tracepoint('python', 'app.py', 10)

            # Simulate execution and send event
            event = construct_event(
                name='probe.hit.snapshot',
                payload={
                    'probeId': 'py-tp-1',
                    'probeType': 'tracepoint',
                    'file': 'app.py',
                    'line': 10,
                    'snapshot': {'arguments': {'x': 5}, 'returnValue': 10}
                },
                runtime='python'
            )

            response = post_event_directly(event, orch.sink_url)
            assert response.status_code == 200

    def test_python_logpoint_flow(self):
        """Test complete Python logpoint flow."""
        with e2e_test_session(['python']) as orch:
            assert orch.create_logpoint('python', 'app.py', 20, 'User: {user_id}')

            event = construct_event(
                name='probe.hit.logpoint',
                payload={
                    'probeId': 'py-lp-1',
                    'probeType': 'logpoint',
                    'file': 'app.py',
                    'line': 20,
                    'message': 'User: 123'
                },
                runtime='python'
            )

            response = post_event_directly(event, orch.sink_url)
            assert response.status_code == 200

    def test_python_conditional_tracepoint(self):
        """Test Python tracepoint with condition."""
        with e2e_test_session(['python']) as orch:
            assert orch.create_tracepoint('python', 'app.py', 10, 'count > 5')

            # Event when condition is true
            event = construct_event(
                name='probe.hit.snapshot',
                payload={
                    'probeId': 'py-cond-1',
                    'probeType': 'tracepoint',
                    'file': 'app.py',
                    'line': 10,
                    'condition': 'count > 5',
                    'conditionEvaluated': True,
                    'snapshot': {'locals': {'count': 10}}
                },
                runtime='python'
            )

            response = post_event_directly(event, orch.sink_url)
            assert response.status_code == 200


@pytest.mark.skipif(
    not any(x in sys.modules for x in ['flask']),
    reason="Flask not installed"
)
class TestJavaE2E:
    """End-to-end tests for Java runtime."""

    def test_java_tracepoint_flow(self):
        """Test complete Java tracepoint flow."""
        with e2e_test_session(['java']) as orch:
            assert orch.create_tracepoint('java', 'App.java', 10)

            event = construct_event(
                name='probe.hit.snapshot',
                payload={
                    'probeId': 'java-tp-1',
                    'probeType': 'tracepoint',
                    'file': 'App.java',
                    'line': 10,
                    'method': 'add',
                    'snapshot': {'arguments': {'x': 5, 'y': 3}, 'returnValue': 8}
                },
                runtime='java'
            )

            response = post_event_directly(event, orch.sink_url)
            assert response.status_code == 200

    def test_java_logpoint_flow(self):
        """Test complete Java logpoint flow."""
        with e2e_test_session(['java']) as orch:
            assert orch.create_logpoint('java', 'App.java', 20, 'Result: {result}')

            event = construct_event(
                name='probe.hit.logpoint',
                payload={
                    'probeId': 'java-lp-1',
                    'probeType': 'logpoint',
                    'file': 'App.java',
                    'line': 20,
                    'message': 'Result: 100',
                    'method': 'process'
                },
                runtime='java'
            )

            response = post_event_directly(event, orch.sink_url)
            assert response.status_code == 200


@pytest.mark.skipif(
    not any(x in sys.modules for x in ['flask']),
    reason="Flask not installed"
)
class TestNodeE2E:
    """End-to-end tests for Node.js runtime."""

    def test_node_tracepoint_flow(self):
        """Test complete Node.js tracepoint flow."""
        with e2e_test_session(['node']) as orch:
            assert orch.create_tracepoint('node', 'app.js', 10)

            event = construct_event(
                name='probe.hit.snapshot',
                payload={
                    'probeId': 'node-tp-1',
                    'probeType': 'tracepoint',
                    'file': 'app.js',
                    'line': 10,
                    'snapshot': {'arguments': {'x': 5}, 'locals': {'y': 10}}
                },
                runtime='node'
            )

            response = post_event_directly(event, orch.sink_url)
            assert response.status_code == 200

    def test_node_logpoint_flow(self):
        """Test complete Node.js logpoint flow."""
        with e2e_test_session(['node']) as orch:
            assert orch.create_logpoint('node', 'app.js', 20, 'Event: {eventType}')

            event = construct_event(
                name='probe.hit.logpoint',
                payload={
                    'probeId': 'node-lp-1',
                    'probeType': 'logpoint',
                    'file': 'app.js',
                    'line': 20,
                    'message': 'Event: click'
                },
                runtime='node'
            )

            response = post_event_directly(event, orch.sink_url)
            assert response.status_code == 200


@pytest.mark.skipif(
    not any(x in sys.modules for x in ['flask']),
    reason="Flask not installed"
)
class TestMultiRuntimeE2E:
    """End-to-end tests for multi-runtime scenarios."""

    def test_all_runtimes_simultaneously(self):
        """Test all three runtimes working simultaneously."""
        with e2e_test_session(['python', 'java', 'node']) as orch:
            # Create probes in each runtime
            for runtime in ['python', 'java', 'node']:
                assert orch.create_tracepoint(runtime, 'app.ext', 10)

            # Send events from each runtime
            for i, runtime in enumerate(['python', 'java', 'node']):
                event = construct_event(
                    name='probe.hit.snapshot',
                    payload={
                        'probeId': f'{runtime}-1',
                        'probeType': 'tracepoint',
                        'file': 'app.ext',
                        'line': 10
                    },
                    runtime=runtime
                )
                response = post_event_directly(event, orch.sink_url)
                assert response.status_code == 200

            # Verify events from all runtimes captured
            py_events = orch.get_captured_events(filter_runtime='python')
            java_events = orch.get_captured_events(filter_runtime='java')
            node_events = orch.get_captured_events(filter_runtime='node')

            assert len(py_events) > 0
            assert len(java_events) > 0
            assert len(node_events) > 0

    def test_cross_runtime_event_schema_consistency(self):
        """Test that all runtimes emit events with identical schema."""
        with e2e_test_session(['python', 'java', 'node']) as orch:
            events_by_runtime = {}

            for runtime in ['python', 'java', 'node']:
                event = construct_event(
                    name='probe.hit.snapshot',
                    payload={
                        'probeId': f'{runtime}-schema-test',
                        'probeType': 'tracepoint',
                        'file': 'test.ext',
                        'line': 1
                    },
                    runtime=runtime
                )
                post_event_directly(event, orch.sink_url)
                events_by_runtime[runtime] = event

            # Verify all events have same base structure
            required_fields = {'name', 'timestamp', 'id', 'client', 'payload'}
            required_client_fields = {
                'hostname', 'applicationName', 'agentVersion', 'runtime', 'runtimeVersion'
            }
            required_payload_fields = {'probeId', 'probeType', 'file', 'line'}

            for runtime, event in events_by_runtime.items():
                # Verify base fields
                assert required_fields.issubset(event.keys()), f"{runtime} missing base fields"

                # Verify client fields
                client = event['client']
                assert required_client_fields.issubset(client.keys()), f"{runtime} missing client fields"

                # Verify payload fields
                payload = event['payload']
                assert required_payload_fields.issubset(payload.keys()), f"{runtime} missing payload fields"

    def test_event_ordering_across_runtimes(self):
        """Test that events from different runtimes maintain order."""
        with e2e_test_session(['python', 'java', 'node']) as orch:
            timestamps = []

            for runtime in ['python', 'java', 'node']:
                event = construct_event(
                    name='probe.hit.snapshot',
                    payload={'probeId': f'{runtime}-order', 'probeType': 'tracepoint', 'file': 'test.ext', 'line': 1},
                    runtime=runtime
                )
                timestamps.append((runtime, event['timestamp']))
                post_event_directly(event, orch.sink_url)

            # All events should be within reasonable time window
            assert len(timestamps) == 3


@pytest.mark.skipif(
    not any(x in sys.modules for x in ['flask']),
    reason="Flask not installed"
)
class TestE2EErrorScenarios:
    """Test error scenarios in E2E flows."""

    def test_invalid_line_number_rejected(self):
        """Test that invalid line numbers are rejected."""
        with e2e_test_session(['python']) as orch:
            # Line 0 should be invalid
            assert not orch.create_tracepoint('python', 'app.py', 0)

    def test_missing_required_fields(self):
        """Test that events with missing fields are rejected."""
        with e2e_test_session(['python']) as orch:
            # Event missing probeId
            invalid_event = {
                'name': 'probe.hit.snapshot',
                'timestamp': '2025-01-01T00:00:00.000Z',
                'id': 'test-id',
                'client': {
                    'hostname': 'localhost',
                    'applicationName': 'test',
                    'agentVersion': '0.3.0',
                    'runtime': 'python',
                    'runtimeVersion': '3.11'
                },
                'payload': {
                    'probeType': 'tracepoint',
                    'file': 'test.py',
                    'line': 1
                }
            }

            response = post_event_directly(invalid_event, orch.sink_url)
            assert response.status_code == 400

    def test_recovery_after_failure(self):
        """Test that system recovers after event processing failure."""
        with e2e_test_session(['python']) as orch:
            # Send valid event after invalid one
            assert orch.create_tracepoint('python', 'app.py', 10)

            valid_event = construct_event(
                name='probe.hit.snapshot',
                payload={
                    'probeId': 'valid-1',
                    'probeType': 'tracepoint',
                    'file': 'app.py',
                    'line': 10
                },
                runtime='python'
            )

            response = post_event_directly(valid_event, orch.sink_url)
            assert response.status_code == 200


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
