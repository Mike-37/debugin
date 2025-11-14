#!/usr/bin/env python3
"""
DebugIn Event Sink Server

A reference implementation of the Event Sink that receives, validates, and logs
events from all DebugIn agents (Python, Java, Node.js).

Implements the canonical Event Schema specified in docs/event-schema.md.

HTTP Endpoints:
  - POST /api/events     - Accept an event
  - GET /health          - Health check

Usage:
  python scripts/event_sink.py [--host 127.0.0.1] [--port 4317]

Environment Variables:
  - EVENT_SINK_HOST      - Server host (default: 127.0.0.1)
  - EVENT_SINK_PORT      - Server port (default: 4317)
  - EVENT_SINK_DEBUG     - Enable debug logging (default: false)
"""

import json
import sys
import uuid
import logging
import argparse
from datetime import datetime, timezone
from typing import Any, Dict, Tuple, Optional
from pathlib import Path

try:
    from flask import Flask, request, jsonify
except ImportError:
    print("Error: Flask is required. Install with: pip install flask")
    sys.exit(1)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('event_sink')

app = Flask(__name__)

# In-memory event storage (for testing/debugging)
_events_received = []


class EventValidator:
    """Validates events against the DebugIn Event Schema."""

    # Required fields in base event
    REQUIRED_BASE_FIELDS = {'name', 'timestamp', 'id', 'client', 'payload'}

    # Required fields in client object
    REQUIRED_CLIENT_FIELDS = {
        'hostname', 'applicationName', 'agentVersion', 'runtime', 'runtimeVersion'
    }

    # Valid event types
    VALID_EVENT_TYPES = {
        'probe.hit.snapshot',
        'probe.hit.logpoint',
        'probe.error.condition',
        'probe.error.snapshot',
        'probe.error.rateLimit',
        'agent.status.started',
        'agent.status.stopped',
    }

    # Required payload fields per event type
    PAYLOAD_REQUIREMENTS = {
        'probe.hit.snapshot': {
            'required': {'probeId', 'probeType', 'file', 'line'},
            'optional': {'method', 'className', 'condition', 'conditionEvaluated',
                        'snapshot', 'stack', 'hitCount', 'totalHits', 'rateLimit'}
        },
        'probe.hit.logpoint': {
            'required': {'probeId', 'probeType', 'file', 'line', 'message'},
            'optional': {'method', 'className', 'condition', 'conditionEvaluated',
                        'conditionResult', 'messageTemplate', 'hitCount', 'totalHits', 'rateLimit'}
        },
        'probe.error.condition': {
            'required': {'probeId', 'probeType', 'file', 'line', 'condition', 'error'},
            'optional': {'errorType', 'errorStack'}
        },
        'probe.error.snapshot': {
            'required': {'probeId', 'probeType', 'file', 'line', 'error'},
            'optional': {'errorType', 'failedVariable', 'attemptedValue'}
        },
        'probe.error.rateLimit': {
            'required': {'probeId', 'probeType', 'file', 'line', 'message'},
            'optional': {'limit', 'droppedCount'}
        },
        'agent.status.started': {
            'required': {'message'},
            'optional': {'engine', 'features'}
        },
        'agent.status.stopped': {
            'required': {'message'},
            'optional': {'uptime', 'totalProbes', 'totalEvents'}
        },
    }

    @classmethod
    def validate(cls, event: Any) -> Tuple[bool, Optional[str]]:
        """
        Validate an event against the schema.

        Returns:
            (is_valid, error_message)
        """
        if not isinstance(event, dict):
            return False, "Event must be a JSON object"

        # Check base fields
        missing = cls.REQUIRED_BASE_FIELDS - set(event.keys())
        if missing:
            return False, f"Missing required fields: {', '.join(sorted(missing))}"

        # Validate event name
        event_name = event.get('name')
        if event_name not in cls.VALID_EVENT_TYPES:
            return False, f"Invalid event type '{event_name}'. Valid types: {', '.join(sorted(cls.VALID_EVENT_TYPES))}"

        # Validate timestamp format (ISO 8601)
        timestamp = event.get('timestamp')
        try:
            # Try to parse as ISO 8601
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except (AttributeError, ValueError):
            return False, f"Invalid timestamp format: '{timestamp}' (must be ISO 8601)"

        # Validate event ID (UUID format)
        event_id = event.get('id')
        try:
            uuid.UUID(event_id)
        except (ValueError, AttributeError, TypeError):
            return False, f"Invalid event ID: '{event_id}' (must be UUID v4)"

        # Validate client object
        client = event.get('client')
        if not isinstance(client, dict):
            return False, "Client must be a JSON object"

        missing_client = cls.REQUIRED_CLIENT_FIELDS - set(client.keys())
        if missing_client:
            return False, f"Missing required client fields: {', '.join(sorted(missing_client))}"

        # Validate runtime field
        runtime = client.get('runtime')
        if runtime not in {'python', 'java', 'node'}:
            return False, f"Invalid runtime '{runtime}'. Must be one of: python, java, node"

        # Validate payload structure
        payload = event.get('payload')
        if not isinstance(payload, dict):
            return False, "Payload must be a JSON object"

        # Check payload requirements based on event type
        requirements = cls.PAYLOAD_REQUIREMENTS.get(event_name)
        if requirements:
            missing_payload = requirements['required'] - set(payload.keys())
            if missing_payload:
                return False, f"Missing required payload fields for {event_name}: {', '.join(sorted(missing_payload))}"

        return True, None


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'debugin-event-sink',
        'events_received': len(_events_received),
        'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    }), 200


@app.route('/api/events', methods=['POST'])
def receive_event():
    """
    Receive and validate an event.

    POST /api/events
    Content-Type: application/json

    Body: { event object conforming to schema }

    Returns:
        200: Event accepted
        400: Invalid event format
        500: Server error
    """
    # Parse JSON
    try:
        event = request.get_json(force=True)
    except Exception as e:
        logger.warning(f"Failed to parse JSON: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Invalid JSON format',
            'error': str(e)
        }), 400

    # Validate event
    is_valid, error_msg = EventValidator.validate(event)
    if not is_valid:
        logger.warning(f"Invalid event: {error_msg}")
        return jsonify({
            'status': 'error',
            'message': 'Invalid event format',
            'error': error_msg
        }), 400

    # Store event (for testing/debugging)
    event_id = event.get('id')
    event_name = event.get('name')
    _events_received.append(event)

    # Log event
    runtime = event.get('client', {}).get('runtime', 'unknown')
    app_name = event.get('client', {}).get('applicationName', 'unknown')
    logger.info(f"✓ Event accepted: {event_name} (id={event_id}, runtime={runtime}, app={app_name})")

    # Return success response
    return jsonify({
        'status': 'accepted',
        'id': event_id,
        'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    }), 200


@app.route('/api/events', methods=['GET'])
def list_events():
    """
    List received events (debug endpoint).

    Query Parameters:
      - runtime: Filter by runtime (python, java, node)
      - event_type: Filter by event type
      - limit: Max events to return (default: 100)
      - offset: Offset for pagination (default: 0)

    Returns:
        200: JSON array of events
    """
    runtime_filter = request.args.get('runtime')
    event_type_filter = request.args.get('event_type')
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))

    # Filter events
    filtered = _events_received
    if runtime_filter:
        filtered = [e for e in filtered if e.get('client', {}).get('runtime') == runtime_filter]
    if event_type_filter:
        filtered = [e for e in filtered if e.get('name') == event_type_filter]

    # Apply pagination
    total = len(filtered)
    events = filtered[offset:offset + limit]

    return jsonify({
        'total': total,
        'offset': offset,
        'limit': limit,
        'count': len(events),
        'events': events
    }), 200


@app.route('/api/events/clear', methods=['POST'])
def clear_events():
    """
    Clear all stored events (for testing).

    POST /api/events/clear

    Returns:
        200: Events cleared
    """
    global _events_received
    count = len(_events_received)
    _events_received = []
    logger.info(f"Cleared {count} stored events")
    return jsonify({
        'status': 'cleared',
        'count': count
    }), 200


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({
        'status': 'error',
        'message': 'Endpoint not found',
        'path': request.path
    }), 404


@app.errorhandler(405)
def method_not_allowed(error):
    """Handle 405 errors."""
    return jsonify({
        'status': 'error',
        'message': 'Method not allowed',
        'method': request.method,
        'path': request.path
    }), 405


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'status': 'error',
        'message': 'Internal server error'
    }), 500


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(
        description='DebugIn Event Sink - receives and validates debugger events'
    )
    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='Server host (default: 127.0.0.1)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=4317,
        help='Server port (default: 4317)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=1,
        help='Number of workers (default: 1)'
    )

    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)
        app.logger.setLevel(logging.DEBUG)

    logger.info(f"Starting DebugIn Event Sink on {args.host}:{args.port}")
    logger.info(f"Event schema: docs/event-schema.md")
    logger.info(f"Health check: GET http://{args.host}:{args.port}/health")
    logger.info(f"POST events: POST http://{args.host}:{args.port}/api/events")

    try:
        app.run(
            host=args.host,
            port=args.port,
            debug=args.debug,
            use_reloader=False,
            threaded=True
        )
    except KeyboardInterrupt:
        logger.info("Event Sink shutting down")
        sys.exit(0)


if __name__ == '__main__':
    main()
