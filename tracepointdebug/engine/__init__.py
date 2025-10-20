import sys, os
engine_choice = os.environ.get("TRACEPOINTDEBUG_ENGINE", "auto")

if engine_choice == "pytrace" or (engine_choice == "auto" and sys.version_info >= (3, 11)):
    from .pytrace import start, stop, set_logpoint, remove_logpoint
else:
    try:
        from .native import start, stop, set_logpoint, remove_logpoint
    except ImportError:
        # fallback to pytrace if native engine is not available
        from .pytrace import start, stop, set_logpoint, remove_logpoint