from __future__ import absolute_import
import logging
import socket
import time
import os
from concurrent.futures.thread import ThreadPoolExecutor
from threading import Thread
from uuid import uuid4

from tracepointdebug.config import config_names
from tracepointdebug.config.config_provider import ConfigProvider
from tracepointdebug.application import utils
from tracepointdebug.application.application import Application
from tracepointdebug.broker.application.application_status import ApplicationStatus
from tracepointdebug.broker.broker_client import BrokerConnection, EventClient
from tracepointdebug.broker.broker_credentials import BrokerCredentials
from tracepointdebug.broker.broker_message_callback import BrokerMessageCallback
from tracepointdebug.broker.event.application_status_event import ApplicationStatusEvent
from tracepointdebug.probe.application.application_status_tracepoint_provider import \
    ApplicationStatusTracePointProvider
from tracepointdebug.probe.encoder import to_json

from tracepointdebug.broker.request.filter_tracepoints_request import FilterTracePointsRequest
from tracepointdebug.broker.request.filter_logpoints_request import FilterLogPointsRequest
from tracepointdebug.broker.request.get_config_request import GetConfigRequest

API_KEY = ConfigProvider.get(config_names.SIDEKICK_APIKEY)
BROKER_HOST = utils.get_from_environment_variables("SIDEKICK_BROKER_HOST", "wss://broker.service.runsidekick.com", str)
BROKER_PORT = utils.get_from_environment_variables("SIDEKICK_BROKER_PORT", 443, int)
EVENT_SINK_URL = os.getenv("EVENT_SINK_URL", "http://127.0.0.1:4317")

APPLICATION_STATUS_PUBLISH_PERIOD_IN_SECS = 60
GET_CONFIG_PERIOD_IN_SECS = 5 * 60

logger = logging.getLogger(__name__)


class BrokerManager(object):


    __instance = None
    hostname = socket.gethostname()


    def __init__(self):
        if not EVENT_SINK_URL:
            raise RuntimeError("EVENT_SINK_URL environment variable not set.")
        logger.info("Event sink URL: %s", EVENT_SINK_URL)
        self._client = None
        self._initialize_event_client()
        
        self.broker_connection = None
        self.initialized = False
        self._event_executor = ThreadPoolExecutor()
        self._request_executor = ThreadPoolExecutor()
        self._tracepoint_data_redaction_callback = None
        self._log_data_redaction_callback = None
        import sys
        if sys.version_info[0] >= 3:
            self.application_status_thread = Thread(target=self.application_status_sender, daemon=True)
            self.get_config_thread = Thread(target=self.get_config_sender, daemon=True)
        else:
            self.application_status_thread = Thread(target=self.application_status_sender)
            self.get_config_thread = Thread(target=self.get_config_sender)
            self.application_status_thread.daemon = True
            self.get_config_thread.daemon = True
        self.application_status_providers = [ApplicationStatusTracePointProvider()]

    def _initialize_event_client(self):
        """Initialize the event client with health check"""
        try:
            self._client = EventClient(base_url=EVENT_SINK_URL)
            # Perform health check
            import requests
            response = requests.get(f"{EVENT_SINK_URL}/health", timeout=2)
            response.raise_for_status()
            logger.info("Event sink health check passed")
        except Exception as e:
            logger.error("Failed to initialize EventClient: %s", e)
            self._client = None

    @staticmethod
    def instance():
        return BrokerManager() if BrokerManager.__instance is None else BrokerManager.__instance


    def initialize(self):
        if not self.initialized:
            self.connect_to_broker()
            self.initialized = True

    def connect_to_broker(self):
        try:
            application_info = Application.get_application_info()
            broker_credentials = BrokerCredentials(api_key=API_KEY,
                                                   app_instance_id=application_info['applicationInstanceId'],
                                                   app_name=application_info['applicationName'],
                                                   app_stage=application_info['applicationStage'],
                                                   app_version=application_info['applicationVersion'],
                                                   runtime=application_info['applicationRuntime'],
                                                   hostname=BrokerManager.hostname)

            broker_message_callback = BrokerMessageCallback()
            self.broker_connection = BrokerConnection(host=BROKER_HOST, port=BROKER_PORT,
                                                      broker_credentials=broker_credentials,
                                                      message_callback=broker_message_callback.on_message,
                                                      initial_request_to_broker=self.publish_request)

            self.broker_connection.connect()
            self.application_status_thread.start()
            self.get_config_thread.start()
        except Exception as e:
            logger.error("Error connecting to broker %s" % e)


    @staticmethod
    def prepare_event(event):
        if event.id is None:
            event.id = str(uuid4())
        if event.time is None:
            event.time = int(time.time() * 1000)
        if event.hostname is None:
            event.hostname = socket.gethostname()
        application_info = Application.get_application_info()
        event.application_instance_id = application_info['applicationInstanceId']
        event.application_name = application_info['applicationName']

    def do_publish_event(self, event):
        # Check if client is initialized
        if self._client is None:
            logger.error("EventClient is None in do_publish_event. Cannot publish event.")
            return False
            
        self.prepare_event(event)
        try:
            payload = event.to_json() if hasattr(event, "to_json") else event.__dict__
            # Add runtime header for event sink
            import requests
            headers = {"X-Runtime": Application.get_application_info().get("applicationRuntime", "python")}
            url = f"{self._client.base_url}/api/events"
            
            # Use the EventClient's send method with retries
            for i in range(self._client.retries):
                try:
                    data = requests.compat.json.dumps(payload)
                    r = self._client.session.post(url, data=data, 
                                              headers={"content-type": "application/json", **headers}, 
                                              timeout=self._client.timeout)
                    r.raise_for_status()
                    return True
                except Exception as e:
                    if i == self._client.retries - 1:
                        logger.exception("publish_event failed after %d retries to %s", self._client.retries, url)
                        return False
                    time.sleep(self._client.backoff * (2 ** i))
            return False
        except Exception as e:
            logger.exception("publish_event failed: %s (%s)", type(event).__name__, getattr(event, 'id', None))
            return False


    def publish_event(self, event):
        if self._client is None:
            logger.error("EventClient is None in publish_event. Cannot publish event.")
            return
        self._event_executor.submit(self.do_publish_event, event)


    @staticmethod
    def create_request():
        application_info = Application.get_application_info()
        filter_tracepoints_request = FilterTracePointsRequest(application_info.get("applicationName", ""), 
                                                            application_info.get("applicationVersion", ""),
                                                            application_info.get("applicationStage", ""),
                                                            application_info.get("applicationTags", {}))
        filter_tracepoints_request.id = str(uuid4())

        filter_logpoints_request = FilterLogPointsRequest(application_info.get("applicationName", ""), 
                                                            application_info.get("applicationVersion", ""),
                                                            application_info.get("applicationStage", ""),
                                                            application_info.get("applicationTags", {}))
        filter_logpoints_request.id = str(uuid4())
        return filter_tracepoints_request, filter_logpoints_request

    def do_publish_request(self):
        tracepoints_request, logpoints_request = self.create_request()
        try:
            serialized_tracepoints_request = to_json(tracepoints_request)
            self.broker_connection.send(serialized_tracepoints_request)
            serialized_logpoints_request = to_json(logpoints_request)
            self.broker_connection.send(serialized_logpoints_request)
        except Exception as e:
            logger.error("Error serializing request %s" % e)


    def publish_request(self):
        self._request_executor.submit(self.do_publish_request)


    def application_status_sender(self):
        while self.broker_connection is not None and self.broker_connection.is_running():
            self.broker_connection.connected.wait()
            self.publish_application_status()
            time.sleep(APPLICATION_STATUS_PUBLISH_PERIOD_IN_SECS)


    def get_config_sender(self):
        while self.broker_connection is not None and self.broker_connection.is_running():
            self.broker_connection.connected.wait()
            self.send_get_config()
            time.sleep(GET_CONFIG_PERIOD_IN_SECS)

    def send_get_config(self):
        try:
            application_info = Application.get_application_info()
            get_config_request = GetConfigRequest(application_info.get("applicationName", ""), 
                                                    application_info.get("applicationVersion", ""),
                                                    application_info.get("applicationStage", ""),
                                                    application_info.get("applicationTags", {}))
            serialized_get_config_request = to_json(get_config_request)
            self.broker_connection.send(serialized_get_config_request)       
        except Exception as e:
            pass

    def publish_application_status(self, client=None):
        application_info = Application.get_application_info()
        application_status = ApplicationStatus()
        application_status.name = application_info['applicationName']
        application_status.instance_id = application_info['applicationInstanceId']
        application_status.version = application_info['applicationVersion']
        application_status.stage = application_info['applicationStage']
        application_status.runtime = application_info['applicationRuntime']
        try:
            hostname = socket.gethostname()
            application_status.hostname = hostname
            host_ip = socket.gethostbyname(hostname)
            application_status.ip = host_ip
        except:
            pass

        for status_provider in self.application_status_providers:
            status_provider.provide(application_status, client)
        event = ApplicationStatusEvent(client=client, application=application_status)
        self.publish_event(event)