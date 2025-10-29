"""
Vibration Data Analyzer

Analyzes vibration data to detect anomalies, patterns, and trends.
Provides statistical analysis and threshold-based alerting.
"""

import numpy as np
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from collections import deque
import json
import time

logger = logging.getLogger(__name__)


@dataclass
class VibrationStats:
    """Statistical summary of vibration data"""
    mean_magnitude: float
    max_magnitude: float
    min_magnitude: float
    std_deviation: float
    rms_value: float
    peak_to_peak: float
    sample_count: int
    duration_seconds: float


@dataclass
class VibrationAlert:
    """Vibration alert information"""
    timestamp: float
    alert_type: str  # 'threshold', 'spike', 'anomaly'
    severity: str    # 'low', 'medium', 'high', 'critical'
    magnitude: float
    threshold: float
    message: str


class VibrationAnalyzer:
    """
    Analyze vibration data for patterns and anomalies

    Features:
    - Real-time statistics calculation
    - Threshold-based alerting
    - Spike detection
    - Trend analysis
    - Data buffering for windowed analysis
    """

    def __init__(
        self,
        window_size: int = 100,
        alert_thresholds: Optional[Dict[str, float]] = None
    ):
        """
        Initialize analyzer

        Args:
            window_size: Number of samples to keep in buffer for analysis
            alert_thresholds: Dictionary of alert thresholds
                {
                    'low': 2.0,      # m/s²
                    'medium': 5.0,
                    'high': 10.0,
                    'critical': 20.0
                }
        """
        self.window_size = window_size
        self.alert_thresholds = alert_thresholds or {
            'low': 2.0,
            'medium': 5.0,
            'high': 10.0,
            'critical': 20.0
        }

        # Data buffers (using deque for efficient rolling window)
        self.magnitude_buffer = deque(maxlen=window_size)
        self.x_buffer = deque(maxlen=window_size)
        self.y_buffer = deque(maxlen=window_size)
        self.z_buffer = deque(maxlen=window_size)
        self.timestamp_buffer = deque(maxlen=window_size)

        # Alert tracking
        self.alerts: List[VibrationAlert] = []
        self.last_alert_time = 0
        self.alert_cooldown = 5.0  # seconds between similar alerts

        # Statistics
        self.total_samples = 0
        self.start_time = time.time()

    def add_reading(self, reading) -> None:
        """
        Add new vibration reading to buffer

        Args:
            reading: VibrationReading object
        """
        self.magnitude_buffer.append(reading.magnitude)
        self.x_buffer.append(reading.x_axis)
        self.y_buffer.append(reading.y_axis)
        self.z_buffer.append(reading.z_axis)
        self.timestamp_buffer.append(reading.timestamp)
        self.total_samples += 1

        # Check for alerts
        self._check_thresholds(reading)
        self._check_spike(reading)

    def get_current_stats(self) -> Optional[VibrationStats]:
        """
        Calculate current statistics from buffered data

        Returns:
            VibrationStats object or None if insufficient data
        """
        if len(self.magnitude_buffer) < 2:
            return None

        magnitudes = np.array(self.magnitude_buffer)

        # Calculate statistics
        mean_mag = np.mean(magnitudes)
        max_mag = np.max(magnitudes)
        min_mag = np.min(magnitudes)
        std_dev = np.std(magnitudes)
        rms = np.sqrt(np.mean(magnitudes ** 2))
        peak_to_peak = max_mag - min_mag

        duration = self.timestamp_buffer[-1] - self.timestamp_buffer[0]

        return VibrationStats(
            mean_magnitude=float(mean_mag),
            max_magnitude=float(max_mag),
            min_magnitude=float(min_mag),
            std_deviation=float(std_dev),
            rms_value=float(rms),
            peak_to_peak=float(peak_to_peak),
            sample_count=len(magnitudes),
            duration_seconds=duration
        )

    def _check_thresholds(self, reading) -> None:
        """Check if reading exceeds thresholds"""
        magnitude = reading.magnitude

        # Determine severity level
        severity = None
        threshold = 0.0

        if magnitude >= self.alert_thresholds['critical']:
            severity = 'critical'
            threshold = self.alert_thresholds['critical']
        elif magnitude >= self.alert_thresholds['high']:
            severity = 'high'
            threshold = self.alert_thresholds['high']
        elif magnitude >= self.alert_thresholds['medium']:
            severity = 'medium'
            threshold = self.alert_thresholds['medium']
        elif magnitude >= self.alert_thresholds['low']:
            severity = 'low'
            threshold = self.alert_thresholds['low']

        if severity:
            # Apply cooldown to avoid alert spam
            current_time = reading.timestamp
            if current_time - self.last_alert_time > self.alert_cooldown:
                alert = VibrationAlert(
                    timestamp=reading.timestamp,
                    alert_type='threshold',
                    severity=severity,
                    magnitude=magnitude,
                    threshold=threshold,
                    message=f"{severity.upper()} vibration detected: {magnitude:.2f} m/s² (threshold: {threshold:.2f})"
                )
                self.alerts.append(alert)
                self.last_alert_time = current_time
                logger.warning(alert.message)

    def _check_spike(self, reading) -> None:
        """Detect sudden spikes in vibration"""
        if len(self.magnitude_buffer) < 10:
            return

        # Calculate recent average (excluding current reading)
        recent_avg = np.mean(list(self.magnitude_buffer)[:-1])

        # Spike detection: current reading is 3x the recent average
        if reading.magnitude > recent_avg * 3 and recent_avg > 0.1:
            current_time = reading.timestamp
            if current_time - self.last_alert_time > self.alert_cooldown:
                alert = VibrationAlert(
                    timestamp=reading.timestamp,
                    alert_type='spike',
                    severity='high',
                    magnitude=reading.magnitude,
                    threshold=recent_avg * 3,
                    message=f"SPIKE detected: {reading.magnitude:.2f} m/s² (3x average: {recent_avg:.2f})"
                )
                self.alerts.append(alert)
                self.last_alert_time = current_time
                logger.warning(alert.message)

    def get_recent_alerts(self, count: int = 10) -> List[VibrationAlert]:
        """Get most recent alerts"""
        return self.alerts[-count:] if self.alerts else []

    def get_axis_stats(self) -> Dict[str, Dict[str, float]]:
        """Get statistics for each axis"""
        if len(self.x_buffer) < 2:
            return {}

        def axis_stats(buffer):
            arr = np.array(buffer)
            return {
                'mean': float(np.mean(arr)),
                'max': float(np.max(arr)),
                'min': float(np.min(arr)),
                'std': float(np.std(arr)),
                'rms': float(np.sqrt(np.mean(arr ** 2)))
            }

        return {
            'x_axis': axis_stats(self.x_buffer),
            'y_axis': axis_stats(self.y_buffer),
            'z_axis': axis_stats(self.z_buffer)
        }

    def get_trend(self, samples: int = 20) -> str:
        """
        Analyze trend over recent samples

        Returns:
            'increasing', 'decreasing', 'stable', or 'insufficient_data'
        """
        if len(self.magnitude_buffer) < samples:
            return 'insufficient_data'

        recent_data = list(self.magnitude_buffer)[-samples:]
        x = np.arange(len(recent_data))
        y = np.array(recent_data)

        # Linear regression
        coeffs = np.polyfit(x, y, 1)
        slope = coeffs[0]

        # Classify trend based on slope
        if abs(slope) < 0.01:  # Nearly flat
            return 'stable'
        elif slope > 0:
            return 'increasing'
        else:
            return 'decreasing'

    def is_abnormal(self) -> bool:
        """
        Check if current vibration level is abnormal

        Returns:
            True if any recent reading exceeds medium threshold
        """
        if not self.magnitude_buffer:
            return False

        recent = list(self.magnitude_buffer)[-5:]  # Last 5 readings
        return any(mag >= self.alert_thresholds['medium'] for mag in recent)

    def reset(self) -> None:
        """Reset all buffers and statistics"""
        self.magnitude_buffer.clear()
        self.x_buffer.clear()
        self.y_buffer.clear()
        self.z_buffer.clear()
        self.timestamp_buffer.clear()
        self.alerts.clear()
        self.total_samples = 0
        self.start_time = time.time()
        logger.info("Vibration analyzer reset")

    def export_stats_json(self) -> str:
        """Export current statistics as JSON"""
        stats = self.get_current_stats()
        axis_stats = self.get_axis_stats()
        recent_alerts = self.get_recent_alerts()

        data = {
            'overall_stats': asdict(stats) if stats else None,
            'axis_stats': axis_stats,
            'trend': self.get_trend(),
            'is_abnormal': self.is_abnormal(),
            'total_samples': self.total_samples,
            'uptime_seconds': time.time() - self.start_time,
            'recent_alerts': [asdict(alert) for alert in recent_alerts],
            'alert_thresholds': self.alert_thresholds
        }

        return json.dumps(data, indent=2)

    def get_summary(self) -> Dict[str, Any]:
        """Get summary dictionary for display"""
        stats = self.get_current_stats()

        return {
            'current_magnitude': self.magnitude_buffer[-1] if self.magnitude_buffer else 0.0,
            'mean_magnitude': stats.mean_magnitude if stats else 0.0,
            'max_magnitude': stats.max_magnitude if stats else 0.0,
            'rms_value': stats.rms_value if stats else 0.0,
            'trend': self.get_trend(),
            'is_abnormal': self.is_abnormal(),
            'alert_count': len(self.alerts),
            'sample_count': self.total_samples
        }
