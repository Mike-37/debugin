import datetime
import itertools
import os
import sys
import types
import logging

import six

from .snapshot import Snapshot
from .value import Value
from .variable import Variable
from .variables import Variables
from .snapshot_collector_config_manager import SnapshotCollectorConfigManager
from .serialization import CircularReferenceTracker, safe_serialize_object, is_non_serializable
from tracepointdebug.probe.frame import Frame

logger = logging.getLogger(__name__)

_PRIMITIVE_TYPES = (type(None), float, complex, bool, slice, bytearray,
                    six.text_type,
                    six.binary_type) + six.integer_types + six.string_types
_TEXT_TYPES = (six.string_types, six.text_type)
_DATE_TYPES = (datetime.date, datetime.time, datetime.timedelta)
_VECTOR_TYPES = (tuple, list, set)


class SnapshotCollector(object):
    def __init__(self):
        self.cur_size = 0
        self.tracker = CircularReferenceTracker(max_depth=SnapshotCollectorConfigManager.get_parse_depth())

    def collect(self, top_frame):
        frame = top_frame
        collected_frames = []
        # Reset tracker for new collection
        self.tracker = CircularReferenceTracker(max_depth=SnapshotCollectorConfigManager.get_parse_depth())

        while frame and len(collected_frames) < SnapshotCollectorConfigManager.get_max_frames():
            code = frame.f_code
            file_path = normalize_path(code.co_filename)
            if len(collected_frames) < SnapshotCollectorConfigManager.get_max_expand_frames():
                collected_frames.append(
                    Frame(frame.f_lineno, self.collect_frame_locals(frame=frame), file_path, code.co_name))
            else:
                collected_frames.append(Frame(frame.f_lineno, Variables([]), file_path, code.co_name))
            frame = frame.f_back

        top_frame_method_name = top_frame.f_code.co_name
        file = top_frame.f_code.co_filename
        snapshot = Snapshot(frames=collected_frames, method_name=top_frame_method_name, file=file)
        return snapshot

    def collect_frame_locals(self, frame):
        frame_locals = frame.f_locals
        variables = []
        for name, value in six.viewitems(frame_locals):
            try:
                # Use enhanced serialization for robustness
                if is_non_serializable(value):
                    # Use safe_serialize_object for non-serializable types
                    val = Value(var_type=type(value).__name__,
                              value=safe_serialize_object(value, self.tracker))
                else:
                    val = self.collect_variable_value(value, 0, SnapshotCollectorConfigManager.get_parse_depth())

                if val is not None and type(value).__name__.find("byte") == -1:
                    variables.append(Variable(name, type(value).__name__, val))
                if len(variables) > SnapshotCollectorConfigManager.get_max_properties():
                    break
            except Exception as e:
                logger.warning(f"Error collecting variable '{name}': {e}")
                # Skip problematic variable
                continue
        return Variables(variables)

    def collect_variable_value(self, variable, depth, max_depth):
        if depth >= max_depth:
            return None

        if self.cur_size >= SnapshotCollectorConfigManager.get_max_size():
            return None

        if variable is None:
            self.cur_size += 4
            return Value(var_type=type(None).__name__, value=None)

        if isinstance(variable, _PRIMITIVE_TYPES):
            if isinstance(variable, _TEXT_TYPES):
                r = _trim_string(variable, SnapshotCollectorConfigManager.get_max_var_len())
            else:
                r = variable
            self.cur_size += len(repr(r))
            return Value(var_type=type(variable).__name__, value=r)

        if isinstance(variable, _DATE_TYPES):
            r = str(variable)
            self.cur_size += len(r)
            return Value(var_type=type(variable).__name__, value=r)

        if isinstance(variable, dict):
            items = [(k, v) for (k, v) in variable.items()]
            r = {}
            for name, value in items:
                if self.cur_size >= SnapshotCollectorConfigManager.get_max_size():
                    break
                val = self.collect_variable_value(value, depth + 1, max_depth)
                if val is not None:
                    r[str(name)] = val
                    self.cur_size += len(repr(name))
            return Value(var_type=type(variable).__name__, value=r)

        if isinstance(variable, _VECTOR_TYPES):
            r = []
            for item in variable:
                if self.cur_size >= SnapshotCollectorConfigManager.get_max_size():
                    break
                val = self.collect_variable_value(item, depth + 1, max_depth)
                if val is not None:
                    r.append(val)

            return Value(var_type=type(variable).__name__, value=r)

        if isinstance(variable, types.FunctionType):
            self.cur_size += len(variable.__name__)
            return Value(var_type=type(variable).__name__, value=variable.__name__)

        if hasattr(variable, '__dict__'):
            items = variable.__dict__.items()
            if six.PY3:
                items = list(itertools.islice(items, 20 + 1))
            r = {}
            for name, value in items:
                if self.cur_size >= SnapshotCollectorConfigManager.get_max_size():
                    break
                val = self.collect_variable_value(value, depth + 1, max_depth)
                if val is not None:
                    r[str(name)] = val
                    self.cur_size += len(repr(name))

            return Value(var_type=type(variable).__name__, value=r)

        return Value(var_type=type(variable).__name__, value=None)


def normalize_path(path):
    path = os.path.normpath(path)

    for sys_path in sys.path:
        if not sys_path:
            continue

        sys_path = os.path.join(sys_path, '')

        if path.startswith(sys_path):
            return path[len(sys_path):]

    return path


def _trim_string(s, max_len):
    if len(s) <= max_len:
        return s
    return s[:max_len + 1] + '...'
