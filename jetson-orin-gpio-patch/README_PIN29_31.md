 # GPIO Pin 29, 31 활성화 가이드

## ⚠️ 중요 경고
**Pin 29, 31은 WiFi와 충돌할 수 있습니다!**
- Pin 29, 31은 기본적으로 extperiph3_clk, extperiph4_clk (외부 주변장치 클럭) 기능을 가집니다
- 일부 WiFi 모듈이 이 클럭을 사용할 수 있으므로 GPIO로 변경 시 WiFi가 작동하지 않을 수 있습니다
- **사용 전 WiFi 연결을 확인하고, 문제 발생 시 즉시 오버레이를 제거하세요**

## 개요
Jetson Orin Nano의 Pin 29, 31을 GPIO 출력으로 사용하기 위한 Device Tree Overlay

## GPIO 핀 매핑

| 물리적 핀 | SoC Pin Name | 기본 기능 | GPIO 모드 |
|---------|--------------|----------|----------|
| **29** | soc_gpio32_pq5 | extperiph3_clk | 출력 GPIO |
| **31** | soc_gpio33_pq6 | extperiph4_clk | 출력 GPIO |

## 설치 방법

### 1. DTS 컴파일
```bash
cd ~/jetson-food-ai/jetson-orin-gpio-patch
dtc -I dts -O dtb -o pin29_31_as_gpio.dtbo pin29_31_as_gpio.dts
```

### 2. /boot/로 복사
```bash
sudo cp pin29_31_as_gpio.dtbo /boot/
```

### 3. extlinux.conf 수정
```bash
sudo vim /boot/extlinux/extlinux.conf
```

JetsonIO LABEL 섹션에서 OVERLAYS 라인 수정:
```
LABEL JetsonIO
    MENU LABEL Custom Header Config: <HDR40 Pin 29, 31 gpio output>
    LINUX /boot/Image
    FDT /boot/dtb/kernel_tegra234-p3768-0000+p3767-0005-nv-super.dtb
    INITRD /boot/initrd
    APPEND ${cbootargs} root=PARTUUID=... rw rootwait rootfstype=ext4 ...
    OVERLAYS /boot/pin29_31_as_gpio.dtbo
```

**여러 오버레이 동시 사용:**
```
OVERLAYS /boot/pin7_15_as_gpio.dtbo /boot/pin29_31_as_gpio.dtbo
```

### 4. 재부팅
```bash
sudo reboot
```

### 5. WiFi 확인
재부팅 후 **반드시** WiFi가 정상 작동하는지 확인:
```bash
nmcli device status
ping -c 4 8.8.8.8
```

## 사용 방법

### Python (Jetson.GPIO)
```python
import Jetson.GPIO as GPIO

# BOARD 모드 사용
GPIO.setmode(GPIO.BOARD)

# Pin 29, 31을 출력으로 설정
GPIO.setup(29, GPIO.OUT)
GPIO.setup(31, GPIO.OUT)

# HIGH 출력 (3.3V)
GPIO.output(29, GPIO.HIGH)
GPIO.output(31, GPIO.HIGH)

# LOW 출력 (0V)
GPIO.output(29, GPIO.LOW)
GPIO.output(31, GPIO.LOW)

# 정리
GPIO.cleanup()
```

### sysfs를 통한 제어 (테스트용)
```bash
# GPIO 번호 확인
cat /sys/kernel/debug/gpio

# Pin 29, 31의 GPIO 번호를 찾아서 export
# 예: gpio<N>으로 나타나는 번호 사용
```

## 주의사항

### ⚠️ WiFi 충돌
- **가장 중요**: Pin 29, 31을 GPIO로 사용 시 WiFi가 작동하지 않을 수 있습니다
- 증상: WiFi 인터페이스가 사라지거나 연결이 안 됨
- 해결: 아래 "제거 방법"을 따라 오버레이를 비활성화하고 재부팅

### ⚠️ 기본 기능
- Pin 29: extperiph3_clk (외부 주변장치 클럭 3)
- Pin 31: extperiph4_clk (외부 주변장치 클럭 4)
- GPIO로 사용 시 이 클럭 기능들이 비활성화됩니다

### ⚠️ 전기적 특성
- **최대 전류**: 50mA per pin
- **전압**: 3.3V (5V 절대 연결 금지!)
- **논리 레벨**: 3.3V CMOS
- **출력 전용**: 이 오버레이는 출력용으로 설정되어 있습니다

### ⚠️ SSR 릴레이 연결 시
SSR(Solid State Relay)을 제어할 때:
- 3.3V 출력이므로 SSR의 제어 전압 사양 확인 필요
- 대부분의 SSR은 3-32V DC 제어 전압 지원
- 전류 제한: 50mA (일반적인 SSR 제어 전류는 5-20mA)

## 제거 방법

WiFi 문제 발생 시 즉시 실행:

### Overlay 비활성화
```bash
sudo nano /boot/extlinux/extlinux.conf

# OVERLAYS 라인에서 pin29_31_as_gpio.dtbo 제거 또는 주석처리:
# OVERLAYS /boot/pin7_15_as_gpio.dtbo
# 또는 완전히 주석:
# #OVERLAYS /boot/pin29_31_as_gpio.dtbo

sudo reboot
```

## 트러블슈팅

### WiFi가 작동하지 않음
1. 즉시 오버레이 제거 (위 제거 방법 참고)
2. 재부팅
3. WiFi 확인: `nmcli device status`
4. 다른 GPIO 핀 사용 고려 (Pin 7, 15, 32, 33 등)

### GPIO가 작동하지 않음
```bash
# 오버레이 적용 확인
cat /boot/extlinux/extlinux.conf | grep OVERLAYS

# GPIO 상태 확인
sudo cat /sys/kernel/debug/gpio | grep -A 5 "gpio-32\|gpio-33"

# 커널 로그 확인
dmesg | grep -i gpio
```

## 대안 GPIO 핀
WiFi와 충돌하지 않는 안전한 GPIO 핀:
- **Pin 7**: Audio MCLK (오디오 사용 안 할 시)
- **Pin 15**: PWM1 (PWM 사용 안 할 시)
- **Pin 32**: PWM7
- **Pin 33**: PWM5

## 참고 자료
- [Jetson GPIO Library](https://github.com/NVIDIA/jetson-gpio)
- [Jetson Orin Nano Pinout](https://jetsonhacks.com/)
- Pin mapping: `headers/tegra234-p3767-0000-common-hdr40.dtsi`
- SoC pins: soc_gpio32_pq5 (Pin 29), soc_gpio33_pq6 (Pin 31)
