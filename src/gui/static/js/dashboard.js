// Dashboard JavaScript

class MonitoringDashboard {
    constructor() {
        this.updateInterval = 1000; // Update every 1 second
        this.updateTimer = null;
        this.manualOverride = false;

        this.init();
    }

    init() {
        console.log('Initializing dashboard...');

        // Set up event listeners
        this.setupEventListeners();

        // Start periodic updates
        this.startUpdates();

        // Update current time
        this.updateCurrentTime();
        setInterval(() => this.updateCurrentTime(), 1000);
    }

    setupEventListeners() {
        // Service control buttons
        document.querySelectorAll('.service-start').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const serviceId = e.target.getAttribute('data-service');
                this.startService(serviceId);
            });
        });

        document.querySelectorAll('.service-stop').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const serviceId = e.target.getAttribute('data-service');
                this.stopService(serviceId);
            });
        });

        // Bulk controls
        document.getElementById('start-all-btn').addEventListener('click', () => {
            this.startAllServices();
        });

        document.getElementById('stop-all-btn').addEventListener('click', () => {
            this.stopAllServices();
        });

        // Scheduler controls
        document.getElementById('toggle-override-btn').addEventListener('click', () => {
            this.toggleManualOverride();
        });

        document.getElementById('edit-schedule-btn').addEventListener('click', () => {
            this.showScheduleModal();
        });

        // Modal controls
        const modal = document.getElementById('schedule-modal');
        const closeBtn = modal.querySelector('.close');

        closeBtn.addEventListener('click', () => {
            modal.style.display = 'none';
        });

        window.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });

        // Schedule form
        document.getElementById('schedule-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveSchedule();
        });
    }

    startUpdates() {
        this.updateTimer = setInterval(() => {
            this.fetchStatus();
        }, this.updateInterval);

        // Initial fetch
        this.fetchStatus();
    }

    stopUpdates() {
        if (this.updateTimer) {
            clearInterval(this.updateTimer);
        }
    }

    async fetchStatus() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();

            if (data.error) {
                console.error('Status error:', data.error);
                return;
            }

            this.updateUI(data);
            document.getElementById('last-update').textContent = new Date().toLocaleTimeString();

        } catch (error) {
            console.error('Failed to fetch status:', error);
        }
    }

    updateUI(data) {
        // Update system status
        const statusBadge = document.getElementById('system-status');
        if (data.initialized) {
            statusBadge.textContent = 'Online';
            statusBadge.classList.add('online');
        }

        // Update services
        if (data.services) {
            data.services.forEach(service => {
                this.updateServiceUI(service);
            });
        }

        // Update scheduler
        if (data.scheduler) {
            this.updateSchedulerUI(data.scheduler);
        }

        // Update vibration monitoring
        if (data.vibration) {
            this.updateVibrationUI(data.vibration);
        }

        // Update alerts
        if (data.alerts) {
            this.updateAlertsUI(data.alerts);
        }
    }

    updateServiceUI(service) {
        const indicator = document.getElementById(`${service.service_id}-status-indicator`);
        const text = document.getElementById(`${service.service_id}-status-text`);

        if (indicator && text) {
            // Update indicator
            indicator.className = 'status-indicator';

            if (service.status === 'running') {
                indicator.classList.add('running');
                text.textContent = 'Running';
            } else if (service.status === 'stopped') {
                indicator.classList.add('stopped');
                text.textContent = 'Stopped';
            } else if (service.status === 'error') {
                indicator.classList.add('error');
                text.textContent = 'Error';
            } else {
                text.textContent = service.status;
            }

            // Show error message if present
            if (service.error_message) {
                text.textContent += ` (${service.error_message})`;
            }
        }
    }

    updateSchedulerUI(scheduler) {
        document.getElementById('scheduler-status').textContent =
            scheduler.scheduler_running ? 'Active' : 'Inactive';

        document.getElementById('work-hours').textContent =
            `${scheduler.schedule.start} - ${scheduler.schedule.end}`;

        document.getElementById('is-work-time').textContent =
            scheduler.is_work_time ? '✅ Yes' : '❌ No';

        document.getElementById('auto-mode').textContent =
            scheduler.manual_override ? '❌ Disabled (Manual)' : '✅ Enabled';

        // Update next event
        let nextEvent = '--';
        if (scheduler.minutes_until_start !== null) {
            const hours = Math.floor(scheduler.minutes_until_start / 60);
            const mins = scheduler.minutes_until_start % 60;
            nextEvent = `Start in ${hours}h ${mins}m`;
        } else if (scheduler.minutes_until_end !== null) {
            const hours = Math.floor(scheduler.minutes_until_end / 60);
            const mins = scheduler.minutes_until_end % 60;
            nextEvent = `End in ${hours}h ${mins}m`;
        }
        document.getElementById('next-event').textContent = nextEvent;

        this.manualOverride = scheduler.manual_override;
        const overrideBtn = document.getElementById('toggle-override-btn');
        overrideBtn.textContent = this.manualOverride ? 'Disable Override' : 'Enable Override';
    }

    updateVibrationUI(vibration) {
        if (!vibration.latest_reading) return;

        const latest = vibration.latest_reading;
        const analysis = vibration.analysis;

        // Update metric cards
        document.getElementById('vib-current').textContent =
            `${latest.magnitude.toFixed(2)} m/s²`;

        if (vibration.statistics) {
            document.getElementById('vib-mean').textContent =
                `${vibration.statistics.mean_magnitude.toFixed(2)} m/s²`;
            document.getElementById('vib-max').textContent =
                `${vibration.statistics.max_magnitude.toFixed(2)} m/s²`;
            document.getElementById('vib-rms').textContent =
                `${vibration.statistics.rms_value.toFixed(2)} m/s²`;
        }

        if (analysis) {
            document.getElementById('vib-trend').textContent = analysis.trend;
            document.getElementById('vib-samples').textContent = analysis.sample_count;
        }

        // Update axis bars
        const maxVal = 20; // m/s² - max scale for visualization
        this.updateAxisBar('x', latest.x_axis, maxVal);
        this.updateAxisBar('y', latest.y_axis, maxVal);
        this.updateAxisBar('z', latest.z_axis, maxVal);
    }

    updateAxisBar(axis, value, maxVal) {
        const percentage = Math.min(Math.abs(value) / maxVal * 100, 100);
        const bar = document.getElementById(`${axis}-axis-bar`);
        const valueSpan = document.getElementById(`${axis}-axis-value`);

        if (bar && valueSpan) {
            bar.style.width = `${percentage}%`;
            valueSpan.textContent = value.toFixed(2);

            // Color based on magnitude
            if (Math.abs(value) < 2) {
                bar.style.background = '#10b981'; // Green
            } else if (Math.abs(value) < 5) {
                bar.style.background = '#f59e0b'; // Yellow
            } else if (Math.abs(value) < 10) {
                bar.style.background = '#ef4444'; // Red
            } else {
                bar.style.background = '#7c3aed'; // Purple
            }
        }
    }

    updateAlertsUI(alerts) {
        const alertsList = document.getElementById('alerts-list');

        if (!alerts || alerts.length === 0) {
            alertsList.innerHTML = '<div class="no-alerts">No alerts</div>';
            return;
        }

        alertsList.innerHTML = '';

        // Show most recent alerts first
        [...alerts].reverse().forEach(alert => {
            const alertItem = document.createElement('div');
            alertItem.className = `alert-item severity-${alert.severity}`;

            const time = new Date(alert.timestamp * 1000).toLocaleTimeString();

            alertItem.innerHTML = `
                <div class="alert-header">
                    <span class="alert-type">${alert.severity} - ${alert.type}</span>
                    <span class="alert-time">${time}</span>
                </div>
                <div class="alert-message">${alert.message}</div>
            `;

            alertsList.appendChild(alertItem);
        });
    }

    updateCurrentTime() {
        const now = new Date();
        document.getElementById('current-time').textContent = now.toLocaleTimeString();
    }

    // API Calls

    async startService(serviceId) {
        try {
            const response = await fetch(`/api/service/${serviceId}/start`, {
                method: 'POST'
            });
            const data = await response.json();

            if (data.success) {
                console.log(`Service ${serviceId} started`);
            } else {
                console.error(`Failed to start service ${serviceId}`);
            }

            // Force immediate update
            this.fetchStatus();

        } catch (error) {
            console.error('Error starting service:', error);
        }
    }

    async stopService(serviceId) {
        try {
            const response = await fetch(`/api/service/${serviceId}/stop`, {
                method: 'POST'
            });
            const data = await response.json();

            if (data.success) {
                console.log(`Service ${serviceId} stopped`);
            }

            this.fetchStatus();

        } catch (error) {
            console.error('Error stopping service:', error);
        }
    }

    async startAllServices() {
        try {
            const response = await fetch('/api/services/start_all', {
                method: 'POST'
            });
            const data = await response.json();

            if (data.success) {
                console.log('All services started');
            }

            this.fetchStatus();

        } catch (error) {
            console.error('Error starting all services:', error);
        }
    }

    async stopAllServices() {
        try {
            const response = await fetch('/api/services/stop_all', {
                method: 'POST'
            });
            const data = await response.json();

            if (data.success) {
                console.log('All services stopped');
            }

            this.fetchStatus();

        } catch (error) {
            console.error('Error stopping all services:', error);
        }
    }

    async toggleManualOverride() {
        try {
            const response = await fetch('/api/scheduler/override', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    enable: !this.manualOverride
                })
            });

            const data = await response.json();

            if (data.success) {
                console.log('Manual override toggled');
            }

            this.fetchStatus();

        } catch (error) {
            console.error('Error toggling override:', error);
        }
    }

    showScheduleModal() {
        const modal = document.getElementById('schedule-modal');
        modal.style.display = 'block';
    }

    async saveSchedule() {
        const startTime = document.getElementById('schedule-start').value;
        const endTime = document.getElementById('schedule-end').value;

        const enabledDays = [];
        document.querySelectorAll('input[name="day"]:checked').forEach(checkbox => {
            enabledDays.push(parseInt(checkbox.value));
        });

        try {
            const response = await fetch('/api/scheduler/update', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    start_time: startTime,
                    end_time: endTime,
                    enabled_days: enabledDays
                })
            });

            const data = await response.json();

            if (data.success) {
                console.log('Schedule updated');
                document.getElementById('schedule-modal').style.display = 'none';
            }

            this.fetchStatus();

        } catch (error) {
            console.error('Error saving schedule:', error);
        }
    }
}

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new MonitoringDashboard();
});
