"""
Test support module for DebugIn Event Sink.

Provides helpers for starting event sink in tests and capturing events
for assertions across all runtimes (Python, Java, Node.js).

Usage:
    with EventSink() as sink:
        # Your test code here
        events = sink.wait_for_events(
            event_type='probe.hit.snapshot',
            runtime='python',
            timeout=5.0
        )
        assert len(events) > 0
"""

import time
import queue
import threading
import requests
import logging
import uuid
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timezone
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class EventCapture:
    """Captures events from the event sink for testing."""

    def __init__(self, sink_url: str = 'http://127.0.0.1:4317'):
        """
        Initialize event capture.

        Args:
            sink_url: Base URL of the event sink (default: http://127.0.0.1:4317)
        """
        self.sink_url = sink_url.rstrip('/')
        self._events = []
        self._lock = threading.Lock()
        self._event_ready = threading.Event()

    def record_event(self, event: Dict[str, Any]) -> None:
        """Record an event (called by sink or test harness)."""
        with self._lock:
            self._events.append(event)
        self._event_ready.set()

    def get_all_events(self) -> List[Dict[str, Any]]:
        """Get all captured events."""
        with self._lock:
            return list(self._events)

    def get_events_by_type(self, event_type: str) -> List[Dict[str, Any]]:
        """Get events filtered by event type."""
        with self._lock:
            return [e for e in self._events if e.get('name') == event_type]

    def get_events_by_runtime(self, runtime: str) -> List[Dict[str, Any]]:
        """Get events filtered by runtime."""
        with self._lock:
            return [
                e for e in self._events
                if e.get('client', {}).get('runtime') == runtime
            ]

    def get_events_by_app(self, app_name: str) -> List[Dict[str, Any]]:
        """Get events filtered by application name."""
        with self._lock:
            return [
                e for e in self._events
                if e.get('client', {}).get('applicationName') == app_name
            ]

    def get_events_by_probe(self, probe_id: str) -> List[Dict[str, Any]]:
        """Get events filtered by probe ID."""
        with self._lock:
            return [
                e for e in self._events
                if e.get('payload', {}).get('probeId') == probe_id
            ]

    def wait_for_events(
        self,
        event_type: Optional[str] = None,
        runtime: Optional[str] = None,
        app_name: Optional[str] = None,
        probe_id: Optional[str] = None,
        count: int = 1,
        timeout: float = 5.0,
        predicate: Optional[Callable[[Dict[str, Any]], bool]] = None
    ) -> List[Dict[str, Any]]:
        """
        Wait for events matching criteria.

        Args:
            event_type: Filter by event type (e.g., 'probe.hit.snapshot')
            runtime: Filter by runtime ('python', 'java', 'node')
            app_name: Filter by application name
            probe_id: Filter by probe ID
            count: Minimum number of events to wait for
            timeout: Maximum time to wait in seconds
            predicate: Custom filter function

        Returns:
            List of matching events

        Raises:
            TimeoutError: If not enough events received within timeout
        """
        start_time = time.time()
        while True:
            # Collect matching events
            events = self.get_all_events()
            matching = events

            if event_type:
                matching = [e for e in matching if e.get('name') == event_type]
            if runtime:
                matching = [
                    e for e in matching
                    if e.get('client', {}).get('runtime') == runtime
                ]
            if app_name:
                matching = [
                    e for e in matching
                    if e.get('client', {}).get('applicationName') == app_name
                ]
            if probe_id:
                matching = [
                    e for e in matching
                    if e.get('payload', {}).get('probeId') == probe_id
                ]
            if predicate:
                matching = [e for e in matching if predicate(e)]

            # Check if we have enough events
            if len(matching) >= count:
                return matching

            # Check timeout
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                raise TimeoutError(
                    f"Timed out waiting for {count} events "
                    f"(event_type={event_type}, runtime={runtime}). "
                    f"Got {len(matching)} matching events out of {len(events)} total."
                )

            # Wait a bit before retrying
            time.sleep(0.1)

    def clear(self) -> int:
        """Clear all captured events. Returns count of cleared events."""
        with self._lock:
            count = len(self._events)
            self._events = []
        return count

    @staticmethod
    def make_tracepoint(
        lang: str,
        file: str,
        line: int,
        condition: Optional[str] = None,
        sample: Optional[Dict[str, Any]] = None,
        snapshot: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a canonical tracepoint probe configuration.

        Args:
            lang: Language ('python', 'java', 'node')
            file: Source file path
            line: Line number
            condition: Optional condition expression
            sample: Optional sample config (limitPerSecond, burst)
            snapshot: Optional snapshot config (maxDepth, maxProps, etc)
            tags: Optional list of tags

        Returns:
            Probe configuration dictionary
        """
        return {
            "id": f"probe-{uuid.uuid4().hex[:12]}",
            "file": file,
            "line": line,
            "condition": condition,
            "sample": sample or {"limitPerSecond": 10, "burst": 1},
            "snapshot": snapshot or {
                "maxDepth": 5,
                "maxProps": 50,
                "params": True,
                "fields": [],
                "locals": True
            },
            "tags": tags or []
        }

    @staticmethod
    def make_logpoint(
        lang: str,
        file: str,
        line: int,
        message: Optional[str] = None,
        condition: Optional[str] = None,
        sample: Optional[Dict[str, Any]] = None,
        snapshot: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a canonical logpoint probe configuration.

        Args:
            lang: Language ('python', 'java', 'node')
            file: Source file path
            line: Line number
            message: Log message template
            condition: Optional condition expression
            sample: Optional sample config
            snapshot: Optional snapshot config
            tags: Optional list of tags

        Returns:
            Probe configuration dictionary
        """
        probe = EventCapture.make_tracepoint(
            lang=lang,
            file=file,
            line=line,
            condition=condition,
            sample=sample,
            snapshot=snapshot,
            tags=tags
        )
        probe["message"] = message or f"Logpoint hit at {file}:{line}"
        return probe

    @staticmethod
    def make_filter(
        lang: Optional[str] = None,
        event_type: Optional[str] = None,
        probeId: Optional[str] = None,
        location: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> Callable[[Dict[str, Any]], bool]:
        """
        Create a filter function for events.

        Args:
            lang: Filter by language
            event_type: Filter by event type
            probeId: Filter by probe ID
            location: Filter by location (file, line, class, method)
            tags: Filter by tags (event must have all specified tags)

        Returns:
            Filter function that returns bool
        """
        def filter_fn(event: Dict[str, Any]) -> bool:
            if lang and event.get("lang") != lang:
                return False
            if event_type and event.get("type") != event_type:
                return False
            if probeId and event.get("probeId") != probeId:
                return False
            if tags:
                event_tags = event.get("tags", [])
                if not all(tag in event_tags for tag in tags):
                    return False
            if location:
                event_loc = event.get("location", {})
                for key, value in location.items():
                    if event_loc.get(key) != value:
                        return False
            return True

        return filter_fn


class EventSinkServer:
    """Manages the event sink server process for tests."""

    def __init__(
        self,
        host: str = '127.0.0.1',
        port: int = None,
        capture: Optional[EventCapture] = None
    ):
        """
        Initialize event sink server.

        Args:
            host: Server host
            port: Server port (None = auto-select free port)
            capture: Optional EventCapture to use instead of creating new one
        """
        self.host = host
        self.port = port or self._find_free_port()
        self.url = f'http://{host}:{self.port}'
        self.capture = capture or EventCapture(self.url)
        self._process = None
        self._started = False

    @staticmethod
    def _find_free_port() -> int:
        """Find a free port by binding to port 0."""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 0))
            return s.getsockname()[1]

    @property
    def events(self) -> List[Dict[str, Any]]:
        """Get all captured events."""
        return self.capture.get_all_events()

    def is_running(self) -> bool:
        """Check if event sink is running."""
        try:
            resp = requests.get(f'{self.url}/health', timeout=1.0)
            return resp.status_code == 200
        except (requests.RequestException, Exception):
            return False

    def start(self, timeout: float = 5.0) -> None:
        """
        Start the event sink server.

        Args:
            timeout: Maximum time to wait for server to start

        Raises:
            RuntimeError: If server fails to start
        """
        if self._started:
            return

        logger.info(f"Starting event sink on {self.host}:{self.port}")

        # Import here to avoid circular deps
        from scripts.event_sink import app

        # Start server in background thread
        def run_server():
            app.run(
                host=self.host,
                port=self.port,
                debug=False,
                use_reloader=False,
                threaded=True
            )

        self._process = threading.Thread(target=run_server, daemon=True)
        self._process.start()

        # Wait for server to start
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_running():
                self._started = True
                logger.info(f"Event sink started")
                return
            time.sleep(0.2)

        raise RuntimeError(
            f"Event sink failed to start on {self.host}:{self.port} "
            f"within {timeout} seconds"
        )

    def stop(self) -> None:
        """Stop the event sink server."""
        if not self._started:
            return
        logger.info("Stopping event sink")
        # Note: Thread-based server doesn't have a clean stop mechanism
        # This is expected for test servers; real deployments use proper servers
        self._started = False

    def clear_events(self) -> int:
        """Clear all captured events."""
        try:
            resp = requests.post(f'{self.url}/api/events/clear', timeout=5.0)
            if resp.status_code == 200:
                return resp.json().get('count', 0)
        except Exception as e:
            logger.warning(f"Failed to clear events via API: {e}")
        return self.capture.clear()

    def clear(self) -> int:
        """Clear all captured events (alias for clear_events)."""
        return self.clear_events()

    def wait_for(
        self,
        predicate: Callable[[Dict[str, Any]], bool],
        count: int = 1,
        timeout: float = 5.0
    ) -> List[Dict[str, Any]]:
        """
        Wait for events matching a predicate.

        Args:
            predicate: Filter function that returns bool
            count: Minimum number of matching events to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            List of matching events

        Raises:
            TimeoutError: If not enough events arrive within timeout
        """
        start_time = time.time()
        while True:
            matching = [e for e in self.events if predicate(e)]
            if len(matching) >= count:
                return matching

            elapsed = time.time() - start_time
            if elapsed >= timeout:
                raise TimeoutError(
                    f"Timeout waiting for {count} events matching predicate "
                    f"({elapsed:.1f}s > {timeout:.1f}s). Got {len(matching)} matching events."
                )

            time.sleep(0.1)

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


@contextmanager
def event_sink_fixture(
    host: str = '127.0.0.1',
    port: int = 4317
):
    """
    Context manager for event sink in tests.

    Usage:
        with event_sink_fixture() as sink:
            # Test code
            events = sink.wait_for_events(
                event_type='probe.hit.snapshot',
                timeout=5.0
            )

    Yields:
        EventSinkServer instance
    """
    sink = EventSinkServer(host=host, port=port)
    try:
        sink.start()
        yield sink
    finally:
        sink.stop()


def post_event_directly(
    event: Dict[str, Any],
    sink_url: str = 'http://127.0.0.1:4317',
    timeout: float = 5.0
) -> requests.Response:
    """
    Post an event directly to the sink (for testing).

    Args:
        event: Event object
        sink_url: Event sink base URL
        timeout: Request timeout

    Returns:
        Response object

    Raises:
        requests.RequestException: If request fails
    """
    resp = requests.post(
        f'{sink_url}/api/events',
        json=event,
        timeout=timeout
    )
    return resp


def construct_event(
    name: str,
    payload: Dict[str, Any],
    client: Optional[Dict[str, Any]] = None,
    timestamp: Optional[str] = None,
    event_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Construct a test event.

    Args:
        name: Event type (e.g., 'probe.hit.snapshot')
        payload: Event payload
        client: Client metadata (default: minimal valid metadata)
        timestamp: ISO 8601 timestamp (default: now)
        event_id: Event UUID (default: generate random)

    Returns:
        Event object ready to post to sink
    """
    import uuid

    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    if event_id is None:
        event_id = str(uuid.uuid4())

    if client is None:
        client = {
            'hostname': 'test-host',
            'applicationName': 'test-app',
            'applicationInstanceId': 'test-1',
            'agentVersion': '0.3.0',
            'runtime': 'python',
            'runtimeVersion': '3.11'
        }

    return {
        'name': name,
        'timestamp': timestamp,
        'id': event_id,
        'client': client,
        'payload': payload
    }
