"""
Work Scheduler

Manages automatic startup and shutdown of monitoring services
based on configured work hours.
"""

import time
import logging
from datetime import datetime, time as dt_time
from typing import Dict, Any, Callable, Optional, List
from dataclasses import dataclass
import threading

logger = logging.getLogger(__name__)


@dataclass
class WorkSchedule:
    """Work schedule configuration"""
    start_hour: int      # 0-23
    start_minute: int    # 0-59
    end_hour: int        # 0-23
    end_minute: int      # 0-59
    enabled_days: List[int]  # 0=Monday, 6=Sunday
    timezone: str = 'Asia/Seoul'


class WorkScheduler:
    """
    Automatic service scheduler based on work hours

    Features:
    - Automatic start/stop based on time
    - Day-of-week scheduling
    - Multiple service management
    - Manual override support
    - Grace period for shutdown
    """

    def __init__(self, schedule_config: Dict[str, Any]):
        """
        Initialize work scheduler

        Args:
            schedule_config: Schedule configuration dictionary
                {
                    'work_hours': {
                        'start': '08:30',
                        'end': '19:00',
                        'enabled_days': [0, 1, 2, 3, 4]  # Mon-Fri
                    },
                    'grace_period_minutes': 5,
                    'auto_start_enabled': True,
                    'auto_stop_enabled': True
                }
        """
        self.config = schedule_config
        work_hours = schedule_config.get('work_hours', {})

        # Parse work schedule
        start_time = work_hours.get('start', '08:30').split(':')
        end_time = work_hours.get('end', '19:00').split(':')

        self.schedule = WorkSchedule(
            start_hour=int(start_time[0]),
            start_minute=int(start_time[1]),
            end_hour=int(end_time[0]),
            end_minute=int(end_time[1]),
            enabled_days=work_hours.get('enabled_days', [0, 1, 2, 3, 4, 5, 6]),  # All days
            timezone=schedule_config.get('timezone', 'Asia/Seoul')
        )

        self.grace_period_minutes = schedule_config.get('grace_period_minutes', 5)
        self.auto_start_enabled = schedule_config.get('auto_start_enabled', True)
        self.auto_stop_enabled = schedule_config.get('auto_stop_enabled', True)

        # Service callbacks
        self.start_callback: Optional[Callable[[], bool]] = None
        self.stop_callback: Optional[Callable[[], None]] = None

        # Scheduler state
        self.is_running = False
        self.scheduler_thread: Optional[threading.Thread] = None
        self.manual_override = False  # If True, ignore schedule
        self.services_started = False

        logger.info(f"Work scheduler initialized: {self.schedule.start_hour:02d}:{self.schedule.start_minute:02d} - {self.schedule.end_hour:02d}:{self.schedule.end_minute:02d}")

    def set_callbacks(
        self,
        start_callback: Callable[[], bool],
        stop_callback: Callable[[], None]
    ) -> None:
        """
        Set service start/stop callbacks

        Args:
            start_callback: Function to call to start services (returns True on success)
            stop_callback: Function to call to stop services
        """
        self.start_callback = start_callback
        self.stop_callback = stop_callback

    def is_work_time(self) -> bool:
        """
        Check if current time is within work hours

        Returns:
            True if within work hours
        """
        now = datetime.now()
        current_time = now.time()
        current_day = now.weekday()  # 0=Monday, 6=Sunday

        # Check if today is enabled
        if current_day not in self.schedule.enabled_days:
            return False

        # Create time objects for comparison
        start_time = dt_time(self.schedule.start_hour, self.schedule.start_minute)
        end_time = dt_time(self.schedule.end_hour, self.schedule.end_minute)

        # Check if current time is within range
        if start_time <= end_time:
            # Normal case: 08:30 - 19:00
            return start_time <= current_time <= end_time
        else:
            # Overnight case: 22:00 - 06:00
            return current_time >= start_time or current_time <= end_time

    def minutes_until_work_start(self) -> Optional[int]:
        """
        Calculate minutes until work starts

        Returns:
            Minutes until start, or None if currently in work hours
        """
        if self.is_work_time():
            return None

        now = datetime.now()
        current_minutes = now.hour * 60 + now.minute
        start_minutes = self.schedule.start_hour * 60 + self.schedule.start_minute

        if start_minutes > current_minutes:
            return start_minutes - current_minutes
        else:
            # Tomorrow
            return (24 * 60 - current_minutes) + start_minutes

    def minutes_until_work_end(self) -> Optional[int]:
        """
        Calculate minutes until work ends

        Returns:
            Minutes until end, or None if not in work hours
        """
        if not self.is_work_time():
            return None

        now = datetime.now()
        current_minutes = now.hour * 60 + now.minute
        end_minutes = self.schedule.end_hour * 60 + self.schedule.end_minute

        if end_minutes > current_minutes:
            return end_minutes - current_minutes
        else:
            # Tomorrow (overnight shift)
            return (24 * 60 - current_minutes) + end_minutes

    def start_scheduler(self) -> None:
        """Start the automatic scheduler"""
        if self.is_running:
            logger.warning("Scheduler already running")
            return

        if not self.start_callback or not self.stop_callback:
            logger.error("Callbacks not set. Call set_callbacks() first")
            return

        self.is_running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        logger.info("Work scheduler started")

    def _scheduler_loop(self) -> None:
        """Background scheduler loop"""
        check_interval = 60  # Check every minute

        while self.is_running:
            try:
                # Skip if manual override is active
                if not self.manual_override:
                    current_work_time = self.is_work_time()

                    # Auto-start logic
                    if current_work_time and not self.services_started and self.auto_start_enabled:
                        logger.info("Work hours started - starting services")
                        if self.start_callback():
                            self.services_started = True
                            logger.info("Services started successfully")
                        else:
                            logger.error("Failed to start services")

                    # Auto-stop logic
                    elif not current_work_time and self.services_started and self.auto_stop_enabled:
                        logger.info("Work hours ended - stopping services")
                        self.stop_callback()
                        self.services_started = False
                        logger.info("Services stopped")

            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")

            time.sleep(check_interval)

        logger.info("Scheduler loop stopped")

    def stop_scheduler(self) -> None:
        """Stop the automatic scheduler"""
        if not self.is_running:
            return

        self.is_running = False

        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=2.0)

        logger.info("Work scheduler stopped")

    def enable_manual_override(self) -> None:
        """Enable manual override (disable automatic scheduling)"""
        self.manual_override = True
        logger.info("Manual override enabled - automatic scheduling disabled")

    def disable_manual_override(self) -> None:
        """Disable manual override (enable automatic scheduling)"""
        self.manual_override = False
        logger.info("Manual override disabled - automatic scheduling enabled")

    def force_start(self) -> bool:
        """
        Manually start services (overrides schedule)

        Returns:
            True if successful
        """
        if not self.start_callback:
            logger.error("Start callback not set")
            return False

        self.enable_manual_override()
        result = self.start_callback()
        if result:
            self.services_started = True
            logger.info("Services manually started")
        return result

    def force_stop(self) -> None:
        """Manually stop services (overrides schedule)"""
        if not self.stop_callback:
            logger.error("Stop callback not set")
            return

        self.enable_manual_override()
        self.stop_callback()
        self.services_started = False
        logger.info("Services manually stopped")

    def get_status(self) -> Dict[str, Any]:
        """
        Get current scheduler status

        Returns:
            Status dictionary
        """
        is_work_time = self.is_work_time()

        return {
            'scheduler_running': self.is_running,
            'is_work_time': is_work_time,
            'services_started': self.services_started,
            'manual_override': self.manual_override,
            'auto_start_enabled': self.auto_start_enabled,
            'auto_stop_enabled': self.auto_stop_enabled,
            'schedule': {
                'start': f"{self.schedule.start_hour:02d}:{self.schedule.start_minute:02d}",
                'end': f"{self.schedule.end_hour:02d}:{self.schedule.end_minute:02d}",
                'enabled_days': self.schedule.enabled_days
            },
            'minutes_until_start': self.minutes_until_work_start(),
            'minutes_until_end': self.minutes_until_work_end(),
            'current_time': datetime.now().strftime("%H:%M:%S")
        }

    def update_schedule(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        enabled_days: Optional[List[int]] = None
    ) -> None:
        """
        Update work schedule

        Args:
            start_time: Start time in "HH:MM" format
            end_time: End time in "HH:MM" format
            enabled_days: List of enabled days (0=Monday, 6=Sunday)
        """
        if start_time:
            parts = start_time.split(':')
            self.schedule.start_hour = int(parts[0])
            self.schedule.start_minute = int(parts[1])

        if end_time:
            parts = end_time.split(':')
            self.schedule.end_hour = int(parts[0])
            self.schedule.end_minute = int(parts[1])

        if enabled_days is not None:
            self.schedule.enabled_days = enabled_days

        logger.info(f"Schedule updated: {self.schedule.start_hour:02d}:{self.schedule.start_minute:02d} - {self.schedule.end_hour:02d}:{self.schedule.end_minute:02d}")
