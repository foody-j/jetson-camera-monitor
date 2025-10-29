#!/usr/bin/env python3
"""
온도 센서 시뮬레이터 및 실제 센서 연동
- 시뮬레이션 모드: 실제와 유사한 온도 패턴 생성
- 실제 센서 모드: Serial/Modbus/GPIO 연동
"""

import time
import numpy as np
from abc import ABC, abstractmethod
from typing import Optional, Tuple
import json


# ================== 센서 베이스 클래스 ==================

class TemperatureSensor(ABC):
    """온도 센서 추상 클래스"""
    
    @abstractmethod
    def read(self) -> float:
        """온도 읽기"""
        pass
        
    @abstractmethod
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        pass


# ================== 시뮬레이터 ==================

class FryingSimulator:
    """튀김 조리 과정 시뮬레이터"""
    
    def __init__(self, 
                 initial_oil_temp: float = 170.0,
                 initial_fryer_temp: float = 175.0):
        """
        Args:
            initial_oil_temp: 초기 튀김유 온도
            initial_fryer_temp: 초기 튀김기 온도
        """
        self.initial_oil_temp = initial_oil_temp
        self.initial_fryer_temp = initial_fryer_temp
        self.start_time = None
        self.food_type = "generic"
        
        # 음식별 온도 변화 패턴
        self.temp_profiles = {
            "chicken": {
                "oil_drop_rate": 0.08,      # 초당 온도 감소율
                "oil_recovery_time": 60,     # 온도 회복 시작 시간
                "oil_fluctuation": 0.5,      # 온도 변동폭
                "cooking_time": 180          # 표준 조리시간(초)
            },
            "shrimp": {
                "oil_drop_rate": 0.05,
                "oil_recovery_time": 40,
                "oil_fluctuation": 0.3,
                "cooking_time": 120
            },
            "potato": {
                "oil_drop_rate": 0.06,
                "oil_recovery_time": 50,
                "oil_fluctuation": 0.4,
                "cooking_time": 150
            }
        }
        
    def start_cooking(self, food_type: str = "chicken"):
        """조리 시작"""
        self.start_time = time.time()
        self.food_type = food_type if food_type in self.temp_profiles else "chicken"
        print(f"🔥 시뮬레이션 시작: {self.food_type}")
        
    def get_oil_temperature(self) -> float:
        """튀김유 온도 계산"""
        if not self.start_time:
            return self.initial_oil_temp
            
        elapsed = time.time() - self.start_time
        profile = self.temp_profiles[self.food_type]
        
        # 기본 온도 감소 (음식 투입 직후)
        temp_drop = elapsed * profile["oil_drop_rate"]
        
        # 온도 회복 (히터 작동)
        if elapsed > profile["oil_recovery_time"]:
            recovery_elapsed = elapsed - profile["oil_recovery_time"]
            recovery = recovery_elapsed * 0.03  # 천천히 회복
            temp_drop -= recovery
            
        # 최종 온도 계산
        temp = self.initial_oil_temp - temp_drop
        
        # 노이즈 추가 (실제와 유사하게)
        noise = np.random.normal(0, profile["oil_fluctuation"])
        temp += noise
        
        # 온도 범위 제한
        temp = max(150, min(180, temp))  # 150-180도 사이
        
        return temp
        
    def get_fryer_temperature(self) -> float:
        """튀김기 벽면 온도 계산"""
        if not self.start_time:
            return self.initial_fryer_temp
            
        # 튀김기 온도는 유온도보다 약간 높고 변화가 느림
        oil_temp = self.get_oil_temperature()
        fryer_temp = oil_temp + np.random.uniform(3, 7)
        
        return fryer_temp
        
    def get_internal_temperature(self) -> float:
        """음식 내부 온도 (탐침온도계 시뮬레이션)"""
        if not self.start_time:
            return 20.0  # 실온
            
        elapsed = time.time() - self.start_time
        profile = self.temp_profiles[self.food_type]
        
        # S자 곡선으로 온도 상승
        progress = elapsed / profile["cooking_time"]
        
        if progress < 0.2:
            # 초기: 천천히 상승
            internal_temp = 20 + (progress * 5 * 30)
        elif progress < 0.8:
            # 중간: 빠르게 상승
            internal_temp = 30 + ((progress - 0.2) / 0.6 * 45)
        else:
            # 후기: 천천히 상승
            internal_temp = 75 + ((progress - 0.8) / 0.2 * 5)
            
        # 노이즈 추가
        internal_temp += np.random.normal(0, 1)
        
        return min(internal_temp, 85)  # 최대 85도
        
    def is_complete(self) -> bool:
        """조리 완료 여부 (시뮬레이션)"""
        if not self.start_time:
            return False
            
        # 내부 온도 기준 (치킨 75도, 새우 63도 등)
        thresholds = {"chicken": 75, "shrimp": 63, "potato": 70}
        threshold = thresholds.get(self.food_type, 70)
        
        return self.get_internal_temperature() >= threshold


# ================== 실제 센서 인터페이스 ==================

class SerialTemperatureSensor(TemperatureSensor):
    """시리얼 통신 온도 센서"""
    
    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 9600):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        
        try:
            import serial
            self.serial = serial.Serial(port, baudrate, timeout=1)
            print(f"✅ 시리얼 센서 연결: {port}")
        except Exception as e:
            print(f"❌ 시리얼 연결 실패: {e}")
            
    def read(self) -> float:
        """온도 읽기"""
        if not self.serial:
            return -999.0
            
        try:
            # 센서에 읽기 명령 전송
            self.serial.write(b"READ_TEMP\n")
            
            # 응답 읽기
            response = self.serial.readline().decode().strip()
            
            # 파싱 (형식: "TEMP:25.5")
            if response.startswith("TEMP:"):
                temp = float(response.split(":")[1])
                return temp
                
        except Exception as e:
            print(f"읽기 오류: {e}")
            
        return -999.0
        
    def is_connected(self) -> bool:
        return self.serial is not None and self.serial.is_open


class ModbusTemperatureSensor(TemperatureSensor):
    """Modbus RTU 온도 센서"""
    
    def __init__(self, port: str = "/dev/ttyUSB0", 
                 slave_id: int = 1, register: int = 0x0000):
        self.port = port
        self.slave_id = slave_id
        self.register = register
        self.client = None
        
        try:
            from pymodbus.client import ModbusSerialClient
            self.client = ModbusSerialClient(
                port=port,
                baudrate=9600,
                parity='N',
                stopbits=1,
                bytesize=8
            )
            if self.client.connect():
                print(f"✅ Modbus 센서 연결: {port} (ID: {slave_id})")
        except ImportError:
            print("⚠️ pymodbus 설치 필요: pip install pymodbus")
        except Exception as e:
            print(f"❌ Modbus 연결 실패: {e}")
            
    def read(self) -> float:
        """온도 읽기"""
        if not self.client:
            return -999.0
            
        try:
            # Holding Register 읽기
            result = self.client.read_holding_registers(
                self.register, 1, slave=self.slave_id
            )
            
            if result and not result.isError():
                # 보통 10배 또는 100배 스케일링
                raw_value = result.registers[0]
                temp = raw_value / 10.0  # 0.1도 단위라고 가정
                return temp
                
        except Exception as e:
            print(f"Modbus 읽기 오류: {e}")
            
        return -999.0
        
    def is_connected(self) -> bool:
        return self.client is not None and self.client.is_socket_open()


class GPIOTemperatureSensor(TemperatureSensor):
    """GPIO 연결 온도 센서 (DS18B20 등)"""
    
    def __init__(self, gpio_pin: int = 4):
        self.gpio_pin = gpio_pin
        self.sensor_file = None
        
        # 1-Wire 센서 파일 찾기
        import glob
        base_dir = '/sys/bus/w1/devices/'
        device_folders = glob.glob(base_dir + '28*')
        
        if device_folders:
            self.sensor_file = device_folders[0] + '/w1_slave'
            print(f"✅ GPIO 센서 발견: {self.sensor_file}")
        else:
            print("❌ 1-Wire 센서를 찾을 수 없습니다")
            
    def read(self) -> float:
        """온도 읽기"""
        if not self.sensor_file:
            return -999.0
            
        try:
            with open(self.sensor_file, 'r') as f:
                lines = f.readlines()
                
            # 체크섬 확인
            if lines[0].strip()[-3:] != 'YES':
                return -999.0
                
            # 온도 파싱
            temp_pos = lines[1].find('t=')
            if temp_pos != -1:
                temp_string = lines[1][temp_pos+2:]
                temp_c = float(temp_string) / 1000.0
                return temp_c
                
        except Exception as e:
            print(f"GPIO 센서 읽기 오류: {e}")
            
        return -999.0
        
    def is_connected(self) -> bool:
        return self.sensor_file is not None


# ================== 통합 센서 매니저 ==================

class SensorManager:
    """센서 통합 관리"""
    
    def __init__(self, mode: str = "simulate"):
        """
        Args:
            mode: "simulate", "serial", "modbus", "gpio"
        """
        self.mode = mode
        self.simulator = None
        self.oil_sensor = None
        self.fryer_sensor = None
        
        self._initialize_sensors()
        
    def _initialize_sensors(self):
        """센서 초기화"""
        if self.mode == "simulate":
            self.simulator = FryingSimulator()
            print("🎮 시뮬레이션 모드")
            
        elif self.mode == "serial":
            self.oil_sensor = SerialTemperatureSensor("/dev/ttyUSB0")
            self.fryer_sensor = SerialTemperatureSensor("/dev/ttyUSB1")
            
        elif self.mode == "modbus":
            self.oil_sensor = ModbusTemperatureSensor(
                port="/dev/ttyUSB0", slave_id=1, register=0x0000
            )
            self.fryer_sensor = ModbusTemperatureSensor(
                port="/dev/ttyUSB0", slave_id=2, register=0x0000
            )
            
        elif self.mode == "gpio":
            self.oil_sensor = GPIOTemperatureSensor(gpio_pin=4)
            self.fryer_sensor = GPIOTemperatureSensor(gpio_pin=17)
            
    def start_cooking(self, food_type: str = "chicken"):
        """조리 시작"""
        if self.simulator:
            self.simulator.start_cooking(food_type)
            
    def read_temperatures(self) -> Tuple[float, float]:
        """
        온도 읽기
        
        Returns:
            (oil_temp, fryer_temp)
        """
        if self.mode == "simulate":
            oil_temp = self.simulator.get_oil_temperature()
            fryer_temp = self.simulator.get_fryer_temperature()
        else:
            oil_temp = self.oil_sensor.read() if self.oil_sensor else -999
            fryer_temp = self.fryer_sensor.read() if self.fryer_sensor else -999
            
        return oil_temp, fryer_temp
        
    def get_probe_temperature(self) -> float:
        """탐침 온도 (시뮬레이션용)"""
        if self.simulator:
            return self.simulator.get_internal_temperature()
        return -999
        
    def is_complete(self) -> bool:
        """완료 여부 (시뮬레이션용)"""
        if self.simulator:
            return self.simulator.is_complete()
        return False


# ================== 테스트 코드 ==================

def test_simulator():
    """시뮬레이터 테스트"""
    print("\n" + "=" * 60)
    print("🧪 튀김 시뮬레이터 테스트")
    print("=" * 60)
    
    manager = SensorManager(mode="simulate")
    manager.start_cooking("chicken")
    
    print("\n30초간 온도 변화 관찰...")
    print("시간(초) | 유온도 | 튀김기 | 내부온도 | 완료여부")
    print("-" * 50)
    
    for i in range(31):
        oil_temp, fryer_temp = manager.read_temperatures()
        probe_temp = manager.get_probe_temperature()
        is_complete = manager.is_complete()
        
        print(f"{i:4d}초 | {oil_temp:6.1f}°C | {fryer_temp:6.1f}°C | "
              f"{probe_temp:6.1f}°C | {'완료' if is_complete else '진행중'}")
              
        time.sleep(1)
        

def sensor_config_guide():
    """센서 설정 가이드 출력"""
    print("""
================== 센서 연결 가이드 ==================

1. 시리얼 센서 (Arduino + MAX6675 등)
   - 연결: USB → /dev/ttyUSB0
   - 설정: baudrate=9600
   - Arduino 코드 예시:
     void loop() {
       if (Serial.available()) {
         String cmd = Serial.readString();
         if (cmd == "READ_TEMP") {
           float temp = thermocouple.readCelsius();
           Serial.print("TEMP:");
           Serial.println(temp);
         }
       }
     }

2. Modbus RTU 센서 (산업용)
   - 연결: RS485 → USB 컨버터
   - 설정: 9600 8N1
   - 주소: 1번(유온도), 2번(튀김기)
   - 레지스터: 0x0000 (온도값)

3. GPIO 센서 (DS18B20)
   - 연결: GPIO4(유온도), GPIO17(튀김기)
   - 1-Wire 활성화 필요:
     sudo modprobe w1-gpio
     sudo modprobe w1-therm
   
4. 시뮬레이션 모드
   - 실제 센서 없이 테스트
   - 실제와 유사한 온도 패턴 생성

사용법:
   manager = SensorManager(mode="simulate")  # 또는 "serial", "modbus", "gpio"
   oil_temp, fryer_temp = manager.read_temperatures()
=====================================================
""")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "guide":
            sensor_config_guide()
        elif sys.argv[1] == "test":
            test_simulator()
    else:
        test_simulator()