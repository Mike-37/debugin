"""
Control API for Python TracepointDebug Agent

This module implements the HTTP control API that allows external tools
(like the Test Orchestrator Agent) to control the agent's behavior:

- Set/remove tracepoints and logpoints
- Enable/disable points by ID or tag
- Configure rate limits and other settings
- Query current state
"""
import json
import os
import sys
import threading
from flask import Flask, request, jsonify
from typing import Dict, Any, Optional
import uuid

from tracepointdebug.probe.breakpoints.tracepoint.trace_point_manager import TracePointManager
from tracepointdebug.probe.breakpoints.logpoint.log_point_manager import LogPointManager
from tracepointdebug.probe.tag_manager import TagManager
from tracepointdebug.config.config_provider import ConfigProvider
from tracepointdebug.probe.breakpoints.tracepoint.trace_point import TracePoint
from tracepointdebug.probe.breakpoints.logpoint.log_point import LogPoint
from tracepointdebug.probe.event.tracepoint.trace_point_snapshot_event import TracePointSnapshotEvent
from tracepointdebug.probe.event.logpoint.log_point_event import LogPointEvent
from tracepointdebug.probe.event.logpoint.put_logpoint_failed_event import PutLogPointFailedEvent
from tracepointdebug.probe.event.tracepoint.put_tracepoint_failed_event import PutTracePointFailedEvent

import logging
logger = logging.getLogger(__name__)


class ControlAPI:
    """HTTP Control API for the Python agent"""

    def __init__(self, port: int = 5001, host: str = "127.0.0.1"):
        self.port = port
        # Default to 127.0.0.1 for security, but allow override via environment
        # to bind to 0.0.0.0 if DEBUGIN_CONTROL_API_BIND_ALL is set
        if os.environ.get("DEBUGIN_CONTROL_API_BIND_ALL", "").lower() in ("1", "true", "yes"):
            self.host = "0.0.0.0"
        else:
            self.host = host
        self.app = Flask(__name__)

        # Don't initialize managers immediately - they require broker manager which isn't available yet
        self.tracepoint_manager = None
        self.logpoint_manager = None
        self.tag_manager = None
        self.config_provider = None

        # Dictionary to store point IDs for management
        self.point_ids: Dict[str, Dict[str, Any]] = {}

        self._setup_routes()
        self.server_thread = None
        self.running = False
        self.broker_manager = None
        self.engine = None
    
    def _setup_routes(self):
        """Setup API routes"""
        self.app.add_url_rule('/health', 'health', self.health, methods=['GET'])
        self.app.add_url_rule('/tracepoints', 'put_tracepoint', self.put_tracepoint, methods=['POST'])
        self.app.add_url_rule('/logpoints', 'put_logpoint', self.put_logpoint, methods=['POST'])
        self.app.add_url_rule('/tags/enable', 'enable_tags', self.enable_tags, methods=['POST'])
        self.app.add_url_rule('/tags/disable', 'disable_tags', self.disable_tags, methods=['POST'])
        self.app.add_url_rule('/points/enable', 'enable_point', self.enable_point, methods=['POST'])
        self.app.add_url_rule('/points/disable', 'disable_point', self.disable_point, methods=['POST'])
        self.app.add_url_rule('/points/remove', 'remove_point', self.remove_point, methods=['POST'])
        self.app.add_url_rule('/points', 'get_points', self.get_points, methods=['GET'])
        self.app.add_url_rule('/config', 'set_config', self.set_config, methods=['POST'])
    
    def health(self):
        """Health check endpoint"""
        try:
            # Check FT status
            import sysconfig
            py_gil_disabled = os.environ.get("Py_GIL_DISABLED", "0") if hasattr(os, 'environ') else "0"
            has_gil_check = hasattr(sys, '_is_gil_enabled')
            gil_enabled_now = sys._is_gil_enabled() if has_gil_check else True
            
            # Determine engine
            engine = "pytrace"  # Default
            if self.engine:
                from tracepointdebug.engine.native import NativeEngine
                if isinstance(self.engine, NativeEngine):
                    engine = "native"
            
            # Check sink status
            sink_status = "down"
            if self.broker_manager and self.broker_manager._client:
                import requests
                try:
                    # Try stats endpoint instead of health
                    response = requests.get(f"{self.broker_manager._client.base_url}/stats", timeout=1)
                    sink_status = "ok" if response.status_code == 200 else "down"
                except:
                    pass
            
            # Get version
            version = "unknown"
            try:
                from tracepointdebug import __version__
                version = __version__
            except:
                pass
            
            import platform
            return jsonify({
                "status": "healthy",
                "agent": {
                    "name": "tracepointdebug",
                    "version": version,
                    "runtime": "python",
                    "runtimeVersion": platform.python_version()
                },
                "features": {
                    "tracepoints": True,
                    "logpoints": True,
                    "conditions": True,
                    "rateLimit": True,
                    "freeThreaded": not gil_enabled_now
                },
                "broker": {
                    "connected": self.broker_manager is not None,
                    "url": "wss://broker.service.runsidekick.com:443" if self.broker_manager else "unknown"
                },
                "eventSink": {
                    "connected": sink_status == "ok",
                    "url": "http://127.0.0.1:4317"
                },
                "uptime": 0,
                "_debug": {
                    "py_gil_disabled": py_gil_disabled,
                    "has_gil_check": has_gil_check,
                    "gil_enabled_now": gil_enabled_now
                }
            })
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
    
    def _generate_point_id(self) -> str:
        """Generate a unique ID for a point"""
        return str(uuid.uuid4())
    
    def put_tracepoint(self):
        """Handle POST /tracepoints"""
        try:
            data = request.get_json(force=True, silent=True)
            if data is None:
                return jsonify({
                    "error": "Invalid JSON",
                    "code": "INVALID_JSON"
                }), 400

            # Validate required fields
            required_fields = ['file', 'line']
            for field in required_fields:
                if field not in data:
                    return jsonify({
                        "error": f"Missing required field: {field}",
                        "code": "MISSING_FIELD"
                    }), 400

            # Validate line number
            line_no = data.get('line')
            if not isinstance(line_no, int) or line_no < 1:
                return jsonify({
                    "error": "Invalid line number: line must be >= 1",
                    "code": "INVALID_LINE"
                }), 400
            
            # Create tracepoint configuration
            file_path = data['file']
            line_no = data['line']
            condition = data.get('condition', '')
            expire_hit_count = data.get('expire_hit_count', 0)
            expire_duration_ms = data.get('expire_duration_ms', 0)
            tags = data.get('tags', [])
            file_hash = data.get('file_hash', None)
            
            # Create a unique ID for this tracepoint
            point_id = self._generate_point_id()
            
            # Add to manager using correct method signature
            # Format: put_trace_point(self, trace_point_id, file, file_hash, line, client, expire_duration, expire_count,
            #                        enable_tracing, condition, tags)
            client = "control_api"
            if self.tracepoint_manager:
                self.tracepoint_manager.put_trace_point(
                    trace_point_id=point_id,
                    file=file_path,
                    file_hash=file_hash,
                    line=line_no,
                    client=client,
                    expire_duration=expire_duration_ms,
                    expire_count=expire_hit_count,
                    enable_tracing=True,  # Enable tracing by default
                    condition=condition,
                    tags=tags
                )
            
            # Store the point ID for later management
            self.point_ids[point_id] = {
                "type": "tracepoint",
                "config": data
            }

            return jsonify({
                "id": point_id,
                "type": "tracepoint",
                "file": file_path,
                "line": line_no,
                "enabled": True,
                "created": "now",
                "condition": data.get('condition')
            }), 201
        except Exception as e:
            logger.exception("Error creating tracepoint")
            return jsonify({
                "error": f"Failed to create tracepoint: {str(e)}",
                "code": "TRACEPOINT_CREATE_ERROR"
            }), 500
    
    def put_logpoint(self):
        """Handle POST /logpoints"""
        try:
            data = request.get_json()
            
            # Validate required fields
            required_fields = ['file', 'line', 'log_expression']
            for field in required_fields:
                if field not in data:
                    return jsonify({
                        "ok": False,
                        "error": f"Missing required field: {field}"
                    }), 400
            
            # Extract parameters
            file_path = data['file']
            line_no = data['line']
            log_expression = data['log_expression']
            level = data.get('level', 'INFO')
            stdout_enabled = data.get('stdout_enabled', True)
            condition = data.get('condition', '')
            expire_hit_count = data.get('expire_hit_count', 0)
            expire_duration_ms = data.get('expire_duration_ms', 0)
            tags = data.get('tags', [])
            
            # Create a unique ID for this logpoint
            point_id = self._generate_point_id()
            
            # Add to manager using correct method signature
            # Format: put_log_point(self, log_point_id, file, file_hash, line, client, expire_duration, expire_count,
            #                      disabled, log_expression, condition, log_level, stdout_enabled, tags)
            client = "control_api"
            if self.logpoint_manager:
                self.logpoint_manager.put_log_point(
                    log_point_id=point_id,
                    file=file_path,
                    file_hash=None,  # Not provided in the request
                    line=line_no,
                    client=client,
                    expire_duration=expire_duration_ms,
                    expire_count=expire_hit_count,
                    disabled=False,  # Enable by default
                    log_expression=log_expression,
                    condition=condition,
                    log_level=level,
                    stdout_enabled=stdout_enabled,
                    tags=tags
                )
            
            # Store the point ID for later management
            self.point_ids[point_id] = {
                "type": "logpoint",
                "config": data
            }
            
            return jsonify({
                "ok": True,
                "id": point_id
            })
        except Exception as e:
            return jsonify({
                "ok": False,
                "error": f"Exception occurred: {str(e)}"
            }), 500
    
    def enable_tags(self):
        """Handle POST /tags/enable"""
        try:
            data = request.get_json()
            if 'tags' not in data:
                return jsonify({
                    "ok": False,
                    "error": "Missing 'tags' field"
                }), 400
            
            tags = data['tags']
            client = "control_api"
            # Call enable on both tracepoint and logpoint managers
            if self.tracepoint_manager:
                self.tracepoint_manager.enable_tag(tags, client)
            if self.logpoint_manager:
                self.logpoint_manager.enable_tag(tags, client)
            
            return jsonify({
                "ok": True
            })
        except Exception as e:
            return jsonify({
                "ok": False,
                "error": f"Exception occurred: {str(e)}"
            }), 500
    
    def disable_tags(self):
        """Handle POST /tags/disable"""
        try:
            data = request.get_json()
            if 'tags' not in data:
                return jsonify({
                    "ok": False,
                    "error": "Missing 'tags' field"
                }), 400

            tags = data['tags']
            client = "control_api"

            # Call disable on both tracepoint and logpoint managers
            # This matches the behavior of enable_tags
            if self.tracepoint_manager:
                self.tracepoint_manager.disable_tag(tags, client)
            if self.logpoint_manager:
                self.logpoint_manager.disable_tag(tags, client)

            return jsonify({
                "ok": True
            })
        except Exception as e:
            logger.exception("tags_disable failed")
            return jsonify({
                "ok": False,
                "error": f"Exception occurred: {str(e)}"
            }), 500
    
    def enable_point(self):
        """Handle POST /points/enable"""
        try:
            data = request.get_json()
            if 'id' not in data:
                return jsonify({
                    "ok": False,
                    "error": "Missing 'id' field"
                }), 400
            
            point_id = data['id']
            if point_id not in self.point_ids:
                return jsonify({
                    "ok": False,
                    "error": f"Point with ID {point_id} not found"
                }), 404
            
            point_info = self.point_ids[point_id]
            
            client = "control_api"
            if point_info['type'] == 'tracepoint' and self.tracepoint_manager:
                # Enable tracepoint
                self.tracepoint_manager.enable_trace_point(point_id, client)
            elif point_info['type'] == 'logpoint' and self.logpoint_manager:
                # Enable logpoint
                self.logpoint_manager.enable_log_point(point_id, client)
            
            return jsonify({
                "ok": True
            })
        except Exception as e:
            return jsonify({
                "ok": False,
                "error": f"Exception occurred: {str(e)}"
            }), 500
    
    def disable_point(self):
        """Handle POST /points/disable"""
        try:
            data = request.get_json()
            if 'id' not in data:
                return jsonify({
                    "ok": False,
                    "error": "Missing 'id' field"
                }), 400
            
            point_id = data['id']
            if point_id not in self.point_ids:
                return jsonify({
                    "ok": False,
                    "error": f"Point with ID {point_id} not found"
                }), 404
            
            point_info = self.point_ids[point_id]
            
            client = "control_api"
            if point_info['type'] == 'tracepoint' and self.tracepoint_manager:
                # Disable tracepoint
                self.tracepoint_manager.disable_trace_point(point_id, client)
            elif point_info['type'] == 'logpoint' and self.logpoint_manager:
                # Disable logpoint
                self.logpoint_manager.disable_log_point(point_id, client)
            
            return jsonify({
                "ok": True
            })
        except Exception as e:
            return jsonify({
                "ok": False,
                "error": f"Exception occurred: {str(e)}"
            }), 500
    
    def remove_point(self):
        """Handle POST /points/remove"""
        try:
            data = request.get_json()
            if 'id' not in data:
                return jsonify({
                    "ok": False,
                    "error": "Missing 'id' field"
                }), 400
            
            point_id = data['id']
            if point_id not in self.point_ids:
                return jsonify({
                    "ok": False,
                    "error": f"Point with ID {point_id} not found"
                }), 404
            
            point_info = self.point_ids[point_id]
            
            client = "control_api"
            if point_info['type'] == 'tracepoint' and self.tracepoint_manager:
                # Remove tracepoint
                self.tracepoint_manager.remove_trace_point(point_id, client)
            elif point_info['type'] == 'logpoint' and self.logpoint_manager:
                # Remove logpoint
                self.logpoint_manager.remove_log_point(point_id, client)
            
            # Remove from our ID tracking
            del self.point_ids[point_id]
            
            return jsonify({
                "ok": True
            })
        except Exception as e:
            return jsonify({
                "ok": False,
                "error": f"Exception occurred: {str(e)}"
            }), 500
    
    def get_points(self):
        """Handle GET /points"""
        try:
            # Use default client for listing
            client = "control_api"
            
            # Get all active points from managers
            tracepoints = []
            logpoints = []
            
            if self.tracepoint_manager:
                try:
                    # Try different signatures for list_trace_points
                    if hasattr(self.tracepoint_manager, 'list_trace_points'):
                        try:
                            # Try with just client parameter
                            tracepoints = self.tracepoint_manager.list_trace_points(client=client)
                        except TypeError:
                            # Try without client parameter
                            tracepoints = self.tracepoint_manager.list_trace_points()
                    
                    # Filter out disabled tracepoints
                    tracepoints = [tp for tp in tracepoints if not getattr(tp, 'disabled', True)]
                except Exception as e:
                    print(f"Error listing tracepoints: {e}")
                    
            if self.logpoint_manager:
                try:
                    # Try different signatures for list_log_points
                    if hasattr(self.logpoint_manager, 'list_log_points'):
                        try:
                            # Try with just client parameter
                            logpoints = self.logpoint_manager.list_log_points(client=client)
                        except TypeError:
                            # Try without client parameter
                            logpoints = self.logpoint_manager.list_log_points()
                    
                    # Filter out disabled logpoints
                    logpoints = [lp for lp in logpoints if not getattr(lp, 'disabled', True)]
                except Exception as e:
                    print(f"Error listing logpoints: {e}")
            
            points = []
            
            # Format tracepoints
            for tp in tracepoints:
                points.append({
                    "id": getattr(tp, 'trace_point_id', 'unknown'),
                    "type": "tracepoint",
                    "file": getattr(tp, 'file', 'unknown'),
                    "line": getattr(tp, 'line', 0),
                    "enabled": not getattr(tp, 'disabled', True),
                    "tags": getattr(tp, 'tags', []),
                    "condition": getattr(tp, 'condition', '')
                })
            
            # Format logpoints
            for lp in logpoints:
                points.append({
                    "id": getattr(lp, 'log_point_id', 'unknown'),
                    "type": "logpoint",
                    "file": getattr(lp, 'file', 'unknown'),
                    "line": getattr(lp, 'line', 0),
                    "enabled": not getattr(lp, 'disabled', True),
                    "tags": getattr(lp, 'tags', []),
                    "log_expression": getattr(lp, 'log_expression', '')
                })
            
            # Add any points we're tracking manually
            for point_id, point_info in self.point_ids.items():
                if not any(p['id'] == point_id for p in points):
                    points.append({
                        "id": point_id,
                        "type": point_info['type'],
                        "file": point_info['config'].get('file', 'unknown'),
                        "line": point_info['config'].get('line', 0),
                        "enabled": True,
                        "tags": point_info['config'].get('tags', []),
                        "condition": point_info['config'].get('condition', ''),
                        "log_expression": point_info['config'].get('log_expression', '')
                    })
            
            return jsonify({
                "ok": True,
                "points": points
            })
        except Exception as e:
            return jsonify({
                "ok": False,
                "error": f"Exception occurred: {str(e)}"
            }), 500
    
    def set_config(self):
        """Handle POST /config"""
        try:
            data = request.get_json()
            
            # Update configuration based on provided data
            if self.config_provider:
                for key, value in data.items():
                    self.config_provider.set(key, value)
            
            return jsonify({
                "ok": True
            })
        except Exception as e:
            return jsonify({
                "ok": False,
                "error": f"Exception occurred: {str(e)}"
            }), 500
    
    def start(self):
        """Start the control API server in a separate thread"""
        if self.running:
            return
        
        def run_server():
            self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False)
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        self.running = True
        # Initialize managers after the server thread starts, when we have access to the broker manager
        from tracepointdebug.broker.broker_manager import BrokerManager
        from tracepointdebug.probe.dynamicConfig.dynamic_config_manager import DynamicConfigManager
        from tracepointdebug.engine.selector import get_engine
        
        # Get the broker manager instance
        try:
            self.broker_manager = BrokerManager.instance()
            
            # Get the engine
            self.engine = get_engine()
            
            # Initialize managers with required parameters
            from tracepointdebug.probe.breakpoints.tracepoint.trace_point_manager import TracePointManager
            from tracepointdebug.probe.breakpoints.logpoint.log_point_manager import LogPointManager
            from tracepointdebug.probe.tag_manager import TagManager
            from tracepointdebug.config.config_provider import ConfigProvider
            
            self.tracepoint_manager = TracePointManager(broker_manager=self.broker_manager, data_redaction_callback=None, engine=self.engine)
            self.logpoint_manager = LogPointManager(broker_manager=self.broker_manager, data_redaction_callback=None, engine=self.engine)
            self.tag_manager = TagManager.instance()
            self.config_provider = ConfigProvider()
        except Exception as e:
            print(f"Error initializing managers: {e}")
        
        print(f"Control API server started on {self.host}:{self.port}")
    
    def stop(self):
        """Stop the control API server"""
        if self.running and self.server_thread:
            # Flask doesn't have a clean shutdown method, so we'll just set the flag
            self.running = False
            print("Control API server stopped")


# Global instance for the control API
control_api: Optional[ControlAPI] = None


def start_control_api(port: int = 5001, host: str = "127.0.0.1", broker_manager=None, engine=None):
    """Start the control API server

    Args:
        port: Port to bind to (default: 5001)
        host: Host to bind to (default: 127.0.0.1 for localhost only)
              Set DEBUGIN_CONTROL_API_BIND_ALL=1 to bind to 0.0.0.0 for remote access
        broker_manager: BrokerManager instance
        engine: Trace engine instance
    """
    global control_api
    if control_api is None:
        control_api = ControlAPI(port=port, host=host)
        # Store broker manager and engine for later use when server starts
        control_api.broker_manager = broker_manager
        control_api.engine = engine
        control_api.start()
    return control_api


def stop_control_api():
    """Stop the control API server"""
    global control_api
    if control_api:
        control_api.stop()
        control_api = None


# The auto-start functionality will be handled from the main start function
# to ensure all required components are properly initialized