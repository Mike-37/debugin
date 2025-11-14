"""
Enhanced serialization utilities for snapshot handling.

Provides robust handling of:
- Circular references (with depth tracking)
- Non-serializable objects (file handles, coroutines, etc.)
- Large data structures (truncation and summarization)
"""

import sys
import io
import types
import inspect

# Types that cannot be serialized
NON_SERIALIZABLE_TYPES = (
    io.IOBase,  # File handles, pipes, etc.
    types.GeneratorType,  # Generators
    types.CoroutineType,  # Async coroutines
    types.AsyncGeneratorType,  # Async generators
)


class CircularReferenceTracker:
    """Tracks visited objects to detect and handle circular references."""

    def __init__(self, max_depth=3):
        self.max_depth = max_depth
        self.visited = set()
        self.depth = 0
        self.current_path = []

    def enter(self, obj_id):
        """Enter an object context. Returns True if circular ref detected."""
        if obj_id in self.visited:
            return True  # Circular reference
        self.visited.add(obj_id)
        self.depth += 1
        return False

    def exit(self, obj_id):
        """Exit object context."""
        if obj_id in self.visited:
            self.visited.discard(obj_id)
        self.depth -= 1

    def is_max_depth_reached(self):
        """Check if max depth exceeded."""
        return self.depth >= self.max_depth

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def is_non_serializable(obj):
    """Check if object is non-serializable."""
    # Check against known types
    if isinstance(obj, NON_SERIALIZABLE_TYPES):
        return True

    # Check for coroutines
    if inspect.iscoroutine(obj):
        return True
    if inspect.isgenerator(obj):
        return True

    # Check for file-like objects
    if hasattr(obj, 'read') or hasattr(obj, 'write'):
        if hasattr(obj, 'close'):  # Likely a file
            return True

    return False


def make_type_representation(obj):
    """Create a safe representation of a non-serializable object."""
    obj_type = type(obj).__name__
    obj_repr = repr(obj)

    # Truncate repr if too long
    if len(obj_repr) > 200:
        obj_repr = obj_repr[:197] + "..."

    return {
        "__tpd_type__": obj_type,
        "__repr__": obj_repr,
        "__serializable__": False
    }


def make_circular_reference_marker(depth_reached=False):
    """Create a marker for circular reference detection."""
    return {
        "__tpd_type__": "CircularReference",
        "__tpd_circular__": True,
        "__message__": "Circular reference detected (max depth reached)" if depth_reached
                      else "Circular reference detected"
    }


def safe_serialize_object(obj, tracker, max_properties=100):
    """
    Safely serialize an object, handling circular refs and non-serializable types.

    Args:
        obj: Object to serialize
        tracker: CircularReferenceTracker instance
        max_properties: Max properties to include in objects

    Returns:
        Serializable representation of object
    """
    # None
    if obj is None:
        return None

    # Primitives
    if isinstance(obj, (bool, int, float, str, bytes)):
        return obj

    # Check if non-serializable
    if is_non_serializable(obj):
        return make_type_representation(obj)

    # Check max depth
    if tracker.is_max_depth_reached():
        return make_type_representation(obj)

    obj_id = id(obj)

    # Check for circular reference
    if tracker.enter(obj_id):
        return make_circular_reference_marker()

    try:
        # Dict
        if isinstance(obj, dict):
            result = {}
            count = 0
            for key, value in obj.items():
                if count >= max_properties:
                    result["__tpd_truncated__"] = True
                    result["__tpd_remaining__"] = len(obj) - count
                    break
                try:
                    result[str(key)] = safe_serialize_object(value, tracker, max_properties)
                    count += 1
                except Exception as e:
                    result[str(key)] = f"<error serializing: {type(e).__name__}>"
            return result

        # List/tuple
        if isinstance(obj, (list, tuple)):
            result = []
            for idx, item in enumerate(obj):
                if idx >= max_properties:
                    result.append({
                        "__tpd_truncated__": True,
                        "__tpd_remaining__": len(obj) - idx
                    })
                    break
                try:
                    result.append(safe_serialize_object(item, tracker, max_properties))
                except Exception as e:
                    result.append(f"<error serializing: {type(e).__name__}>")
            return result if isinstance(obj, list) else tuple(result)

        # Set
        if isinstance(obj, set):
            result = []
            for idx, item in enumerate(obj):
                if idx >= max_properties:
                    result.append({
                        "__tpd_truncated__": True,
                        "__tpd_remaining__": len(obj) - idx
                    })
                    break
                try:
                    result.append(safe_serialize_object(item, tracker, max_properties))
                except Exception as e:
                    result.append(f"<error serializing: {type(e).__name__}>")
            return result

        # Custom objects with __dict__
        if hasattr(obj, '__dict__'):
            result = {}
            count = 0
            for key, value in obj.__dict__.items():
                if count >= max_properties:
                    result["__tpd_truncated__"] = True
                    result["__tpd_remaining__"] = len(obj.__dict__) - count
                    break
                try:
                    result[str(key)] = safe_serialize_object(value, tracker, max_properties)
                    count += 1
                except Exception as e:
                    result[str(key)] = f"<error serializing: {type(e).__name__}>"
            return result

        # Fallback: use repr
        return make_type_representation(obj)

    finally:
        tracker.exit(obj_id)
