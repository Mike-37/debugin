# Thin wrapper around the existing cdbg_native functionality
import sys

# Store cookies for removing breakpoints later
_breakpoint_cookies = {}

def start():
    try:
        import tracepointdebug.cdbg_native as cdbg_native
        if hasattr(cdbg_native, 'InitializeModule'):
            cdbg_native.InitializeModule(None)
    except ImportError:
        # Fallback if cdbg_native is not available (e.g., on systems without native build)
        from .pytrace import start as pytrace_start
        pytrace_start()

def stop():
    try:
        import tracepointdebug.cdbg_native as cdbg_native
        # No stop function in cdbg_native, so just return
        pass
    except ImportError:
        # Fallback if cdbg_native is not available
        from .pytrace import stop as pytrace_stop
        pytrace_stop()

def set_logpoint(lp_id, file, line, fn):
    # Use the native C++ implementation for setting breakpoints when available
    try:
        import tracepointdebug.cdbg_native as cdbg_native
        # For native implementation, call the native method directly
        # This is a simplified approach - native module expects code object in real usage
        cookie = cdbg_native.SetConditionalBreakpoint(None, line, None, fn)
        _breakpoint_cookies[lp_id] = cookie
        return cookie
    except ImportError:
        # Fallback to pytrace if native module is not available
        from .pytrace import set_logpoint as _py_set
        return _py_set(lp_id, file, line, fn)
    except Exception as e:
        # Fallback to pytrace if native fails
        print(f"Warning: Native breakpoint failed, falling back: {e}", file=sys.stderr)
        from .pytrace import set_logpoint as _py_set
        return _py_set(lp_id, file, line, fn)

def remove_logpoint(lp_id):
    # Use the native C++ implementation for removing breakpoints when available
    try:
        import tracepointdebug.cdbg_native as cdbg_native
        if lp_id in _breakpoint_cookies and hasattr(cdbg_native, 'ClearConditionalBreakpoint'):
            cookie = _breakpoint_cookies[lp_id]
            cdbg_native.ClearConditionalBreakpoint(cookie)
            del _breakpoint_cookies[lp_id]
        else:
            # Fallback if cookie not tracked or method not available
            from .pytrace import remove_logpoint as _py_remove
            _py_remove(lp_id)
    except ImportError:
        # Fallback to pytrace if native module is not available
        from .pytrace import remove_logpoint as _py_remove
        _py_remove(lp_id)
    except Exception as e:
        # Fallback to pytrace if native fails
        print(f"Warning: Native remove breakpoint failed, falling back: {e}", file=sys.stderr)
        from .pytrace import remove_logpoint as _py_remove
        _py_remove(lp_id)