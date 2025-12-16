"""
Centralized MQTT Client for Frying AI System
Handles all MQTT communication with automatic metadata injection
"""

import paho.mqtt.client as mqtt
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Callable
import time

logger = logging.getLogger(__name__)


class MQTTClient:
    """Centralized MQTT client with automatic system info injection"""

    def __init__(
        self,
        broker: str = "localhost",
        port: int = 1883,
        client_id: Optional[str] = None,
        topic_prefix: str = "frying_ai",
        system_info: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize MQTT client

        Args:
            broker: MQTT broker address
            port: MQTT broker port
            client_id: Unique client ID (auto-generated if None)
            topic_prefix: Prefix for all topics
            system_info: System information dictionary (from SystemInfo class)
        """
        self.broker = broker
        self.port = port
        self.topic_prefix = topic_prefix
        self.system_info = system_info or {}

        # Create MQTT client
        if client_id is None:
            client_id = f"frying_ai_{int(time.time())}"

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish = self._on_publish

        self.connected = False
        self.connect_retry_delay = 5  # seconds

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        """Callback when connected to broker"""
        if reason_code == 0:
            self.connected = True
            logger.info(f"Connected to MQTT broker at {self.broker}:{self.port}")
        else:
            self.connected = False
            logger.error(f"Failed to connect to MQTT broker: {reason_code}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        """Callback when disconnected from broker"""
        self.connected = False
        logger.warning(f"Disconnected from MQTT broker: {reason_code}")

    def _on_publish(self, client, userdata, mid, reason_code, properties):
        """Callback when message is published"""
        logger.debug(f"Message published: mid={mid}")

    def connect(self, blocking: bool = False, timeout: float = 5.0) -> bool:
        """
        Connect to MQTT broker

        Args:
            blocking: If True, wait for connection
            timeout: Connection timeout in seconds

        Returns:
            True if connected successfully
        """
        try:
            logger.info(f"Connecting to MQTT broker at {self.broker}:{self.port}")
            self.client.connect(self.broker, self.port, 60)

            if blocking:
                # Start loop and wait for connection
                self.client.loop_start()
                start_time = time.time()
                while not self.connected and (time.time() - start_time) < timeout:
                    time.sleep(0.1)
                return self.connected
            else:
                # Start non-blocking loop
                self.client.loop_start()
                return True

        except Exception as e:
            logger.error(f"Error connecting to MQTT broker: {e}")
            return False

    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()
        self.connected = False
        logger.info("Disconnected from MQTT broker")

    def publish(
        self,
        topic_suffix: str,
        payload: Dict[str, Any],
        qos: int = 1,
        retain: bool = False,
        include_metadata: bool = True
    ) -> bool:
        """
        Publish message with automatic metadata injection

        Args:
            topic_suffix: Topic suffix (will be prefixed with topic_prefix)
            payload: Message payload dictionary
            qos: Quality of Service (0, 1, or 2)
            retain: Retain message flag
            include_metadata: Include timestamp and device info

        Returns:
            True if published successfully
        """
        try:
            # Build full topic
            full_topic = f"{self.topic_prefix}/{topic_suffix}"

            # Add metadata if requested
            if include_metadata:
                message = {
                    "timestamp": datetime.now().isoformat(),
                    "device": self.system_info,
                    "data": payload
                }
            else:
                message = payload

            # Convert to JSON
            json_payload = json.dumps(message)

            # Publish
            result = self.client.publish(full_topic, json_payload, qos=qos, retain=retain)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"Published to {full_topic}: {len(json_payload)} bytes")
                return True
            else:
                logger.error(f"Failed to publish to {full_topic}: {result.rc}")
                return False

        except Exception as e:
            logger.error(f"Error publishing message: {e}")
            return False

    def subscribe(self, topic: str, callback: Callable, qos: int = 1, use_prefix: bool = False):
        """
        Subscribe to topic

        Args:
            topic: Topic to subscribe (no prefix by default)
            callback: Callback function(client, userdata, message)
            qos: Quality of Service
            use_prefix: If True, add topic_prefix (default: False)
        """
        full_topic = f"{self.topic_prefix}/{topic}" if use_prefix else topic

        # Initialize callbacks dict if not exists
        if not hasattr(self, '_callbacks'):
            self._callbacks = {}

            # Set up message dispatcher (only once)
            def on_message(client, userdata, msg):
                topic = msg.topic
                if topic in self._callbacks:
                    try:
                        self._callbacks[topic](client, userdata, msg)
                    except Exception as e:
                        logger.error(f"Error processing message from {topic}: {e}")

            self.client.on_message = on_message

        # Store callback for this topic
        self._callbacks[full_topic] = callback

        self.client.subscribe(full_topic, qos=qos)
        logger.info(f"Subscribed to {full_topic}")

    def is_connected(self) -> bool:
        """Check if connected to broker"""
        return self.connected

    def __enter__(self):
        """Context manager entry"""
        self.connect(blocking=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
