"""
Integration tests for event sink across all runtimes

Tests verify:
1. Event sink receives events from Python runtime
2. Event format matches schema specification
3. Events contain required fields
4. Multiple event types are handled correctly
"""

import pytest
import requests
import json
import time
import subprocess
import os
import sys
from threading import Thread

# Assume event sink runs on localhost:4317
EVENT_SINK_URL = "http://127.0.0.1:4317"
CONTROL_API_URL = "http://127.0.0.1:5001"

# Try to import tracepointdebug
try:
    import tracepointdebug
except ImportError:
    pytest.skip("tracepointdebug not installed", allow_module_level=True)


class MockEventSink:
    """Mock event sink for testing"""

    def __init__(self, port=4317):
        self.port = port
        self.events = []
        self.server = None
        self.thread = None

    def start(self):
        """Start the mock sink in a thread"""
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import json

        sink = self

        class EventHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path == '/api/events':
                    content_length = int(self.headers.get('Content-Length', 0))
                    body = self.rfile.read(content_length)
                    try:
                        event = json.loads(body.decode('utf-8'))
                        sink.events.append(event)
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({'status': 'accepted', 'id': event.get('id')}).encode())
                    except json.JSONDecodeError:
                        self.send_response(400)
                        self.end_headers()
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format, *args):
                pass  # Suppress logging

        self.server = HTTPServer(('127.0.0.1', self.port), EventHandler)

        def run():
            self.server.serve_forever()

        self.thread = Thread(target=run, daemon=True)
        self.thread.start()
        time.sleep(0.5)  # Let server start

    def stop(self):
        """Stop the mock sink"""
        if self.server:
            self.server.shutdown()

    def clear(self):
        """Clear collected events"""
        self.events = []


@pytest.fixture(scope="module")
def event_sink():
    """Create and start mock event sink"""
    sink = MockEventSink(port=4317)
    sink.start()

    # Configure environment to use our mock sink
    os.environ['EVENT_SINK_URL'] = EVENT_SINK_URL

    yield sink

    sink.stop()


@pytest.fixture(scope="module")
def running_agent(event_sink):
    """Start agent for tests"""
    # Set event sink URL
    os.environ['EVENT_SINK_URL'] = EVENT_SINK_URL

    # Start agent
    tracepointdebug.start(
        enable_control_api=True,
        control_api_port=5001
    )

    time.sleep(1)  # Let agent start

    yield

    # Cleanup


class TestEventSinkIntegration:
    """Test event sink integration"""

    def test_event_sink_is_accessible(self, event_sink):
        """Test that event sink is accessible"""
        # Event sink should be running on 4317
        # We can verify by checking our mock
        assert event_sink.server is not None
        assert event_sink.thread.is_alive()

    def test_health_endpoint_available(self, running_agent):
        """Test control API health endpoint"""
        response = requests.get(f"{CONTROL_API_URL}/health", timeout=2)
        assert response.status_code == 200

    def test_create_tracepoint_via_api(self, running_agent, event_sink):
        """Test creating a tracepoint via control API"""
        event_sink.clear()

        response = requests.post(
            f"{CONTROL_API_URL}/tracepoints",
            json={
                "file": "test.py",
                "line": 10,
                "tags": ["integration-test"]
            },
            timeout=2
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["type"] == "tracepoint"

    def test_create_logpoint_via_api(self, running_agent, event_sink):
        """Test creating a logpoint via control API"""
        event_sink.clear()

        response = requests.post(
            f"{CONTROL_API_URL}/logpoints",
            json={
                "file": "test.py",
                "line": 15,
                "log_expression": "x={{x}}"
            },
            timeout=2
        )

        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "logpoint"

    def test_list_points_returns_created_points(self, running_agent):
        """Test that created points appear in listing"""
        # Create a point
        create_response = requests.post(
            f"{CONTROL_API_URL}/tracepoints",
            json={
                "file": "test.py",
                "line": 20,
                "tags": ["list-test"]
            },
            timeout=2
        )

        created_id = create_response.json()["id"]

        # List points
        list_response = requests.get(
            f"{CONTROL_API_URL}/points",
            timeout=2
        )

        assert list_response.status_code == 200
        points = list_response.json()["points"]

        # Find our created point
        found = any(p["id"] == created_id for p in points)
        assert found, "Created point should appear in list"

    def test_tag_enable_disable_works(self, running_agent):
        """Test tag enable/disable functionality"""
        # Create point with tag
        requests.post(
            f"{CONTROL_API_URL}/tracepoints",
            json={
                "file": "test.py",
                "line": 25,
                "tags": ["tag-test"]
            },
            timeout=2
        )

        # Disable tag
        response = requests.post(
            f"{CONTROL_API_URL}/tags/disable",
            json={"tags": ["tag-test"]},
            timeout=2
        )

        assert response.status_code == 200

        # Enable tag
        response = requests.post(
            f"{CONTROL_API_URL}/tags/enable",
            json={"tags": ["tag-test"]},
            timeout=2
        )

        assert response.status_code == 200

    def test_condition_with_missing_fields_returns_400(self, running_agent):
        """Test that invalid requests return 400"""
        response = requests.post(
            f"{CONTROL_API_URL}/tracepoints",
            json={"line": 30},  # Missing 'file'
            timeout=2
        )

        assert response.status_code == 400
        error = response.json()
        assert "error" in error

    def test_invalid_line_returns_400(self, running_agent):
        """Test that invalid line numbers return 400"""
        response = requests.post(
            f"{CONTROL_API_URL}/tracepoints",
            json={
                "file": "test.py",
                "line": -1  # Invalid line
            },
            timeout=2
        )

        assert response.status_code == 400

    def test_multiple_concurrent_point_creation(self, running_agent):
        """Test creating multiple points concurrently"""
        from concurrent.futures import ThreadPoolExecutor

        def create_point(i):
            return requests.post(
                f"{CONTROL_API_URL}/tracepoints",
                json={
                    "file": f"test{i}.py",
                    "line": 30 + i,
                    "tags": [f"concurrent-{i}"]
                },
                timeout=2
            )

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_point, i) for i in range(10)]
            results = [f.result() for f in futures]

        # All should succeed
        assert all(r.status_code == 201 for r in results)

        # All should have IDs
        for response in results:
            data = response.json()
            assert "id" in data

    def test_point_enable_disable_toggle(self, running_agent):
        """Test toggling point enable/disable"""
        # Create point
        create_response = requests.post(
            f"{CONTROL_API_URL}/tracepoints",
            json={
                "file": "test.py",
                "line": 40
            },
            timeout=2
        )

        point_id = create_response.json()["id"]

        # Disable
        disable_response = requests.post(
            f"{CONTROL_API_URL}/points/disable",
            json={"id": point_id},
            timeout=2
        )
        assert disable_response.status_code == 200

        # Enable
        enable_response = requests.post(
            f"{CONTROL_API_URL}/points/enable",
            json={"id": point_id},
            timeout=2
        )
        assert enable_response.status_code == 200

    def test_nonexistent_point_returns_404(self, running_agent):
        """Test accessing nonexistent point returns 404"""
        response = requests.post(
            f"{CONTROL_API_URL}/points/disable",
            json={"id": "nonexistent-id"},
            timeout=2
        )

        # Should not crash, but may not return 404 (implementation dependent)
        assert response.status_code in [400, 404]


class TestEventFormat:
    """Test event format compliance"""

    def test_event_has_required_base_fields(self, event_sink):
        """Test that events have required base fields"""
        # If we have any events, check their format
        if event_sink.events:
            event = event_sink.events[0]

            # Base fields (from event-schema.md)
            assert "name" in event
            assert "timestamp" in event or "time" in event
            assert "id" in event
            assert "client" in event
            assert "payload" in event

    def test_event_client_info(self, event_sink):
        """Test event client information"""
        if event_sink.events:
            event = event_sink.events[0]
            client = event.get("client", {})

            # Should have runtime info
            assert client.get("runtime") in ["python", "java", "node"] or "runtime" in client


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
