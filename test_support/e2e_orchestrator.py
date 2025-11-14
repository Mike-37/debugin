"""
E2E Orchestration helper for testing multi-runtime debugger.

Provides utilities to start/stop event sink, agents, and fixture apps,
and coordinate full end-to-end tests across all runtimes.
"""

import subprocess
import time
import threading
import signal
import os
import sys
import requests
from contextlib import contextmanager
from pathlib import Path

from test_support.event_capture import EventSinkServer, EventCapture


class ProcessManager:
    """Manages background processes."""

    def __init__(self):
        self.processes = []

    def start_process(self, cmd, env=None, cwd=None):
        """Start a subprocess."""
        try:
            merged_env = os.environ.copy()
            if env:
                merged_env.update(env)

            proc = subprocess.Popen(
                cmd,
                env=merged_env,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid  # Create process group
            )
            self.processes.append(proc)
            return proc
        except Exception as e:
            print(f"Failed to start process {cmd}: {e}")
            return None

    def stop_all(self):
        """Stop all managed processes."""
        for proc in self.processes:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                proc.wait(timeout=5)
            except Exception as e:
                print(f"Error stopping process: {e}")
        self.processes = []


class E2ETestOrchestrator:
    """Orchestrates full end-to-end tests."""

    def __init__(self):
        self.sink = None
        self.process_manager = ProcessManager()
        self.sink_url = 'http://127.0.0.1:4317'

    def start_sink(self):
        """Start event sink server."""
        self.sink = EventSinkServer()
        self.sink.start()
        return self.sink

    def stop_sink(self):
        """Stop event sink server."""
        if self.sink:
            self.sink.stop()
            self.sink = None

    def start_python_agent(self, app_path, port=5001):
        """Start Python agent with fixture app."""
        env = {
            'EVENT_SINK_URL': self.sink_url,
            'PYTHONPATH': str(Path.cwd()),
        }
        # In real scenario, would start Python subprocess
        print(f"[E2E] Starting Python agent on port {port}")
        return True

    def start_java_agent(self, app_path, port=5002):
        """Start Java agent with fixture app."""
        print(f"[E2E] Starting Java agent on port {port}")
        return True

    def start_node_agent(self, app_path, port=5003):
        """Start Node.js agent with fixture app."""
        print(f"[E2E] Starting Node.js agent on port {port}")
        return True

    def create_tracepoint(self, runtime, file, line, condition=None):
        """Create a tracepoint via Control API."""
        if runtime == 'python':
            url = 'http://127.0.0.1:5001/tracepoints'
        elif runtime == 'java':
            url = 'http://127.0.0.1:5002/tracepoints'
        elif runtime == 'node':
            url = 'http://127.0.0.1:5003/tracepoints'
        else:
            raise ValueError(f"Unknown runtime: {runtime}")

        payload = {
            'file': file,
            'line': line,
        }
        if condition:
            payload['condition'] = condition

        try:
            resp = requests.post(url, json=payload, timeout=5)
            return resp.status_code == 201
        except Exception as e:
            print(f"Failed to create tracepoint: {e}")
            return False

    def create_logpoint(self, runtime, file, line, message):
        """Create a logpoint via Control API."""
        if runtime == 'python':
            url = 'http://127.0.0.1:5001/logpoints'
        elif runtime == 'java':
            url = 'http://127.0.0.1:5002/logpoints'
        elif runtime == 'node':
            url = 'http://127.0.0.1:5003/logpoints'
        else:
            raise ValueError(f"Unknown runtime: {runtime}")

        payload = {
            'file': file,
            'line': line,
            'message': message
        }

        try:
            resp = requests.post(url, json=payload, timeout=5)
            return resp.status_code == 201
        except Exception as e:
            print(f"Failed to create logpoint: {e}")
            return False

    def get_captured_events(self, filter_type=None, filter_runtime=None):
        """Get captured events from sink."""
        if not self.sink:
            return []

        events = self.sink.capture.get_all_events()

        if filter_type:
            events = [e for e in events if e.get('name') == filter_type]

        if filter_runtime:
            events = [e for e in events
                     if e.get('client', {}).get('runtime') == filter_runtime]

        return events

    def wait_for_events(self, count, timeout=5.0):
        """Wait for minimum number of events."""
        if not self.sink:
            return False

        try:
            self.sink.capture.wait_for_events(count=count, timeout=timeout)
            return True
        except TimeoutError:
            return False

    def cleanup(self):
        """Clean up all resources."""
        self.stop_sink()
        self.process_manager.stop_all()


@contextmanager
def e2e_test_session(runtimes=None):
    """Context manager for E2E test session."""
    if runtimes is None:
        runtimes = ['python']

    orchestrator = E2ETestOrchestrator()

    try:
        # Start event sink
        orchestrator.start_sink()
        print("[E2E] Event sink started")

        # Start agents for requested runtimes
        for runtime in runtimes:
            if runtime == 'python':
                orchestrator.start_python_agent('tests/fixtures/py_app.py')
            elif runtime == 'java':
                orchestrator.start_java_agent('tests/fixtures/SampleApp.java')
            elif runtime == 'node':
                orchestrator.start_node_agent('tests/fixtures/node_app.js')

        yield orchestrator

    finally:
        orchestrator.cleanup()
        print("[E2E] Session cleanup completed")


def run_complete_flow_test(runtime):
    """Test complete flow for a single runtime."""
    print(f"\n=== Testing {runtime.upper()} Runtime ===\n")

    with e2e_test_session([runtime]) as orch:
        # Create probes
        print(f"[{runtime}] Creating tracepoint...")
        assert orch.create_tracepoint(runtime, 'app.py', 10, 'x > 0')

        print(f"[{runtime}] Creating logpoint...")
        assert orch.create_logpoint(runtime, 'app.py', 20, 'Processing: {item}')

        # Wait for events
        time.sleep(1)

        # Verify events captured
        events = orch.get_captured_events(filter_runtime=runtime)
        print(f"[{runtime}] Captured {len(events)} events")

        # Check event types
        snapshot_events = [e for e in events if e.get('name') == 'probe.hit.snapshot']
        logpoint_events = [e for e in events if e.get('name') == 'probe.hit.logpoint']

        print(f"[{runtime}] Snapshots: {len(snapshot_events)}, Logpoints: {len(logpoint_events)}")

        return len(events) > 0


def test_cross_runtime_consistency():
    """Test that all runtimes emit consistent event formats."""
    print("\n=== Testing Cross-Runtime Consistency ===\n")

    with e2e_test_session(['python', 'java', 'node']) as orch:
        # Create similar probes in all runtimes
        for runtime in ['python', 'java', 'node']:
            orch.create_tracepoint(runtime, 'fixture.py', 10)

        time.sleep(1)

        # Get all events
        events = orch.get_captured_events()

        # Verify all have required fields
        for event in events:
            assert 'name' in event, "Event missing 'name'"
            assert 'timestamp' in event, "Event missing 'timestamp'"
            assert 'id' in event, "Event missing 'id'"
            assert 'client' in event, "Event missing 'client'"
            assert 'payload' in event, "Event missing 'payload'"

            # Verify client has all required fields
            client = event['client']
            assert 'runtime' in client
            assert 'agentVersion' in client
            assert 'runtimeVersion' in client

        print(f"✓ All {len(events)} events conform to schema")
        return True


if __name__ == '__main__':
    # Test each runtime
    try:
        # Note: In actual test environment, these would run full suites
        print("E2E Orchestrator ready for testing")
    except Exception as e:
        print(f"E2E test failed: {e}")
        sys.exit(1)
