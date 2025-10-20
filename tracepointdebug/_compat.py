import sys, sysconfig

def build_supports_free_threading() -> bool:
    """
    Checks if the Python interpreter was built with free-threading support.
    """
    return bool(sysconfig.get_config_var("Py_GIL_DISABLED"))

def gil_is_enabled() -> bool:
    """
    Checks if the GIL is currently enabled.

    Requires Python 3.13 or newer.
    """
    f = getattr(sys, "_is_gil_enabled", None)
    return True if f is None else bool(f())

def is_actually_free_threaded() -> bool:
    """
    Checks if the Python interpreter is currently running in free-threaded mode.
    """
    return build_supports_free_threading() and not gil_is_enabled()
