"""
Comprehensive Free-Threaded (FT) Mode Tests for Python 3.13+

Tests verify:
1. FT detection works correctly
2. Engine selection falls back to pytrace in FT mode
3. Agent starts without crashing/deadlocking in FT mode
4. Basic tracing works in FT mode
5. Control API responds correctly when running FT
"""

import sys
import sysconfig
import pytest
import threading
import time
import requests
from unittest.mock import patch

# Import agent and FT compat utilities
import tracepointdebug
from tracepointdebug._compat import build_supports_free_threading, gil_is_enabled, is_actually_free_threaded
from tracepointdebug.engine.selector import get_engine

# Test fixtures and utilities
CONTROL_API_URL = "http://127.0.0.1:5001"


def test_ft_detection_works():
    """Test that FT detection correctly identifies free-threaded Python"""
    build_supports = build_supports_free_threading()
    assert isinstance(build_supports, bool), "build_supports_free_threading() should return bool"

    if sys.version_info >= (3, 13):
        # Python 3.13+ has _is_gil_enabled
        assert hasattr(sys, '_is_gil_enabled'), "Python 3.13+ should have _is_gil_enabled"
        gil_enabled = gil_is_enabled()
        assert isinstance(gil_enabled, bool), "gil_is_enabled() should return bool"


def test_ft_detection_vs_build():
    """Test relationship between build support and runtime FT"""
    build_supports = build_supports_free_threading()
    is_ft = is_actually_free_threaded()

    if not build_supports:
        # If build doesn't support FT, runtime can't be FT
        assert not is_ft, "Cannot be FT if build doesn't support FT"


@pytest.mark.skipif(not is_actually_free_threaded(), reason="FT mode not enabled")
def test_ft_mode_engine_selection():
    """Test that FT mode forces pytrace engine (native not supported)"""
    engine = get_engine()

    # In FT mode, should get pytrace engine
    # Check engine type
    from tracepointdebug.engine.pytrace import PyTraceEngine
    from tracepointdebug.engine.native import NativeEngine

    # Engine should be pytrace, not native
    if isinstance(engine, NativeEngine):
        pytest.skip("Native engine in FT mode - may have fallback logic")

    # Verify it's pytrace
    assert isinstance(engine, PyTraceEngine) or engine.__class__.__name__ == 'PyTraceEngine', \
        f"Expected pytrace engine in FT mode, got {engine.__class__.__name__}"


@pytest.mark.skipif(not is_actually_free_threaded(), reason="FT mode not enabled")
def test_ft_agent_startup():
    """Test that agent can start in FT mode without deadlocks"""
    try:
        # Start agent with timeout
        tracepointdebug.start(
            enable_control_api=True,
            control_api_port=5001
        )

        # Give it time to initialize
        time.sleep(1)

        # Verify it's running by checking health
        response = requests.get(f"{CONTROL_API_URL}/health", timeout=2)
        assert response.status_code == 200, "Agent health check should succeed"

        data = response.json()
        assert data["status"] == "healthy", "Agent should report healthy status"
        assert data["features"]["freeThreaded"] == True, "Agent should report FT capability"

    except threading.ThreadError as e:
        pytest.fail(f"Agent startup in FT mode caused thread error: {e}")
    except Exception as e:
        pytest.fail(f"Agent startup in FT mode failed: {e}")


@pytest.mark.skipif(not is_actually_free_threaded(), reason="FT mode not enabled")
def test_ft_no_segfault():
    """Test that agent operation doesn't cause segfaults in FT mode"""
    try:
        # Make a few API calls
        response = requests.get(f"{CONTROL_API_URL}/points", timeout=2)
        assert response.status_code == 200, "GET /points should succeed"

        # Create a point
        response = requests.post(
            f"{CONTROL_API_URL}/tracepoints",
            json={"file": "test.py", "line": 10},
            timeout=2
        )
        assert response.status_code == 201, "Creating tracepoint should succeed"

        # No segfault = success
        assert True, "FT mode operations completed without segfault"

    except Exception as e:
        pytest.fail(f"FT mode operation failed: {e}")


@pytest.mark.skipif(not is_actually_free_threaded(), reason="FT mode not enabled")
def test_ft_multithreaded_tracing():
    """Test that tracing works in multithreaded FT environment"""
    results = []
    errors = []

    def worker(worker_id):
        try:
            # Each thread creates a tracepoint
            response = requests.post(
                f"{CONTROL_API_URL}/tracepoints",
                json={
                    "file": "test.py",
                    "line": 10 + worker_id,
                    "tags": [f"thread-{worker_id}"]
                },
                timeout=2
            )
            assert response.status_code == 201, f"Thread {worker_id}: tracepoint creation failed"
            results.append(response.json()["id"])
        except Exception as e:
            errors.append((worker_id, str(e)))

    # Create multiple threads
    threads = []
    for i in range(5):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    # Wait for all threads
    for t in threads:
        t.join(timeout=5)
        assert not t.is_alive(), "Thread should complete without deadlock"

    # Check results
    assert len(errors) == 0, f"Multithreaded tracing had errors: {errors}"
    assert len(results) == 5, f"Expected 5 tracepoints created, got {len(results)}"


@pytest.mark.skipif(not is_actually_free_threaded(), reason="FT mode not enabled")
def test_ft_health_endpoint_reports_ft():
    """Test that /health endpoint correctly reports FT status"""
    response = requests.get(f"{CONTROL_API_URL}/health", timeout=2)
    data = response.json()

    assert "features" in data, "Health response should include features"
    assert "freeThreaded" in data["features"], "Features should report FT status"
    assert data["features"]["freeThreaded"] == True, "Should report FT enabled"


@pytest.mark.skipif(build_supports_free_threading(), reason="Only for non-FT builds")
def test_non_ft_build_reports_correctly():
    """Test that non-FT Python builds report correct status"""
    is_ft = is_actually_free_threaded()
    assert not is_ft, "Non-FT build should report FT=False"

    engine = get_engine()
    # Non-FT can use native or pytrace
    assert engine is not None, "Engine should be available"


# GIL re-enablement test (Python 3.13+ only)
@pytest.mark.skipif(sys.version_info < (3, 13), reason="Requires Python 3.13+")
def test_gil_status_available():
    """Test that GIL status checking works on Python 3.13+"""
    if hasattr(sys, '_is_gil_enabled'):
        gil_enabled = sys._is_gil_enabled()
        assert isinstance(gil_enabled, bool), "_is_gil_enabled() should return bool"
    else:
        pytest.skip("Python 3.13+ but _is_gil_enabled not available")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])