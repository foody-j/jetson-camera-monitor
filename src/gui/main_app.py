"""
Centralized Monitoring Dashboard

Web-based GUI for monitoring all systems:
- Camera monitoring
- Vibration detection
- Frying AI
- Work scheduler
"""

import sys
import os
from pathlib import Path

# Add parent directories to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from flask import Flask, render_template, jsonify, request, Response
import logging
import json
import time
from typing import Dict, Any, Optional
import threading

# Import monitoring modules
from monitoring.vibration import VibrationDetector
from scheduler import WorkScheduler, ServiceManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__,
            template_folder='templates',
            static_folder='static')


class MonitoringSystem:
    """
    Centralized monitoring system coordinator

    Manages all monitoring services and provides unified interface
    """

    def __init__(self, config_path: str = 'config/system_config.json'):
        """Initialize monitoring system"""
        self.config_path = config_path
        self.config = self._load_config()

        # Initialize components
        self.service_manager = ServiceManager()
        self.work_scheduler: Optional[WorkScheduler] = None
        self.vibration_detector: Optional[VibrationDetector] = None

        # System state
        self.initialized = False
        self.system_alerts = []

    def _load_config(self) -> Dict[str, Any]:
        """Load system configuration"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        else:
            logger.warning(f"Config file not found: {self.config_path}")
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'vibration': {
                'enabled': True,
                'sensor': {
                    'port': '/dev/ttyUSB0',
                    'baudrate': 9600,
                    'protocol': 'modbus',
                    'slave_address': 1,
                    'timeout': 1.0
                },
                'analyzer': {
                    'window_size': 100,
                    'alert_thresholds': {
                        'low': 2.0,
                        'medium': 5.0,
                        'high': 10.0,
                        'critical': 20.0
                    }
                },
                'log_directory': 'data/vibration_logs',
                'sampling_rate': 10.0
            },
            'camera': {
                'enabled': True,
                'index': 0,
                'resolution': {'width': 640, 'height': 360},
                'fps': 30
            },
            'frying_ai': {
                'enabled': True,
                'fps': 2
            },
            'scheduler': {
                'enabled': True,
                'work_hours': {
                    'start': '08:30',
                    'end': '19:00',
                    'enabled_days': [0, 1, 2, 3, 4, 5, 6]
                },
                'grace_period_minutes': 5,
                'auto_start_enabled': True,
                'auto_stop_enabled': True
            },
            'web_server': {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False
            }
        }

    def initialize(self) -> bool:
        """Initialize all monitoring systems"""
        logger.info("Initializing monitoring system...")

        try:
            # Initialize vibration monitoring
            if self.config['vibration']['enabled']:
                self.vibration_detector = VibrationDetector(
                    sensor_config=self.config['vibration']['sensor'],
                    analyzer_config=self.config['vibration']['analyzer'],
                    log_directory=self.config['vibration']['log_directory'],
                    sampling_rate=self.config['vibration']['sampling_rate']
                )

                if self.vibration_detector.initialize():
                    self.service_manager.register_service('vibration', self.vibration_detector)
                    logger.info("Vibration monitoring initialized")
                else:
                    logger.warning("Failed to initialize vibration monitoring")

            # Initialize work scheduler
            if self.config['scheduler']['enabled']:
                self.work_scheduler = WorkScheduler(self.config['scheduler'])
                self.work_scheduler.set_callbacks(
                    start_callback=self._start_all_services,
                    stop_callback=self._stop_all_services
                )
                self.work_scheduler.start_scheduler()
                logger.info("Work scheduler initialized")

            self.initialized = True
            logger.info("Monitoring system initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize monitoring system: {e}")
            return False

    def _start_all_services(self) -> bool:
        """Start all monitoring services"""
        return self.service_manager.start_all_services()

    def _stop_all_services(self) -> None:
        """Stop all monitoring services"""
        self.service_manager.stop_all_services()

    def get_system_status(self) -> Dict[str, Any]:
        """Get complete system status"""
        status = {
            'initialized': self.initialized,
            'timestamp': time.time(),
            'services': self.service_manager.get_all_statuses(),
            'scheduler': None,
            'vibration': None,
            'alerts': self.system_alerts[-10:]  # Last 10 alerts
        }

        # Add scheduler status
        if self.work_scheduler:
            status['scheduler'] = self.work_scheduler.get_status()

        # Add vibration status
        if self.vibration_detector and self.vibration_detector.is_monitoring:
            status['vibration'] = self.vibration_detector.get_current_status()

        return status

    def cleanup(self) -> None:
        """Cleanup all resources"""
        logger.info("Cleaning up monitoring system...")

        if self.work_scheduler:
            self.work_scheduler.stop_scheduler()

        self.service_manager.stop_all_services()

        if self.vibration_detector:
            self.vibration_detector.cleanup()

        logger.info("Cleanup complete")


# Global monitoring system instance
monitoring_system: Optional[MonitoringSystem] = None


# Flask Routes

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')


@app.route('/api/status')
def api_status():
    """Get current system status (polled by frontend)"""
    if monitoring_system is None:
        return jsonify({'error': 'System not initialized'}), 500

    return jsonify(monitoring_system.get_system_status())


@app.route('/api/service/<service_id>/start', methods=['POST'])
def api_start_service(service_id):
    """Start a specific service"""
    if monitoring_system is None:
        return jsonify({'error': 'System not initialized'}), 500

    success = monitoring_system.service_manager.start_service(service_id)
    return jsonify({'success': success, 'service_id': service_id})


@app.route('/api/service/<service_id>/stop', methods=['POST'])
def api_stop_service(service_id):
    """Stop a specific service"""
    if monitoring_system is None:
        return jsonify({'error': 'System not initialized'}), 500

    monitoring_system.service_manager.stop_service(service_id)
    return jsonify({'success': True, 'service_id': service_id})


@app.route('/api/services/start_all', methods=['POST'])
def api_start_all_services():
    """Start all services"""
    if monitoring_system is None:
        return jsonify({'error': 'System not initialized'}), 500

    success = monitoring_system.service_manager.start_all_services()
    return jsonify({'success': success})


@app.route('/api/services/stop_all', methods=['POST'])
def api_stop_all_services():
    """Stop all services"""
    if monitoring_system is None:
        return jsonify({'error': 'System not initialized'}), 500

    monitoring_system.service_manager.stop_all_services()
    return jsonify({'success': True})


@app.route('/api/scheduler/override', methods=['POST'])
def api_scheduler_override():
    """Enable/disable scheduler manual override"""
    if monitoring_system is None or monitoring_system.work_scheduler is None:
        return jsonify({'error': 'Scheduler not available'}), 500

    data = request.json
    enable = data.get('enable', True)

    if enable:
        monitoring_system.work_scheduler.enable_manual_override()
    else:
        monitoring_system.work_scheduler.disable_manual_override()

    return jsonify({'success': True, 'manual_override': enable})


@app.route('/api/scheduler/update', methods=['POST'])
def api_update_schedule():
    """Update work schedule"""
    if monitoring_system is None or monitoring_system.work_scheduler is None:
        return jsonify({'error': 'Scheduler not available'}), 500

    data = request.json
    monitoring_system.work_scheduler.update_schedule(
        start_time=data.get('start_time'),
        end_time=data.get('end_time'),
        enabled_days=data.get('enabled_days')
    )

    return jsonify({'success': True})


@app.route('/api/vibration/latest')
def api_vibration_latest():
    """Get latest vibration reading"""
    if monitoring_system is None or monitoring_system.vibration_detector is None:
        return jsonify({'error': 'Vibration monitoring not available'}), 500

    latest = monitoring_system.vibration_detector.latest_reading

    if latest is None:
        return jsonify({'error': 'No reading available'}), 404

    return jsonify({
        'timestamp': latest.timestamp,
        'x_axis': latest.x_axis,
        'y_axis': latest.y_axis,
        'z_axis': latest.z_axis,
        'magnitude': latest.magnitude,
        'temperature': latest.temperature,
        'frequency': latest.frequency
    })


def main():
    """Main entry point"""
    global monitoring_system

    # Initialize monitoring system
    config_path = os.path.join(project_root, 'config', 'system_config.json')
    monitoring_system = MonitoringSystem(config_path=config_path)

    if not monitoring_system.initialize():
        logger.error("Failed to initialize monitoring system")
        return

    # Get web server config
    web_config = monitoring_system.config['web_server']

    try:
        logger.info(f"Starting web server on {web_config['host']}:{web_config['port']}")
        app.run(
            host=web_config['host'],
            port=web_config['port'],
            debug=web_config['debug'],
            threaded=True
        )
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        monitoring_system.cleanup()


if __name__ == '__main__':
    main()
