#!/usr/bin/env python3
"""
Dash-based Monitoring Dashboard

Beautiful, modern dashboard using Plotly Dash for real-time monitoring
of all systems: Camera, Vibration, Frying AI, and Work Scheduler.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import logging
import json
import time
from typing import Dict, Any, Optional, List
from collections import deque
from datetime import datetime

# Import monitoring modules
from monitoring.vibration import VibrationDetector
from monitoring.camera import CameraBase
from monitoring.frying import FryingDataCollector
from scheduler import WorkScheduler, ServiceManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== Data Management ====================

class DashboardData:
    """Manages real-time data for dashboard"""

    def __init__(self, max_points: int = 300):
        self.max_points = max_points

        # Vibration data buffers (for live charts)
        self.vib_time = deque(maxlen=max_points)
        self.vib_x = deque(maxlen=max_points)
        self.vib_y = deque(maxlen=max_points)
        self.vib_z = deque(maxlen=max_points)
        self.vib_magnitude = deque(maxlen=max_points)

        # System status
        self.system_status = {
            'initialized': False,
            'services': [],
            'scheduler': None,
            'vibration': None,
            'alerts': []
        }

    def update_vibration(self, reading):
        """Update vibration data buffers"""
        if reading:
            current_time = datetime.fromtimestamp(reading.timestamp)
            self.vib_time.append(current_time)
            self.vib_x.append(reading.x_axis)
            self.vib_y.append(reading.y_axis)
            self.vib_z.append(reading.z_axis)
            self.vib_magnitude.append(reading.magnitude)

    def update_status(self, status: Dict[str, Any]):
        """Update system status"""
        self.system_status = status

        # Update vibration data if available
        if status.get('vibration') and status['vibration'].get('latest_reading'):
            reading_dict = status['vibration']['latest_reading']

            # Create a simple object to hold the data
            class Reading:
                def __init__(self, data):
                    self.timestamp = data['timestamp']
                    self.x_axis = data['x_axis']
                    self.y_axis = data['y_axis']
                    self.z_axis = data['z_axis']
                    self.magnitude = data['magnitude']

            self.update_vibration(Reading(reading_dict))


# Global instances
dashboard_data = DashboardData()
monitoring_system = None


# ==================== Monitoring System ====================

class MonitoringSystem:
    """Centralized monitoring system (same as Flask version)"""

    def __init__(self, config_path: str = 'config/system_config.json'):
        self.config_path = config_path
        self.config = self._load_config()

        self.service_manager = ServiceManager()
        self.work_scheduler: Optional[WorkScheduler] = None
        self.vibration_detector: Optional[VibrationDetector] = None
        self.camera: Optional[CameraBase] = None
        self.frying_collector: Optional[FryingDataCollector] = None

        self.initialized = False
        self.system_alerts = []

    def _load_config(self) -> Dict[str, Any]:
        """Load system configuration"""
        config_file = os.path.join(project_root, self.config_path)
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)
        else:
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
                'resolution': {
                    'width': 640,
                    'height': 360
                },
                'fps': 30,
                'name': 'Default Camera'
            },
            'frying_ai': {
                'enabled': True,
                'fps': 2,
                'log_directory': 'data/frying_dataset'
            },
            'scheduler': {
                'enabled': True,
                'work_hours': {
                    'start': '08:30',
                    'end': '19:00',
                    'enabled_days': [0, 1, 2, 3, 4, 5, 6]
                },
                'auto_start_enabled': True,
                'auto_stop_enabled': True
            }
        }

    def initialize(self) -> bool:
        """Initialize all monitoring systems"""
        logger.info("Initializing monitoring system...")

        try:
            # Initialize camera monitoring
            if self.config.get('camera', {}).get('enabled', True):
                cam_config = self.config['camera']
                resolution = (
                    cam_config['resolution']['width'],
                    cam_config['resolution']['height']
                )
                self.camera = CameraBase(
                    camera_index=cam_config['index'],
                    resolution=resolution
                )

                if self.camera.initialize():
                    self.service_manager.register_service('camera', self.camera)
                    logger.info("Camera monitoring initialized")
                else:
                    logger.warning("Camera initialization failed, but continuing...")

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

            # Initialize frying AI data collector
            if self.config.get('frying_ai', {}).get('enabled', True):
                frying_config = self.config['frying_ai']
                self.frying_collector = FryingDataCollector(
                    base_dir=frying_config['log_directory'],
                    fps=frying_config['fps']
                )

                if self.frying_collector.initialize():
                    self.service_manager.register_service('frying', self.frying_collector)
                    logger.info("Frying AI data collector initialized")
                else:
                    logger.warning("Frying AI initialization failed, but continuing...")

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
            'alerts': self.system_alerts[-10:]
        }

        if self.work_scheduler:
            status['scheduler'] = self.work_scheduler.get_status()

        if self.vibration_detector and self.vibration_detector.is_monitoring:
            status['vibration'] = self.vibration_detector.get_current_status()

        return status

    def cleanup(self) -> None:
        """Cleanup all resources"""
        logger.info("Cleaning up monitoring system...")

        if self.work_scheduler:
            self.work_scheduler.stop_scheduler()

        self.service_manager.stop_all_services()

        if self.camera:
            self.camera.release()

        if self.vibration_detector:
            self.vibration_detector.cleanup()

        if self.frying_collector:
            self.frying_collector.cleanup()

        logger.info("Cleanup complete")


# ==================== Dash App Layout ====================

# Initialize Dash app with Bootstrap theme
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG],  # Dark theme
    suppress_callback_exceptions=True
)

app.title = "Frying AI Monitoring System"


def create_header():
    """Create header component"""
    return dbc.Navbar(
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.H3("🤖 Frying AI Monitoring System", className="text-white mb-0")
                ], width="auto"),
                dbc.Col([
                    html.Div([
                        html.Span(id="current-time", className="text-white me-3"),
                        dbc.Badge("Online", id="system-status-badge", color="success", className="me-2")
                    ], className="d-flex align-items-center justify-content-end")
                ], width="auto", className="ms-auto")
            ], className="w-100 align-items-center")
        ], fluid=True),
        color="dark",
        dark=True,
        className="mb-4"
    )


def create_service_card(service_id: str, service_name: str, icon: str):
    """Create service control card"""
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.Span(icon, className="fs-1 me-2"),
                html.H6(service_name, className="mb-0")
            ], className="d-flex align-items-center mb-3"),
            html.Div([
                dbc.Badge("Stopped", id=f"{service_id}-status", color="secondary", className="me-2"),
                html.Span("", id=f"{service_id}-status-text", className="text-muted small")
            ], className="mb-3"),
            dbc.ButtonGroup([
                dbc.Button("Start", id=f"{service_id}-start-btn", color="success", size="sm", className="me-1"),
                dbc.Button("Stop", id=f"{service_id}-stop-btn", color="danger", size="sm")
            ], className="w-100")
        ])
    ], className="h-100")


def create_layout():
    """Create main dashboard layout"""
    return dbc.Container([
        # Header
        create_header(),

        # Main content
        dbc.Row([
            # Left column - Services and Scheduler
            dbc.Col([
                # Work Scheduler Card
                dbc.Card([
                    dbc.CardHeader(html.H5("⏰ Work Scheduler", className="mb-0")),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.Small("Status:", className="text-muted"),
                                html.Div(id="scheduler-status", className="fw-bold")
                            ], width=6),
                            dbc.Col([
                                html.Small("Work Hours:", className="text-muted"),
                                html.Div(id="work-hours", className="fw-bold")
                            ], width=6)
                        ], className="mb-2"),
                        dbc.Row([
                            dbc.Col([
                                html.Small("Is Work Time:", className="text-muted"),
                                html.Div(id="is-work-time", className="fw-bold")
                            ], width=6),
                            dbc.Col([
                                html.Small("Auto Mode:", className="text-muted"),
                                html.Div(id="auto-mode", className="fw-bold")
                            ], width=6)
                        ], className="mb-3"),
                        html.Div([
                            html.Small("Next Event:", className="text-muted"),
                            html.Div(id="next-event", className="fw-bold text-info")
                        ], className="mb-3"),
                        dbc.ButtonGroup([
                            dbc.Button("Manual Override", id="toggle-override-btn", color="warning", size="sm"),
                            dbc.Button("Edit Schedule", id="edit-schedule-btn", color="secondary", size="sm")
                        ], className="w-100")
                    ])
                ], className="mb-3"),

                # Services Control Card
                dbc.Card([
                    dbc.CardHeader(html.H5("🎛️ Services Control", className="mb-0")),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col(create_service_card("camera", "Camera", "📷"), md=12, lg=4, className="mb-3"),
                            dbc.Col(create_service_card("vibration", "Vibration", "📊"), md=12, lg=4, className="mb-3"),
                            dbc.Col(create_service_card("frying", "Frying AI", "🍟"), md=12, lg=4, className="mb-3")
                        ]),
                        html.Hr(),
                        dbc.ButtonGroup([
                            dbc.Button("Start All Services", id="start-all-btn", color="success", className="me-2"),
                            dbc.Button("Stop All Services", id="stop-all-btn", color="danger")
                        ], className="w-100")
                    ])
                ])
            ], lg=6, className="mb-3"),

            # Right column - Vibration Monitoring
            dbc.Col([
                # Vibration Metrics Card
                dbc.Card([
                    dbc.CardHeader(html.H5("📊 Vibration Monitoring", className="mb-0")),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardBody([
                                        html.Small("Current", className="text-muted d-block"),
                                        html.H4(id="vib-current", className="mb-0 text-primary")
                                    ])
                                ], className="text-center")
                            ], width=3),
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardBody([
                                        html.Small("Mean", className="text-muted d-block"),
                                        html.H4(id="vib-mean", className="mb-0 text-info")
                                    ])
                                ], className="text-center")
                            ], width=3),
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardBody([
                                        html.Small("Max", className="text-muted d-block"),
                                        html.H4(id="vib-max", className="mb-0 text-warning")
                                    ])
                                ], className="text-center")
                            ], width=3),
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardBody([
                                        html.Small("RMS", className="text-muted d-block"),
                                        html.H4(id="vib-rms", className="mb-0 text-success")
                                    ])
                                ], className="text-center")
                            ], width=3)
                        ], className="mb-3"),

                        # Live chart
                        dcc.Graph(id="vibration-chart", config={'displayModeBar': False})
                    ])
                ], className="mb-3"),

                # Alerts Card
                dbc.Card([
                    dbc.CardHeader(html.H5("⚠️ Recent Alerts", className="mb-0")),
                    dbc.CardBody([
                        html.Div(id="alerts-container", style={'maxHeight': '300px', 'overflowY': 'auto'})
                    ])
                ])
            ], lg=6)
        ]),

        # Update interval
        dcc.Interval(id='update-interval', interval=1000, n_intervals=0),  # 1 second

        # Hidden div for storing state
        html.Div(id='hidden-div', style={'display': 'none'})

    ], fluid=True, className="py-3")


app.layout = create_layout()


# ==================== Callbacks ====================

@app.callback(
    [
        Output('current-time', 'children'),
        Output('system-status-badge', 'children'),
        Output('system-status-badge', 'color'),
        Output('scheduler-status', 'children'),
        Output('work-hours', 'children'),
        Output('is-work-time', 'children'),
        Output('auto-mode', 'children'),
        Output('next-event', 'children'),
        Output('camera-status', 'children'),
        Output('camera-status', 'color'),
        Output('vibration-status', 'children'),
        Output('vibration-status', 'color'),
        Output('frying-status', 'children'),
        Output('frying-status', 'color'),
        Output('vib-current', 'children'),
        Output('vib-mean', 'children'),
        Output('vib-max', 'children'),
        Output('vib-rms', 'children'),
        Output('vibration-chart', 'figure'),
        Output('alerts-container', 'children')
    ],
    Input('update-interval', 'n_intervals')
)
def update_dashboard(n):
    """Update all dashboard components"""
    global monitoring_system, dashboard_data

    if monitoring_system is None:
        # Return default values
        return (
            datetime.now().strftime("%H:%M:%S"),
            "Initializing", "warning",
            "--", "--", "--", "--", "--",
            "Stopped", "secondary",
            "Stopped", "secondary",
            "Stopped", "secondary",
            "0.00 m/s²", "0.00 m/s²", "0.00 m/s²", "0.00 m/s²",
            create_empty_chart(),
            html.Div("No alerts", className="text-muted text-center")
        )

    # Get system status
    status = monitoring_system.get_system_status()
    dashboard_data.update_status(status)

    # Current time
    current_time = datetime.now().strftime("%H:%M:%S")

    # System status
    sys_status = "Online" if status['initialized'] else "Offline"
    sys_color = "success" if status['initialized'] else "danger"

    # Scheduler info
    scheduler = status.get('scheduler', {})
    sched_status = "Active" if scheduler.get('scheduler_running') else "Inactive"
    work_hours = f"{scheduler.get('schedule', {}).get('start', '--')} - {scheduler.get('schedule', {}).get('end', '--')}"
    is_work = "✅ Yes" if scheduler.get('is_work_time') else "❌ No"
    auto_mode = "❌ Manual" if scheduler.get('manual_override') else "✅ Auto"

    # Next event
    next_event = "--"
    if scheduler.get('minutes_until_start') is not None:
        mins = scheduler['minutes_until_start']
        next_event = f"Start in {mins//60}h {mins%60}m"
    elif scheduler.get('minutes_until_end') is not None:
        mins = scheduler['minutes_until_end']
        next_event = f"End in {mins//60}h {mins%60}m"

    # Service statuses
    services = {s['service_id']: s for s in status.get('services', [])}

    def get_service_status(service_id):
        s = services.get(service_id, {})
        status_text = s.get('status', 'stopped').capitalize()
        color = 'success' if s.get('status') == 'running' else 'secondary'
        return status_text, color

    cam_text, cam_color = get_service_status('camera')
    vib_text, vib_color = get_service_status('vibration')
    fry_text, fry_color = get_service_status('frying')

    # Vibration metrics
    vib_data = status.get('vibration', {})
    vib_analysis = vib_data.get('analysis', {})
    vib_stats = vib_data.get('statistics', {})

    vib_current = f"{vib_analysis.get('current_magnitude', 0):.2f} m/s²"
    vib_mean = f"{vib_stats.get('mean_magnitude', 0):.2f} m/s²"
    vib_max = f"{vib_stats.get('max_magnitude', 0):.2f} m/s²"
    vib_rms = f"{vib_stats.get('rms_value', 0):.2f} m/s²"

    # Vibration chart
    chart = create_vibration_chart()

    # Alerts
    alerts = create_alerts_list(status.get('alerts', []))

    return (
        current_time,
        sys_status, sys_color,
        sched_status, work_hours, is_work, auto_mode, next_event,
        cam_text, cam_color,
        vib_text, vib_color,
        fry_text, fry_color,
        vib_current, vib_mean, vib_max, vib_rms,
        chart,
        alerts
    )


def create_vibration_chart():
    """Create vibration time-series chart"""
    global dashboard_data

    if len(dashboard_data.vib_time) == 0:
        return create_empty_chart()

    fig = go.Figure()

    # Add traces for each axis
    fig.add_trace(go.Scatter(
        x=list(dashboard_data.vib_time),
        y=list(dashboard_data.vib_x),
        name='X-axis',
        line=dict(color='#FF6B6B', width=2)
    ))

    fig.add_trace(go.Scatter(
        x=list(dashboard_data.vib_time),
        y=list(dashboard_data.vib_y),
        name='Y-axis',
        line=dict(color='#4ECDC4', width=2)
    ))

    fig.add_trace(go.Scatter(
        x=list(dashboard_data.vib_time),
        y=list(dashboard_data.vib_z),
        name='Z-axis',
        line=dict(color='#45B7D1', width=2)
    ))

    fig.add_trace(go.Scatter(
        x=list(dashboard_data.vib_time),
        y=list(dashboard_data.vib_magnitude),
        name='Magnitude',
        line=dict(color='#FFA07A', width=3)
    ))

    fig.update_layout(
        title="Vibration Time Series",
        xaxis_title="Time",
        yaxis_title="Acceleration (m/s²)",
        template="plotly_dark",
        height=300,
        margin=dict(l=50, r=20, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode='x unified'
    )

    return fig


def create_empty_chart():
    """Create empty chart placeholder"""
    fig = go.Figure()
    fig.add_annotation(
        text="No data available",
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=20, color="gray")
    )
    fig.update_layout(
        template="plotly_dark",
        height=300,
        margin=dict(l=50, r=20, t=40, b=40)
    )
    return fig


def create_alerts_list(alerts: List[Dict[str, Any]]):
    """Create alerts list component"""
    if not alerts:
        return html.Div("No alerts", className="text-muted text-center")

    alert_items = []
    for alert in reversed(alerts[-10:]):  # Last 10, most recent first
        severity = alert.get('severity', 'low')
        color_map = {
            'low': 'success',
            'medium': 'warning',
            'high': 'danger',
            'critical': 'danger'
        }

        alert_time = datetime.fromtimestamp(alert['timestamp']).strftime("%H:%M:%S")

        alert_items.append(
            dbc.Alert([
                html.Div([
                    html.Strong(f"{severity.upper()} - {alert.get('type', 'alert').upper()}", className="me-2"),
                    html.Small(alert_time, className="text-muted")
                ], className="d-flex justify-content-between mb-1"),
                html.Div(alert.get('message', ''), className="small")
            ], color=color_map.get(severity, 'secondary'), className="mb-2")
        )

    return html.Div(alert_items)


# Service control callbacks
for service_id in ['camera', 'vibration', 'frying']:
    @app.callback(
        Output(f'{service_id}-start-btn', 'n_clicks'),
        Input(f'{service_id}-start-btn', 'n_clicks'),
        prevent_initial_call=True
    )
    def start_service(n_clicks, sid=service_id):
        if n_clicks and monitoring_system:
            monitoring_system.service_manager.start_service(sid)
        return n_clicks


@app.callback(
    Output('start-all-btn', 'n_clicks'),
    Input('start-all-btn', 'n_clicks'),
    prevent_initial_call=True
)
def start_all(n_clicks):
    if n_clicks and monitoring_system:
        monitoring_system.service_manager.start_all_services()
    return n_clicks


@app.callback(
    Output('stop-all-btn', 'n_clicks'),
    Input('stop-all-btn', 'n_clicks'),
    prevent_initial_call=True
)
def stop_all(n_clicks):
    if n_clicks and monitoring_system:
        monitoring_system.service_manager.stop_all_services()
    return n_clicks


# ==================== Main ====================

def main():
    """Main entry point"""
    global monitoring_system

    print("=" * 60)
    print("🤖 Frying AI Monitoring System (Dash)")
    print("=" * 60)
    print()

    # Initialize monitoring system
    config_path = os.path.join(project_root, 'config', 'system_config.json')
    monitoring_system = MonitoringSystem(config_path=config_path)

    if not monitoring_system.initialize():
        logger.error("Failed to initialize monitoring system")
        return

    print("✓ Monitoring system initialized")
    print()
    print("Starting Dash server...")
    print("Access dashboard at: http://localhost:8050")
    print()
    print("Features:")
    print("  ✓ Real-time vibration charts")
    print("  ✓ Service control")
    print("  ✓ Work scheduler")
    print("  ✓ Live alerts")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 60)
    print()

    try:
        app.run(
            debug=False,
            host='0.0.0.0',
            port=8050
        )
    except KeyboardInterrupt:
        print("\n\nShutdown requested")
    finally:
        monitoring_system.cleanup()


if __name__ == '__main__':
    main()
