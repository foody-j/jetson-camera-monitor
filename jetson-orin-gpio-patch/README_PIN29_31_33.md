# GPIO Pin 29, 31, 33 활성화 가이드

## 개요
Jetson Orin Nano의 Pin 29, 31, 33을 GPIO로 사용하기 위한 Device Tree Overlay

## GPIO 핀 매핑

| 물리적 핀 | GPIO 번호 | SoC Pin Name | 특징 |
|---------|----------|--------------|------|
| **29** | GPIO 417 | soc_gpio26_pq6 | 일반 GPIO |
| **31** | GPIO 419 | soc_gpio27_pq7 | 일반 GPIO |
| **33** | GPIO 391 | soc_gpio00_pp4 | PWM 지원 |

## 설치 방법

### 1. 설치 스크립트 실행
```bash
cd /home/hr_dku_001/jetson-food-ai/jetson-orin-gpio-patch
sudo ./install_pin29_31_33.sh
```

### 2. 재부팅
```bash
sudo reboot
```

### 3. 확인
```bash
# GPIO 디렉토리 확인
ls /sys/class/gpio/

# GPIO export 테스트
echo 417 > /sys/class/gpio/export
echo 419 > /sys/class/gpio/export
echo 391 > /sys/class/gpio/export

# GPIO 디렉토리 생성 확인
ls /sys/class/gpio/gpio417
ls /sys/class/gpio/gpio419
ls /sys/class/gpio/gpio391
```

## Python 사용 예제

### Jetson.GPIO 사용 (BOARD 모드)
```python
import Jetson.GPIO as GPIO
import time

# 핀 모드 설정
GPIO.setmode(GPIO.BOARD)

# 출력 핀 설정
GPIO.setup(29, GPIO.OUT)
GPIO.setup(31, GPIO.OUT)
GPIO.setup(33, GPIO.OUT)

# HIGH 출력
GPIO.output(29, GPIO.HIGH)
GPIO.output(31, GPIO.HIGH)
GPIO.output(33, GPIO.HIGH)

time.sleep(1)

# LOW 출력
GPIO.output(29, GPIO.LOW)
GPIO.output(31, GPIO.LOW)
GPIO.output(33, GPIO.LOW)

# 정리
GPIO.cleanup()
```

### Jetson.GPIO 사용 (BCM 모드 - GPIO 번호 직접 사용)
```python
import Jetson.GPIO as GPIO

GPIO.setmode(GPIO.BCM)

# GPIO 번호로 직접 설정
GPIO.setup(417, GPIO.OUT)
GPIO.setup(419, GPIO.OUT)
GPIO.setup(391, GPIO.OUT)

GPIO.output(417, GPIO.HIGH)
GPIO.output(419, GPIO.HIGH)
GPIO.output(391, GPIO.HIGH)

GPIO.cleanup()
```

## 주의사항

### ⚠️ 전기적 특성
- **최대 전류**: 50mA per pin
- **전압**: 3.3V (5V 절대 연결 금지!)
- **논리 레벨**: 3.3V CMOS

### ⚠️ 핀 충돌 확인
Pin 29, 31, 33이 다른 기능(I2C, SPI 등)에 사용되고 있지 않은지 확인:
```bash
cat /boot/extlinux/extlinux.conf | grep FDT
```

### ⚠️ 기존 Pin 7 Overlay와 호환
- `pin7_as_gpio.dtbo`와 `pin29_31_33_as_gpio.dtbo`는 **동시 사용 가능**
- 충돌하지 않음

## 제거 방법

### Overlay 비활성화
```bash
# extlinux.conf 백업
sudo cp /boot/extlinux/extlinux.conf /boot/extlinux/extlinux.conf.backup

# Overlay 제거
sudo vim /boot/extlinux/extlinux.conf
# FDT 라인에서 "/boot/pin29_31_33_as_gpio.dtbo" 삭제

# 재부팅
sudo reboot
```

## 트러블슈팅

### GPIO export 실패
```bash
# 커널 로그 확인
dmesg | grep gpio
dmesg | grep tegra

# Overlay 로드 확인
ls -la /boot/pin29_31_33_as_gpio.dtbo
cat /boot/extlinux/extlinux.conf | grep pin29_31_33
```

### Permission denied 에러
```bash
# GPIO 그룹 추가
sudo groupadd -f gpio
sudo usermod -a -G gpio $USER

# 재로그인 필요
```

## 참고 자료
- [Jetson GPIO Library](https://github.com/NVIDIA/jetson-gpio)
- [Jetson Orin Nano Pinout](https://jetsonhacks.com/)
- Original overlay: `pin7_as_gpio.dts`
