import sys, sysconfig, pytest

def build_supports_ft():
    return bool(sysconfig.get_config_var("Py_GIL_DISABLED"))

def gil_is_enabled():
    f = getattr(sys, "_is_gil_enabled", None)
    return True if f is None else bool(f())

def test_reports_ft_capability():
    assert isinstance(build_supports_ft(), bool)

@pytest.mark.skipif(build_supports_ft() and not gil_is_enabled(), reason="unsafe cross-thread frame walk in FT")
def test_cross_thread_walk_guard():
    # If you have a helper that walks frames, call it here; else assert _current_frames() is accessible
    frames = sys._current_frames()
    assert isinstance(frames, dict)