#!/bin/bash
# GMSL 카메라 드라이버 자동 로드 스크립트
# 재부팅 시 자동 실행되도록 systemd 서비스로 등록 필요

# 스크립트 위치에서 DRIVER_DIR 자동 감지
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DRIVER_DIR="$SCRIPT_DIR/SG4A-NONX-G2Y-A1_ORIN_NANO_YUV_JP6.2_L4TR36.4.3/ko"

# 로그 디렉토리
LOG_FILE="/tmp/gmsl_driver_load.log"

echo "===== GMSL Driver Load Started: $(date) =====" >> $LOG_FILE

# max96712 모듈 로드
if ! lsmod | grep -q max96712; then
    echo "[$(date)] Loading max96712 module..." >> $LOG_FILE
    sudo insmod $DRIVER_DIR/max96712.ko >> $LOG_FILE 2>&1
    if [ $? -eq 0 ]; then
        echo "[$(date)] max96712 loaded successfully" >> $LOG_FILE
    else
        echo "[$(date)] ERROR: Failed to load max96712" >> $LOG_FILE
        exit 1
    fi
else
    echo "[$(date)] max96712 already loaded" >> $LOG_FILE
fi

# gmsl2 모듈 로드 (모드 2,2,2,2 = GMSL2/3G)
if ! lsmod | grep -q gmsl2; then
    echo "[$(date)] Loading sgx-yuv-gmsl2 module with mode 2,2,2,2..." >> $LOG_FILE
    sudo insmod $DRIVER_DIR/sgx-yuv-gmsl2.ko GMSLMODE_1=2,2,2,2 >> $LOG_FILE 2>&1
    if [ $? -eq 0 ]; then
        echo "[$(date)] sgx-yuv-gmsl2 loaded successfully" >> $LOG_FILE
    else
        echo "[$(date)] ERROR: Failed to load sgx-yuv-gmsl2" >> $LOG_FILE
        exit 1
    fi
else
    echo "[$(date)] sgx-yuv-gmsl2 already loaded" >> $LOG_FILE
fi

# 카메라 장치 확인
sleep 2
echo "[$(date)] Checking camera devices:" >> $LOG_FILE
ls -l /dev/video* >> $LOG_FILE 2>&1

echo "===== GMSL Driver Load Completed: $(date) =====" >> $LOG_FILE
