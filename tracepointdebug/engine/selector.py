import os
import sys
import warnings

import logging
from tracepointdebug._compat import build_supports_free_threading, gil_is_enabled, is_actually_free_threaded
from tracepointdebug.engine import native, pytrace

logger = logging.getLogger(__name__)

def get_engine():
    """
    Selects the appropriate trace engine based on Python version, GIL status,
    and environment variables.
    """
    engine_override = os.environ.get("TRACEPOINTDEBUG_ENGINE")
    
    is_ft = is_actually_free_threaded()
    gil_on = gil_is_enabled()
    
    logger.info(
        "Engine selection: Py_GIL_DISABLED=%s, gil_is_enabled()=%s, override=%s",
        os.environ.get("Py_GIL_DISABLED", "not set"),
        gil_on,
        engine_override
    )

    # Free-threaded mode requires special handling
    if is_ft:
        if engine_override and engine_override.lower() == "native":
            warnings.warn(
                "TRACEPOINTDEBUG_ENGINE=native is not supported in free-threaded mode. "
                "Falling back to 'pytrace'. Cross-thread frame walks are disabled."
            )
        logger.info("Free-threaded mode detected. Forcing 'pytrace' engine.")
        return pytrace

    # Engine selection for GIL-enabled or older Python versions
    py_version = sys.version_info
    if engine_override:
        if engine_override.lower() == "native":
            logger.info("Engine override: using 'native'.")
            return native
        if engine_override.lower() == "pytrace":
            logger.info("Engine override: using 'pytrace'.")
            return pytrace

    if (3, 8) <= py_version <= (3, 10):
        logger.info("Python version is %s. Defaulting to 'native' engine.", py_version)
        return native  # Native-first for older versions
    
    logger.info("Python version is %s. Defaulting to 'pytrace' engine.", py_version)
    # Pytrace-first for 3.11+ (including 3.13/3.14 with GIL on)
    return pytrace
