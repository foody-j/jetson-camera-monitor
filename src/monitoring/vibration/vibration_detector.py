"""
Vibration Detector

Main vibration monitoring system that coordinates sensor reading,
data analysis, and logging.
"""

import time
import logging
import threading
import json
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from datetime import datetime

from .rs485_sensor import RS485VibrationSensor, VibrationReading
from .vibration_analyzer import VibrationAnalyzer, VibrationAlert

logger = logging.getLogger(__name__)


class VibrationDetector:
    """
    Main vibration detection system

    Features:
    - Continuous vibration monitoring
    - Real-time analysis
    - Data logging to CSV/JSON
    - Alert notifications
    - Configurable sampling rate
    """

    def __init__(
        self,
        sensor_config: Dict[str, Any],
        analyzer_config: Optional[Dict[str, Any]] = None,
        log_directory: str = 'data/vibration_logs',
        sampling_rate: float = 10.0  # Hz
    ):
        """
        Initialize vibration detector

        Args:
            sensor_config: RS485 sensor configuration
            analyzer_config: Analyzer settings (window_size, thresholds)
            log_directory: Directory for data logs
            sampling_rate: Samples per second
        """
        self.sensor_config = sensor_config
        self.log_directory = Path(log_directory)
        self.log_directory.mkdir(parents=True, exist_ok=True)
        self.sampling_rate = sampling_rate
        self.sampling_interval = 1.0 / sampling_rate

        # Initialize components
        self.sensor: Optional[RS485VibrationSensor] = None
        self.analyzer = VibrationAnalyzer(**(analyzer_config or {}))

        # Monitoring state
        self.is_running = False
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None

        # Callback for alerts
        self.alert_callback: Optional[Callable[[VibrationAlert], None]] = None

        # Current session
        self.session_id: Optional[str] = None
        self.session_log_file: Optional[Path] = None
        self.session_start_time: Optional[float] = None

        # Latest reading
        self.latest_reading: Optional[VibrationReading] = None

    def initialize(self) -> bool:
        """
        Initialize sensor connection

        Returns:
            True if successful, False otherwise
        """
        try:
            self.sensor = RS485VibrationSensor(self.sensor_config)

            if self.sensor.is_connected():
                logger.info("Vibration sensor initialized successfully")
                return True
            else:
                logger.error("Failed to connect to vibration sensor")
                return False

        except Exception as e:
            logger.error(f"Sensor initialization error: {e}")
            return False

    def start_monitoring(self, session_name: Optional[str] = None) -> bool:
        """
        Start continuous vibration monitoring

        Args:
            session_name: Optional session identifier

        Returns:
            True if started successfully
        """
        if self.is_monitoring:
            logger.warning("Monitoring already active")
            return False

        if self.sensor is None or not self.sensor.is_connected():
            logger.error("Sensor not initialized")
            return False

        # Create session
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_id = session_name or f"vibration_{timestamp}"
        self.session_log_file = self.log_directory / f"{self.session_id}.csv"
        self.session_start_time = time.time()

        # Write CSV header
        with open(self.session_log_file, 'w') as f:
            f.write("timestamp,elapsed_time,x_axis,y_axis,z_axis,magnitude,temperature,frequency\n")

        # Reset analyzer
        self.analyzer.reset()

        # Start monitoring thread
        self.is_monitoring = True
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()

        logger.info(f"Vibration monitoring started - Session: {self.session_id}")
        return True

    def _monitoring_loop(self) -> None:
        """Background monitoring loop"""
        while self.is_running:
            loop_start = time.time()

            try:
                # Read sensor data
                reading = self.sensor.read()

                if reading:
                    self.latest_reading = reading

                    # Add to analyzer
                    self.analyzer.add_reading(reading)

                    # Log to file
                    self._log_reading(reading)

                    # Check for new alerts
                    self._check_alerts()

                else:
                    logger.debug("No reading from sensor")

            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")

            # Maintain sampling rate
            elapsed = time.time() - loop_start
            sleep_time = max(0, self.sampling_interval - elapsed)
            time.sleep(sleep_time)

        self.is_monitoring = False
        logger.info("Monitoring loop stopped")

    def _log_reading(self, reading: VibrationReading) -> None:
        """Log reading to CSV file"""
        if self.session_log_file is None or self.session_start_time is None:
            return

        elapsed = reading.timestamp - self.session_start_time

        with open(self.session_log_file, 'a') as f:
            f.write(
                f"{reading.timestamp:.3f},"
                f"{elapsed:.3f},"
                f"{reading.x_axis:.6f},"
                f"{reading.y_axis:.6f},"
                f"{reading.z_axis:.6f},"
                f"{reading.magnitude:.6f},"
                f"{reading.temperature if reading.temperature else ''},"
                f"{reading.frequency if reading.frequency else ''}\n"
            )

    def _check_alerts(self) -> None:
        """Check for new alerts and invoke callback"""
        if self.alert_callback:
            recent_alerts = self.analyzer.get_recent_alerts(count=1)
            if recent_alerts:
                latest_alert = recent_alerts[-1]
                # Only notify if alert is very recent (within last 2 seconds)
                if time.time() - latest_alert.timestamp < 2.0:
                    self.alert_callback(latest_alert)

    def stop_monitoring(self) -> None:
        """Stop vibration monitoring"""
        if not self.is_monitoring:
            return

        self.is_running = False

        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)

        # Save session summary
        self._save_session_summary()

        logger.info("Vibration monitoring stopped")

    def _save_session_summary(self) -> None:
        """Save session statistics to JSON"""
        if self.session_id is None:
            return

        summary_file = self.log_directory / f"{self.session_id}_summary.json"

        summary = {
            'session_id': self.session_id,
            'start_time': self.session_start_time,
            'end_time': time.time(),
            'duration_seconds': time.time() - self.session_start_time if self.session_start_time else 0,
            'statistics': self.analyzer.export_stats_json(),
            'sensor_config': self.sensor_config
        }

        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Session summary saved: {summary_file}")

    def get_current_status(self) -> Dict[str, Any]:
        """
        Get current monitoring status

        Returns:
            Dictionary with current state and statistics
        """
        stats = self.analyzer.get_current_stats()
        summary = self.analyzer.get_summary()

        return {
            'is_monitoring': self.is_monitoring,
            'sensor_connected': self.sensor.is_connected() if self.sensor else False,
            'session_id': self.session_id,
            'uptime_seconds': time.time() - self.session_start_time if self.session_start_time else 0,
            'latest_reading': {
                'timestamp': self.latest_reading.timestamp,
                'x_axis': self.latest_reading.x_axis,
                'y_axis': self.latest_reading.y_axis,
                'z_axis': self.latest_reading.z_axis,
                'magnitude': self.latest_reading.magnitude,
                'temperature': self.latest_reading.temperature,
            } if self.latest_reading else None,
            'statistics': {
                'mean_magnitude': stats.mean_magnitude,
                'max_magnitude': stats.max_magnitude,
                'rms_value': stats.rms_value,
                'sample_count': stats.sample_count
            } if stats else None,
            'analysis': summary,
            'recent_alerts': [
                {
                    'timestamp': alert.timestamp,
                    'type': alert.alert_type,
                    'severity': alert.severity,
                    'magnitude': alert.magnitude,
                    'message': alert.message
                }
                for alert in self.analyzer.get_recent_alerts(5)
            ]
        }

    def set_alert_callback(self, callback: Callable[[VibrationAlert], None]) -> None:
        """
        Set callback function for alerts

        Args:
            callback: Function to call when alert is triggered
        """
        self.alert_callback = callback

    def cleanup(self) -> None:
        """Cleanup resources"""
        self.stop_monitoring()

        if self.sensor:
            self.sensor.close()

        logger.info("Vibration detector cleanup complete")

    def __enter__(self):
        """Context manager entry"""
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.cleanup()
