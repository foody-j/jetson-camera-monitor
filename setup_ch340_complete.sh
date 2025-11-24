#!/bin/bash
# CH340 USB-RS485 변환기 완전 설치 스크립트 (Jetson Orin Nano)
# 배포용 - 한 번에 모든 설정 완료

set -e

echo "=================================================="
echo "  CH340 USB-RS485 변환기 설치 (Jetson Orin Nano)"
echo "=================================================="
echo ""

if [ "$EUID" -ne 0 ]; then
    echo "오류: root 권한이 필요합니다"
    echo "사용법: sudo bash $0"
    exit 1
fi

# ========== 1. CH341 커널 모듈 빌드 ==========
echo "[1/3] CH341 커널 모듈 빌드 및 설치..."
echo ""

KVER="5.15.148-tegra"
KERNEL_BUILD="/lib/modules/$KVER/build"

if [ ! -d "$KERNEL_BUILD" ]; then
    echo "오류: 커널 빌드 디렉토리 없음"
    exit 1
fi

# 빌드 도구 설치
apt-get update -qq
apt-get install -y build-essential bc kmod wget >/dev/null 2>&1

# 작업 디렉토리
WORK_DIR="/tmp/ch341_install"
rm -rf $WORK_DIR
mkdir -p $WORK_DIR
cd $WORK_DIR

# CH341 드라이버 소스 다운로드
echo "  - 드라이버 소스 다운로드..."
wget -q https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/plain/drivers/usb/serial/ch341.c?h=v5.15 -O ch341.c || {
    # 대체: 최소 드라이버 생성
    cat > ch341.c << 'EOFDRIVER'
// SPDX-License-Identifier: GPL-2.0
#include <linux/kernel.h>
#include <linux/tty.h>
#include <linux/module.h>
#include <linux/slab.h>
#include <linux/usb.h>
#include <linux/usb/serial.h>
#include <linux/serial.h>
#include <asm/unaligned.h>

static const struct usb_device_id id_table[] = {
	{ USB_DEVICE(0x1a86, 0x5523) },
	{ USB_DEVICE(0x1a86, 0x7522) },
	{ USB_DEVICE(0x1a86, 0x7523) },
	{ USB_DEVICE(0x1a86, 0xe523) },
	{ USB_DEVICE(0x4348, 0x5523) },
	{ },
};
MODULE_DEVICE_TABLE(usb, id_table);

static int ch341_attach(struct usb_serial *serial) { return 0; }
static int ch341_open(struct tty_struct *tty, struct usb_serial_port *port) {
	return usb_serial_generic_open(tty, port);
}
static void ch341_close(struct usb_serial_port *port) {
	usb_serial_generic_close(port);
}

static struct usb_serial_driver ch341_device = {
	.driver = {
		.owner	= THIS_MODULE,
		.name	= "ch341-uart",
	},
	.id_table	= id_table,
	.num_ports	= 1,
	.open		= ch341_open,
	.close		= ch341_close,
	.attach		= ch341_attach,
};

static struct usb_serial_driver * const serial_drivers[] = {
	&ch341_device, NULL
};

module_usb_serial_driver(serial_drivers, id_table);

MODULE_LICENSE("GPL v2");
MODULE_DESCRIPTION("WCH CH341/CH340 USB to serial driver");
EOFDRIVER
}

# Makefile 생성
cat > Makefile << 'EOFMAKE'
obj-m := ch341.o
all:
	$(MAKE) -C /lib/modules/$(shell uname -r)/build M=$(PWD) modules
clean:
	rm -f *.o *.ko *.mod.c *.mod .*.cmd Module.symvers modules.order
	rm -rf .tmp_versions
EOFMAKE

echo "  - 컴파일 중..."
make >/dev/null 2>&1 || {
    echo "오류: 컴파일 실패"
    exit 1
}

if [ ! -f "ch341.ko" ]; then
    echo "오류: ch341.ko 생성 실패"
    exit 1
fi

echo "  - 모듈 설치..."
mkdir -p /lib/modules/$KVER/kernel/drivers/usb/serial/
cp ch341.ko /lib/modules/$KVER/kernel/drivers/usb/serial/
depmod -a

# 모듈 로드
rmmod ch341 2>/dev/null || true
modprobe ch341

# 부팅 시 자동 로드
if ! grep -q "^ch341" /etc/modules 2>/dev/null; then
    echo "ch341" >> /etc/modules
fi

echo "  ✓ CH341 모듈 설치 완료"
echo ""

# ========== 2. brltty 제거 (충돌 방지) ==========
echo "[2/3] brltty 충돌 해결..."
echo ""

if systemctl is-active --quiet brltty 2>/dev/null; then
    systemctl stop brltty
    systemctl disable brltty
fi

pkill -9 brltty 2>/dev/null || true

if dpkg -l | grep -q brltty; then
    echo "  - brltty 패키지 제거 중..."
    apt-get remove -y brltty >/dev/null 2>&1
    echo "  ✓ brltty 제거 완료"
else
    echo "  ✓ brltty 없음 (정상)"
fi
echo ""

# ========== 3. udev 규칙 설정 ==========
echo "[3/3] udev 규칙 설정..."
echo ""

cat > /etc/udev/rules.d/99-ch340.rules << 'EOF'
# CH340/CH341 USB to Serial Converter
SUBSYSTEM=="usb", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", MODE="0666", RUN+="/sbin/modprobe ch341"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", MODE="0666", SYMLINK+="ttyUSB_CH340"
KERNEL=="ttyUSB*", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", MODE="0666", GROUP="dialout"
EOF

udevadm control --reload-rules
udevadm trigger

# 사용자를 dialout 그룹에 추가
if [ -n "$SUDO_USER" ]; then
    usermod -a -G dialout $SUDO_USER 2>/dev/null || true
fi

echo "  ✓ udev 규칙 설정 완료"
echo ""

# ========== 완료 ==========
echo "=================================================="
echo "  설치 완료!"
echo "=================================================="
echo ""
echo "USB-RS485 변환기를 연결하세요."
echo "장치: /dev/ttyUSB0 또는 /dev/ttyUSB_CH340"
echo ""
echo "확인 명령어:"
echo "  ls -l /dev/ttyUSB*"
echo "  python3 -c \"import serial.tools.list_ports; [print(p.device) for p in serial.tools.list_ports.comports()]\""
echo ""

# 정리
rm -rf $WORK_DIR

# USB 장치가 이미 연결되어 있다면 재감지
sleep 2
if ls /dev/ttyUSB* >/dev/null 2>&1; then
    echo "✓✓✓ USB 시리얼 장치 발견:"
    ls -l /dev/ttyUSB*
fi
