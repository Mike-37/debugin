import atexit
import os

# Read version from VERSION file (single source of truth)
_version_file = os.path.join(os.path.dirname(__file__), '..', 'VERSION')
try:
    with open(_version_file, 'r') as f:
        __version__ = f.read().strip()
except Exception:
    __version__ = '0.3.0'  # fallback

# Import control API to trigger auto-start if enabled
from .control_api import start_control_api

from tracepointdebug.probe.dynamicConfig.dynamic_config_manager import DynamicConfigManager

from .engine.selector import get_engine
from .broker.broker_manager import BrokerManager
from .probe.breakpoints.tracepoint import TracePointManager
from .probe.breakpoints.logpoint import LogPointManager
from .probe.error_stack_manager import ErrorStackManager
from .control_api import start_control_api

'''
    After importing ConfigProvider for the first time, the __init__.py has been run by interpreter and
    whole configuration is reflected to configs.
'''


tracepoint_data_redaction_callback = None
log_data_redaction_callback = None

import logging
logger = logging.getLogger(__name__)

def start(tracepoint_data_redaction_callback=None, log_data_redaction_callback=None, enable_control_api=True, control_api_port=5001):
    engine = get_engine()
    engine.start()
    
    _broker_manager = BrokerManager.instance()
    
    TracePointManager(broker_manager=_broker_manager, data_redaction_callback=tracepoint_data_redaction_callback, engine=engine)
    LogPointManager(broker_manager=_broker_manager, data_redaction_callback=log_data_redaction_callback, engine=engine)
    
    esm = ErrorStackManager(broker_manager=_broker_manager)
    dcm = DynamicConfigManager(broker_manager=_broker_manager)
    
    _broker_manager.initialize()
    esm.start()
    
    # Start control API if enabled
    if enable_control_api:
        start_control_api(port=control_api_port, broker_manager=_broker_manager, engine=engine)
    
    atexit.register(dcm.handle_detach)