import sys, threading, time

_ACTIVE = False
_CALLBACKS = {}  # id -> callable
_LOCK = threading.RLock()

def _trace(frame, event, arg):
    # Fast path: only on 'line' or 'call' as needed
    if not _ACTIVE or event not in ("line", "call"):
        return _trace
    code = frame.f_code
    key = (code.co_filename, code.co_firstlineno, frame.f_lineno)
    with _LOCK:
        for cb in _CALLBACKS.values():
            cb(frame, event, arg)  # should implement quotas/redaction
    return _trace

def start():
    global _ACTIVE
    if _ACTIVE: return
    _ACTIVE = True
    sys.settrace(_trace)

def stop():
    global _ACTIVE
    _ACTIVE = False
    sys.settrace(None)

def set_logpoint(lp_id, file, line, fn):
    with _LOCK:
        _CALLBACKS[lp_id] = fn

def remove_logpoint(lp_id):
    with _LOCK:
        _CALLBACKS.pop(lp_id, None)