"""
RS485 Vibration Sensor Interface

Handles communication with vibration sensors connected via USB to RS485 adapter.
Supports Modbus RTU protocol for industrial sensors.
"""

import serial
import struct
import time
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


@dataclass
class VibrationReading:
    """Vibration sensor reading data"""
    timestamp: float
    x_axis: float  # m/s² or mm/s
    y_axis: float
    z_axis: float
    magnitude: float
    temperature: Optional[float] = None
    frequency: Optional[float] = None


class RS485SensorInterface(ABC):
    """Abstract base class for RS485 sensors"""

    @abstractmethod
    def read_vibration(self) -> Optional[VibrationReading]:
        """Read vibration data from sensor"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if sensor is connected"""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close sensor connection"""
        pass


class ModbusRS485Sensor(RS485SensorInterface):
    """
    Modbus RTU vibration sensor over RS485

    Common register layout for vibration sensors:
    - 0x0000-0x0002: X, Y, Z acceleration (float32)
    - 0x0006: Temperature (float32)
    - 0x0008: Magnitude (float32)
    - 0x000A: Dominant frequency (float32)
    """

    def __init__(
        self,
        port: str = '/dev/ttyUSB0',
        baudrate: int = 9600,
        slave_address: int = 1,
        timeout: float = 1.0
    ):
        """
        Initialize Modbus RS485 sensor

        Args:
            port: Serial port (e.g., '/dev/ttyUSB0')
            baudrate: Communication speed (9600, 19200, 38400, 115200)
            slave_address: Modbus slave address (1-247)
            timeout: Read timeout in seconds
        """
        self.port = port
        self.baudrate = baudrate
        self.slave_address = slave_address
        self.timeout = timeout
        self.serial_port: Optional[serial.Serial] = None
        self._connected = False

        self._connect()

    def _connect(self) -> None:
        """Establish serial connection"""
        try:
            self.serial_port = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )
            self._connected = True
            logger.info(f"Connected to RS485 sensor on {self.port} @ {self.baudrate} baud")
        except serial.SerialException as e:
            logger.error(f"Failed to connect to RS485 sensor: {e}")
            self._connected = False

    def _calculate_crc(self, data: bytes) -> int:
        """Calculate Modbus CRC16"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc

    def _read_holding_registers(self, start_address: int, count: int) -> Optional[bytes]:
        """
        Read Modbus holding registers (function code 0x03)

        Args:
            start_address: Starting register address
            count: Number of registers to read

        Returns:
            Raw bytes from registers or None on error
        """
        if not self._connected or self.serial_port is None:
            return None

        # Build Modbus RTU request: [slave][function][addr_hi][addr_lo][count_hi][count_lo][crc_lo][crc_hi]
        request = struct.pack('>BBHH', self.slave_address, 0x03, start_address, count)
        crc = self._calculate_crc(request)
        request += struct.pack('<H', crc)

        try:
            self.serial_port.reset_input_buffer()
            self.serial_port.write(request)
            time.sleep(0.05)  # Wait for sensor response

            # Read response: [slave][function][byte_count][data...][crc]
            response = self.serial_port.read(5 + count * 2)

            if len(response) < 5:
                logger.warning("Incomplete Modbus response")
                return None

            # Verify CRC
            received_crc = struct.unpack('<H', response[-2:])[0]
            calculated_crc = self._calculate_crc(response[:-2])

            if received_crc != calculated_crc:
                logger.warning("CRC mismatch in Modbus response")
                return None

            # Extract data bytes
            byte_count = response[2]
            data = response[3:3 + byte_count]
            return data

        except serial.SerialException as e:
            logger.error(f"Modbus read error: {e}")
            return None

    def read_vibration(self) -> Optional[VibrationReading]:
        """Read vibration data from sensor"""
        # Read 6 registers (12 bytes) starting from 0x0000
        # Registers: X (2), Y (2), Z (2), Temp (2), Magnitude (2), Freq (2)
        data = self._read_holding_registers(start_address=0x0000, count=6)

        if data is None or len(data) < 12:
            return None

        try:
            # Parse float32 values (big-endian)
            x_axis = struct.unpack('>f', data[0:4])[0]
            y_axis = struct.unpack('>f', data[4:8])[0]
            z_axis = struct.unpack('>f', data[8:12])[0]

            # Calculate magnitude
            magnitude = (x_axis**2 + y_axis**2 + z_axis**2) ** 0.5

            # Try to read optional temperature and frequency
            temp_data = self._read_holding_registers(start_address=0x0006, count=2)
            temperature = struct.unpack('>f', temp_data)[0] if temp_data else None

            freq_data = self._read_holding_registers(start_address=0x0008, count=2)
            frequency = struct.unpack('>f', freq_data)[0] if freq_data else None

            return VibrationReading(
                timestamp=time.time(),
                x_axis=x_axis,
                y_axis=y_axis,
                z_axis=z_axis,
                magnitude=magnitude,
                temperature=temperature,
                frequency=frequency
            )

        except struct.error as e:
            logger.error(f"Failed to parse sensor data: {e}")
            return None

    def is_connected(self) -> bool:
        """Check if sensor is connected"""
        return self._connected and self.serial_port is not None and self.serial_port.is_open

    def close(self) -> None:
        """Close serial connection"""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            logger.info("RS485 sensor connection closed")
        self._connected = False


class SimpleRS485Sensor(RS485SensorInterface):
    """
    Simple ASCII protocol RS485 sensor

    For sensors that output simple ASCII format:
    "X:1.23,Y:0.45,Z:0.67\n"
    """

    def __init__(
        self,
        port: str = '/dev/ttyUSB0',
        baudrate: int = 9600,
        timeout: float = 1.0
    ):
        self.port = port
        self.baudrate = baudrate
        self.serial_port: Optional[serial.Serial] = None
        self._connected = False

        self._connect()

    def _connect(self) -> None:
        """Establish serial connection"""
        try:
            self.serial_port = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            self._connected = True
            logger.info(f"Connected to ASCII RS485 sensor on {self.port}")
        except serial.SerialException as e:
            logger.error(f"Failed to connect: {e}")
            self._connected = False

    def read_vibration(self) -> Optional[VibrationReading]:
        """Read ASCII vibration data"""
        if not self._connected or self.serial_port is None:
            return None

        try:
            line = self.serial_port.readline().decode('ascii').strip()

            # Parse "X:1.23,Y:0.45,Z:0.67" format
            parts = line.split(',')
            data = {}
            for part in parts:
                if ':' in part:
                    key, value = part.split(':')
                    data[key.strip()] = float(value.strip())

            x_axis = data.get('X', 0.0)
            y_axis = data.get('Y', 0.0)
            z_axis = data.get('Z', 0.0)
            magnitude = (x_axis**2 + y_axis**2 + z_axis**2) ** 0.5

            return VibrationReading(
                timestamp=time.time(),
                x_axis=x_axis,
                y_axis=y_axis,
                z_axis=z_axis,
                magnitude=magnitude,
                temperature=data.get('T'),
                frequency=data.get('F')
            )

        except (ValueError, UnicodeDecodeError, KeyError) as e:
            logger.error(f"Failed to parse ASCII data: {e}")
            return None

    def is_connected(self) -> bool:
        """Check connection status"""
        return self._connected and self.serial_port is not None and self.serial_port.is_open

    def close(self) -> None:
        """Close connection"""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self._connected = False


class RS485VibrationSensor:
    """
    Unified RS485 vibration sensor interface

    Automatically detects protocol type (Modbus or ASCII) or uses specified type
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize sensor with configuration

        Args:
            config: Configuration dictionary with keys:
                - port: Serial port path
                - baudrate: Communication speed
                - protocol: 'modbus' or 'ascii' or 'auto'
                - slave_address: For Modbus (default 1)
                - timeout: Read timeout
        """
        self.config = config
        protocol = config.get('protocol', 'modbus').lower()

        if protocol == 'modbus':
            self.sensor = ModbusRS485Sensor(
                port=config.get('port', '/dev/ttyUSB0'),
                baudrate=config.get('baudrate', 9600),
                slave_address=config.get('slave_address', 1),
                timeout=config.get('timeout', 1.0)
            )
        elif protocol == 'ascii':
            self.sensor = SimpleRS485Sensor(
                port=config.get('port', '/dev/ttyUSB0'),
                baudrate=config.get('baudrate', 9600),
                timeout=config.get('timeout', 1.0)
            )
        else:
            # Default to Modbus
            self.sensor = ModbusRS485Sensor(
                port=config.get('port', '/dev/ttyUSB0'),
                baudrate=config.get('baudrate', 9600),
                slave_address=config.get('slave_address', 1),
                timeout=config.get('timeout', 1.0)
            )

    def read(self) -> Optional[VibrationReading]:
        """Read vibration data"""
        return self.sensor.read_vibration()

    def is_connected(self) -> bool:
        """Check connection status"""
        return self.sensor.is_connected()

    def close(self) -> None:
        """Close connection"""
        self.sensor.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
