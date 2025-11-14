#!/usr/bin/env python3
"""
Tests for canonical probe and event helper builders
Validates make_tracepoint, make_logpoint, and filter predicates
"""

import json
import pytest
from pathlib import Path

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from test_support.event_capture import EventCapture


class TestProbeHelpers:
    """Tests for probe configuration and event helper functions"""

    def test_make_tracepoint_creates_valid_probe(self):
        """make_tracepoint should create a valid probe config"""
        probe = EventCapture.make_tracepoint(
            lang="python",
            file="test.py",
            line=42,
            condition="x > 5"
        )

        assert probe["id"] is not None
        assert probe["file"] == "test.py"
        assert probe["line"] == 42
        assert probe["condition"] == "x > 5"
        assert "sample" in probe
        assert "snapshot" in probe
        assert "tags" in probe

    def test_make_tracepoint_json_serializable(self):
        """Tracepoint should be JSON serializable without custom encoders"""
        probe = EventCapture.make_tracepoint(
            lang="java",
            file="App.java",
            line=10
        )

        # Should not raise
        json_str = json.dumps(probe)
        reconstructed = json.loads(json_str)

        assert reconstructed["file"] == "App.java"
        assert reconstructed["line"] == 10

    def test_make_logpoint_includes_message(self):
        """make_logpoint should include message field"""
        probe = EventCapture.make_logpoint(
            lang="node",
            file="app.js",
            line=5,
            message="User logged in: {user}"
        )

        assert probe["message"] == "User logged in: {user}"
        assert probe["file"] == "app.js"
        assert probe["line"] == 5
        # Should have all other tracepoint fields
        assert "sample" in probe
        assert "snapshot" in probe

    def test_make_logpoint_without_message_valid(self):
        """make_logpoint should work with default message"""
        probe = EventCapture.make_logpoint(
            lang="python",
            file="test.py",
            line=100
        )

        assert "message" in probe
        assert probe["line"] == 100

    def test_probe_with_defaults(self):
        """Probes should have sensible defaults for sample and snapshot"""
        probe = EventCapture.make_tracepoint(
            lang="python",
            file="test.py",
            line=1
        )

        sample = probe.get("sample", {})
        assert "limitPerSecond" in sample or sample.get("limitPerSecond") is not None
        assert "burst" in sample or sample.get("burst") is not None

        snapshot = probe.get("snapshot", {})
        assert "maxDepth" in snapshot or snapshot.get("maxDepth") is not None
        assert "maxProps" in snapshot or snapshot.get("maxProps") is not None

    def test_probe_with_custom_sample_config(self):
        """Probes should allow custom sample config"""
        probe = EventCapture.make_tracepoint(
            lang="python",
            file="test.py",
            line=1,
            sample={"limitPerSecond": 5, "burst": 2}
        )

        assert probe["sample"]["limitPerSecond"] == 5
        assert probe["sample"]["burst"] == 2

    def test_probe_with_tags(self):
        """Probes should support tags"""
        probe = EventCapture.make_tracepoint(
            lang="python",
            file="test.py",
            line=1,
            tags=["performance", "critical"]
        )

        assert "performance" in probe.get("tags", [])
        assert "critical" in probe.get("tags", [])

    def test_filter_by_probe_id(self):
        """Filter should correctly match events by probe ID"""
        probe_id = "probe-123"
        event1 = {
            "probeId": probe_id,
            "type": "tracepoint.hit"
        }
        event2 = {
            "probeId": "probe-456",
            "type": "tracepoint.hit"
        }

        filter_fn = EventCapture.make_filter(probeId=probe_id)

        assert filter_fn(event1) is True
        assert filter_fn(event2) is False

    def test_filter_by_lang(self):
        """Filter should correctly match events by language"""
        event_py = {"lang": "python"}
        event_java = {"lang": "java"}
        event_node = {"lang": "node"}

        filter_fn = EventCapture.make_filter(lang="python")

        assert filter_fn(event_py) is True
        assert filter_fn(event_java) is False
        assert filter_fn(event_node) is False

    def test_filter_by_type(self):
        """Filter should correctly match events by type"""
        tracepoint = {"type": "tracepoint.hit"}
        logpoint = {"type": "logpoint.hit"}

        filter_fn = EventCapture.make_filter(event_type="tracepoint.hit")

        assert filter_fn(tracepoint) is True
        assert filter_fn(logpoint) is False

    def test_filter_by_location(self):
        """Filter should correctly match events by file/line location"""
        event_match = {
            "location": {
                "file": "test.py",
                "line": 42
            }
        }
        event_nomatch = {
            "location": {
                "file": "other.py",
                "line": 100
            }
        }

        filter_fn = EventCapture.make_filter(location={"file": "test.py", "line": 42})

        assert filter_fn(event_match) is True
        assert filter_fn(event_nomatch) is False

    def test_filter_by_tags(self):
        """Filter should correctly match events by tags"""
        event_with_tags = {"tags": ["critical", "perf"]}
        event_without_tags = {"tags": ["debug"]}

        filter_fn = EventCapture.make_filter(tags=["critical"])

        assert filter_fn(event_with_tags) is True
        assert filter_fn(event_without_tags) is False

    def test_filter_multiple_criteria(self):
        """Filter should support multiple criteria (AND logic)"""
        event_match = {
            "lang": "python",
            "type": "tracepoint.hit",
            "location": {"file": "test.py", "line": 1}
        }
        event_wrong_lang = {
            "lang": "java",
            "type": "tracepoint.hit",
            "location": {"file": "test.py", "line": 1}
        }

        filter_fn = EventCapture.make_filter(
            lang="python",
            event_type="tracepoint.hit",
            location={"file": "test.py", "line": 1}
        )

        assert filter_fn(event_match) is True
        assert filter_fn(event_wrong_lang) is False

    def test_filter_partial_matching(self):
        """Filter should support partial location matching"""
        event = {
            "location": {
                "file": "test.py",
                "line": 42,
                "className": "TestClass"
            }
        }

        # Filter by file only
        filter_fn = EventCapture.make_filter(location={"file": "test.py"})
        assert filter_fn(event) is True

        # Filter by line only
        filter_fn = EventCapture.make_filter(location={"line": 42})
        assert filter_fn(event) is True

    def test_probe_id_uniqueness(self):
        """Each probe should get a unique ID"""
        probe1 = EventCapture.make_tracepoint(lang="python", file="a.py", line=1)
        probe2 = EventCapture.make_tracepoint(lang="python", file="b.py", line=2)

        assert probe1["id"] != probe2["id"]

    def test_probe_config_dict_structure(self):
        """Probe should have expected canonical structure"""
        probe = EventCapture.make_tracepoint(
            lang="python",
            file="test.py",
            line=42,
            condition="x > 0"
        )

        # Should have these top-level keys
        required_keys = {"id", "file", "line", "sample", "snapshot", "tags"}
        assert required_keys.issubset(set(probe.keys()))

        # Sample and snapshot should have expected structure
        assert isinstance(probe["sample"], dict)
        assert isinstance(probe["snapshot"], dict)
        assert isinstance(probe["tags"], list)
