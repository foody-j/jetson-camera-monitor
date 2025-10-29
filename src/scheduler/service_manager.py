"""
Service Manager

Manages lifecycle of all monitoring services (camera, vibration, frying AI)
"""

import logging
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service status enumeration"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class ServiceManager:
    """
    Centralized service lifecycle management

    Manages multiple monitoring services and their states
    """

    def __init__(self):
        """Initialize service manager"""
        self.services: Dict[str, Dict[str, Any]] = {
            'camera': {
                'name': 'Camera Monitoring',
                'status': ServiceStatus.STOPPED,
                'instance': None,
                'error_message': None
            },
            'vibration': {
                'name': 'Vibration Monitoring',
                'status': ServiceStatus.STOPPED,
                'instance': None,
                'error_message': None
            },
            'frying': {
                'name': 'Frying AI Monitoring',
                'status': ServiceStatus.STOPPED,
                'instance': None,
                'error_message': None
            }
        }

    def register_service(self, service_id: str, service_instance: Any) -> None:
        """
        Register a service instance

        Args:
            service_id: Service identifier ('camera', 'vibration', 'frying')
            service_instance: Service object instance
        """
        if service_id in self.services:
            self.services[service_id]['instance'] = service_instance
            logger.info(f"Service registered: {service_id}")
        else:
            logger.error(f"Unknown service ID: {service_id}")

    def start_service(self, service_id: str) -> bool:
        """
        Start a specific service

        Args:
            service_id: Service to start

        Returns:
            True if started successfully
        """
        if service_id not in self.services:
            logger.error(f"Unknown service: {service_id}")
            return False

        service = self.services[service_id]

        if service['status'] == ServiceStatus.RUNNING:
            logger.warning(f"Service already running: {service_id}")
            return True

        service['status'] = ServiceStatus.STARTING
        service['error_message'] = None

        try:
            instance = service['instance']

            if instance is None:
                raise Exception("Service instance not registered")

            # Call service-specific start method
            if service_id == 'camera':
                success = self._start_camera_service(instance)
            elif service_id == 'vibration':
                success = self._start_vibration_service(instance)
            elif service_id == 'frying':
                success = self._start_frying_service(instance)
            else:
                success = False

            if success:
                service['status'] = ServiceStatus.RUNNING
                logger.info(f"Service started: {service_id}")
                return True
            else:
                service['status'] = ServiceStatus.ERROR
                service['error_message'] = "Failed to start"
                logger.error(f"Failed to start service: {service_id}")
                return False

        except Exception as e:
            service['status'] = ServiceStatus.ERROR
            service['error_message'] = str(e)
            logger.error(f"Error starting service {service_id}: {e}")
            return False

    def stop_service(self, service_id: str) -> None:
        """
        Stop a specific service

        Args:
            service_id: Service to stop
        """
        if service_id not in self.services:
            logger.error(f"Unknown service: {service_id}")
            return

        service = self.services[service_id]

        if service['status'] == ServiceStatus.STOPPED:
            logger.warning(f"Service already stopped: {service_id}")
            return

        service['status'] = ServiceStatus.STOPPING

        try:
            instance = service['instance']

            if instance is None:
                raise Exception("Service instance not registered")

            # Call service-specific stop method
            if service_id == 'camera':
                self._stop_camera_service(instance)
            elif service_id == 'vibration':
                self._stop_vibration_service(instance)
            elif service_id == 'frying':
                self._stop_frying_service(instance)

            service['status'] = ServiceStatus.STOPPED
            logger.info(f"Service stopped: {service_id}")

        except Exception as e:
            service['status'] = ServiceStatus.ERROR
            service['error_message'] = str(e)
            logger.error(f"Error stopping service {service_id}: {e}")

    def start_all_services(self) -> bool:
        """
        Start all registered services

        Returns:
            True if all started successfully
        """
        logger.info("Starting all services...")
        success = True

        for service_id in self.services.keys():
            if not self.start_service(service_id):
                success = False

        return success

    def stop_all_services(self) -> None:
        """Stop all running services"""
        logger.info("Stopping all services...")

        for service_id in self.services.keys():
            self.stop_service(service_id)

    def get_service_status(self, service_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a specific service

        Args:
            service_id: Service identifier

        Returns:
            Status dictionary or None
        """
        if service_id not in self.services:
            return None

        service = self.services[service_id]

        return {
            'service_id': service_id,
            'name': service['name'],
            'status': service['status'].value,
            'error_message': service['error_message']
        }

    def get_all_statuses(self) -> List[Dict[str, Any]]:
        """
        Get status of all services

        Returns:
            List of status dictionaries
        """
        return [
            self.get_service_status(service_id)
            for service_id in self.services.keys()
        ]

    def is_any_service_running(self) -> bool:
        """Check if any service is running"""
        return any(
            service['status'] == ServiceStatus.RUNNING
            for service in self.services.values()
        )

    # Service-specific start/stop methods

    def _start_camera_service(self, instance) -> bool:
        """Start camera monitoring service"""
        # Assuming instance has a start_monitoring() method
        if hasattr(instance, 'start_monitoring'):
            return instance.start_monitoring()
        elif hasattr(instance, 'start'):
            return instance.start()
        else:
            logger.error("Camera service has no start method")
            return False

    def _stop_camera_service(self, instance) -> None:
        """Stop camera monitoring service"""
        if hasattr(instance, 'stop_monitoring'):
            instance.stop_monitoring()
        elif hasattr(instance, 'stop'):
            instance.stop()
        elif hasattr(instance, 'cleanup'):
            instance.cleanup()

    def _start_vibration_service(self, instance) -> bool:
        """Start vibration monitoring service"""
        if hasattr(instance, 'start_monitoring'):
            return instance.start_monitoring()
        else:
            logger.error("Vibration service has no start_monitoring method")
            return False

    def _stop_vibration_service(self, instance) -> None:
        """Stop vibration monitoring service"""
        if hasattr(instance, 'stop_monitoring'):
            instance.stop_monitoring()

    def _start_frying_service(self, instance) -> bool:
        """Start frying AI monitoring service"""
        # Frying AI may have different start method
        if hasattr(instance, 'start_session'):
            # May need parameters like food_type
            return instance.start_session(food_type='default')
        elif hasattr(instance, 'start'):
            return instance.start()
        else:
            logger.error("Frying AI service has no start method")
            return False

    def _stop_frying_service(self, instance) -> None:
        """Stop frying AI monitoring service"""
        if hasattr(instance, 'stop_session'):
            instance.stop_session()
        elif hasattr(instance, 'stop'):
            instance.stop()
