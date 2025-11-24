# GPIO 출력 문제 해결 가이드

## 문제 상황
Jetson Orin Nano Super Developer Kit에서 GPIO 핀으로 출력이 되지 않는 문제 발생

```python
import Jetson.GPIO as GPIO
GPIO.setmode(GPIO.BOARD)
GPIO.setup(7, GPIO.OUT)
GPIO.output(7, GPIO.HIGH)  # 출력이 안됨!
```

## 원인
JetPack 6.2에서는 GPIO 핀이 기본적으로 **bidirectional(양방향)**로 설정되어 있지 않음.
Device Tree에서 해당 핀을 GPIO 모드로 명시적으로 활성화해야 함.

## 해결 방법

### 1단계: Device Tree Overlay 파일 준비
`jetson-orin-gpio-patch` 디렉토리에 Pin 7용 overlay 파일이 포함되어 있음:
- `pin7_as_gpio.dts` - Device Tree 소스 파일
- `pin7_as_gpio.dtbo` - 컴파일된 overlay 파일

### 2단계: Device Tree Overlay 컴파일 (이미 완료된 경우 스킵)
```bash
cd jetson-orin-gpio-patch
dtc -O dtb -o pin7_as_gpio.dtbo pin7_as_gpio.dts
```

### 3단계: Overlay 파일을 /boot에 복사
```bash
sudo cp pin7_as_gpio.dtbo /boot/
```

### 4단계: jetson-io.py로 Overlay 활성화
```bash
sudo /opt/nvidia/jetson-io/jetson-io.py
```

실행 후:
1. **Configure Jetson 40pin Header** 선택
2. **Pin 7 gpio bidirectional** 찾아서 활성화 (스페이스바로 선택)
3. **Save and reboot** 선택

### 5단계: 재부팅
```bash
sudo reboot
```

### 6단계: 테스트
재부팅 후 테스트 스크립트 실행:
```bash
cd jetson-food-ai
python3 gpio_test.py
```

멀티미터로 Pin 7 측정 시 3.3V 출력 확인!

## Jetson.GPIO 라이브러리 설치
```bash
sudo apt update
sudo apt install python3 python3-pip -y
sudo pip install --upgrade Jetson.GPIO
```

### GPIO 그룹 권한 설정 (sudo 없이 사용하려면)
```bash
sudo usermod -a -G gpio $USER
```
재부팅 또는 로그아웃/로그인 필요

### 라이브러리 확인
```bash
python3 -c "import Jetson.GPIO; print(Jetson.GPIO.__version__)"
```

## 참고 자료
- [GitHub Issue #120 - NVIDIA/jetson-gpio](https://github.com/NVIDIA/jetson-gpio/issues/120)
- [JetsonHacks - Device Tree Overlays on Jetson](https://jetsonhacks.com/2025/04/07/device-tree-overlays-on-jetson-scary-but-fun/)
- jetson-orin-gpio-patch 디렉토리의 README.md

## 문제 해결 팁
- overlay가 제대로 적용되었는지 확인: `cat /boot/extlinux/extlinux.conf`에서 `FDT` 줄에 overlay가 추가되었는지 확인
- GPIO 핀이 다른 장치와 충돌하지 않는지 확인
- 다른 핀을 사용하려면 해당 핀용 DTS 파일을 수정하여 새로운 overlay 생성 필요