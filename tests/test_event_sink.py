#!/usr/bin/env python3
"""
Tests for the InProcessEventSink test harness
Validates HTTP server, event acceptance, validation, and helper functionality
"""

import json
import pytest
import requests
import threading
import time
from pathlib import Path

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from test_support.event_capture import EventSinkServer


class TestInProcessEventSink:
    """Tests for the InProcessEventSink HTTP server"""

    @pytest.fixture
    def sink(self):
        """Create an event sink for testing"""
        server = EventSinkServer()
        server.start()
        yield server
        server.stop()

    def test_sink_starts_on_free_port(self, sink):
        """Verify that sink chooses a free port and is accessible"""
        assert sink.port > 0
        assert sink.host is not None

        # Test health endpoint
        response = requests.get(f"http://{sink.host}:{sink.port}/health")
        assert response.status_code == 200

    def test_post_valid_event_returns_200(self, sink):
        """Valid event POST should return 200 and store event"""
        event = {
            "type": "tracepoint.hit",
            "id": "test-id-123",
            "timestamp": "2025-11-14T12:00:00Z",
            "lang": "python",
            "client": {
                "hostname": "test-host",
                "applicationName": "test-app",
                "agentVersion": "0.3.0",
                "runtime": "cpython",
                "runtimeVersion": "3.11.0"
            },
            "location": {
                "file": "test.py",
                "line": 42
            },
            "probeId": "probe-1",
            "tags": [],
            "payload": {}
        }

        response = requests.post(
            f"http://{sink.host}:{sink.port}/api/events",
            json=event
        )
        assert response.status_code == 200
        assert len(sink.events) == 1
        assert sink.events[0]["id"] == "test-id-123"

    def test_invalid_json_returns_400(self, sink):
        """Invalid JSON should return 400"""
        response = requests.post(
            f"http://{sink.host}:{sink.port}/api/events",
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data or "message" in data

    def test_missing_required_field_returns_422(self, sink):
        """Missing required field should return 422 with field name"""
        event = {
            "type": "tracepoint.hit",
            "id": "test-id",
            # Missing timestamp, lang, client, etc.
            "payload": {}
        }

        response = requests.post(
            f"http://{sink.host}:{sink.port}/api/events",
            json=event
        )
        assert response.status_code == 422
        data = response.json()
        # Should indicate missing required fields
        assert "error" in data or "message" in data

    def test_wait_for_single_event_succeeds(self, sink):
        """wait_for with timeout should succeed when event arrives"""
        def post_event_delayed():
            time.sleep(0.5)
            event = {
                "type": "tracepoint.hit",
                "id": "delayed-event",
                "timestamp": "2025-11-14T12:00:00Z",
                "lang": "python",
                "client": {"hostname": "test", "applicationName": "test",
                          "agentVersion": "0.3.0", "runtime": "cpython", "runtimeVersion": "3.11"},
                "location": {"file": "test.py", "line": 1},
                "probeId": "p1",
                "tags": [],
                "payload": {}
            }
            requests.post(f"http://{sink.host}:{sink.port}/api/events", json=event)

        thread = threading.Thread(target=post_event_delayed)
        thread.start()

        # Wait for event with 2 second timeout
        def predicate(event):
            return event.get("id") == "delayed-event"

        start = time.time()
        events = sink.wait_for(predicate, count=1, timeout=2)
        elapsed = time.time() - start

        assert len(events) == 1
        assert events[0]["id"] == "delayed-event"
        assert elapsed < 2

        thread.join()

    def test_wait_for_timeout_raises_error(self, sink):
        """wait_for with timeout should raise TimeoutError if event doesn't arrive"""
        def predicate(event):
            return event.get("id") == "never-arrives"

        with pytest.raises(TimeoutError):
            sink.wait_for(predicate, count=1, timeout=0.5)

    def test_wait_for_multiple_events(self, sink):
        """wait_for should wait for multiple matching events"""
        # Post 3 events
        for i in range(3):
            event = {
                "type": "tracepoint.hit",
                "id": f"event-{i}",
                "timestamp": "2025-11-14T12:00:00Z",
                "lang": "python",
                "client": {"hostname": "test", "applicationName": "test",
                          "agentVersion": "0.3.0", "runtime": "cpython", "runtimeVersion": "3.11"},
                "location": {"file": "test.py", "line": 1},
                "probeId": "p1",
                "tags": [],
                "payload": {}
            }
            requests.post(f"http://{sink.host}:{sink.port}/api/events", json=event)

        # Wait for all 3
        def predicate(event):
            return event.get("type") == "tracepoint.hit"

        events = sink.wait_for(predicate, count=3, timeout=2)
        assert len(events) == 3

    def test_multiple_sinks_use_different_ports(self):
        """Multiple sinks should not conflict on ports"""
        sink1 = EventSinkServer()
        sink2 = EventSinkServer()

        sink1.start()
        sink2.start()

        try:
            assert sink1.port != sink2.port
            assert sink1.port > 0
            assert sink2.port > 0

            # Both should be accessible
            r1 = requests.get(f"http://{sink1.host}:{sink1.port}/health")
            r2 = requests.get(f"http://{sink2.host}:{sink2.port}/health")

            assert r1.status_code == 200
            assert r2.status_code == 200
        finally:
            sink1.stop()
            sink2.stop()

    def test_filter_events_by_type(self, sink):
        """Events should be filterable by type"""
        # Post mixed events
        events_to_post = [
            {"type": "tracepoint.hit", "id": "t1", "probeId": "p1"},
            {"type": "logpoint.hit", "id": "l1", "probeId": "p2"},
            {"type": "tracepoint.hit", "id": "t2", "probeId": "p1"},
        ]

        for ev in events_to_post:
            full_event = {
                **ev,
                "timestamp": "2025-11-14T12:00:00Z",
                "lang": "python",
                "client": {"hostname": "test", "applicationName": "test",
                          "agentVersion": "0.3.0", "runtime": "cpython", "runtimeVersion": "3.11"},
                "location": {"file": "test.py", "line": 1},
                "tags": [],
                "payload": {}
            }
            requests.post(f"http://{sink.host}:{sink.port}/api/events", json=full_event)

        # Filter for tracepoint events
        tracepoints = [e for e in sink.events if e["type"] == "tracepoint.hit"]
        assert len(tracepoints) == 2
        assert all(e["type"] == "tracepoint.hit" for e in tracepoints)

    def test_clear_events(self, sink):
        """Events should be clearable for test isolation"""
        # Post events
        event = {
            "type": "tracepoint.hit",
            "id": "test-1",
            "timestamp": "2025-11-14T12:00:00Z",
            "lang": "python",
            "client": {"hostname": "test", "applicationName": "test",
                      "agentVersion": "0.3.0", "runtime": "cpython", "runtimeVersion": "3.11"},
            "location": {"file": "test.py", "line": 1},
            "probeId": "p1",
            "tags": [],
            "payload": {}
        }
        requests.post(f"http://{sink.host}:{sink.port}/api/events", json=event)

        assert len(sink.events) == 1

        # Clear and verify
        sink.clear()
        assert len(sink.events) == 0
