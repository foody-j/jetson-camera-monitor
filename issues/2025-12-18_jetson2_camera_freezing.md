# Jetson2 카메라 프리징 이슈

**Date:** 2025-12-18
**Status:** 해결됨 (모니터링 중)
**Location:** Jetson2 (현장 PC)

---

## 환경

- **Device:** NVIDIA Jetson Orin Nano
- **OS:** Ubuntu 22.04, L4T 36.4.3
- **카메라:** GMSL 4대 (video0~video3)
- **드라이버:** sgx_yuv_gmsl2, max96712

---

## 증상

4개 카메라 동시 사용 시 시스템 프리징 발생.
- GUI 멈춤
- 카메라 프레임 중단
- 시스템 응답 없음

---

## 원인 분석

### dmesg 에러 로그

```
tegra194-vi5 13e00000.host1x:vi1@14c00000: IVC capture submit failed
tegra-camrtc-capture-vi tegra-capture-vi: uncorr_err: request timed out after 2500 ms
tegra-camrtc-capture-vi tegra-capture-vi: err_rec: attempting to reset the capture channel
tegra194-vi5 13e00000.host1x:vi1@14c00000: vi_capture_release: control failed, errno 1
video4linux video1: vi capture release failed
tegra-camrtc-capture-vi tegra-capture-vi: fatal: error recovery failed
```

### 근본 원인

**IVC (Inter-VM Communication) 채널 과부하**
- 4개 GMSL 카메라 동시 30fps 스트리밍
- Camera RTCPU와 메인 프로세서 간 통신 실패
- 드라이버 에러 복구 실패 → 시스템 프리징

---

## 시도한 해결책

### 1. 전력 모드 변경

| 모드 | 결과 |
|------|------|
| 25W | ❌ 프리징 |
| 15W | ⚠️ 일시적 안정, 이후 프리징 |
| MAXN | 테스트 안함 |

→ **전력 모드는 근본 원인 아님**

### 2. FPS 낮추기 (30fps → 15fps)

❌ 카메라 작동 안함 (GMSL 드라이버 제한)

### 3. 카메라 초기화 딜레이 증가 ✓

**변경 내용:**
```python
# 변경 전
CAMERA_INIT_DELAY = 2.0  # 초

# 변경 후
CAMERA_INIT_DELAY = 4.0  # 초 (현장 IVC 채널 과부하 방지)
```

**파일:** `jetson2_frying_ai/JETSON2_INTEGRATED.py:1461`

→ **현재 안정적으로 동작 중**

---

## 프리징 후 복구 방법

프리징 발생 시 IVC 채널이 망가져서 카메라 초기화 실패함.

### 방법 1: 재부팅 (권장)
```bash
sudo reboot
```

### 방법 2: 드라이버 리로드
```bash
sudo modprobe -r sgx_yuv_gmsl2 max96712
sudo modprobe sgx_yuv_gmsl2 max96712
```

---

## 랩 PC vs 현장 PC 비교

| 항목 | 랩 PC | 현장 PC |
|------|-------|---------|
| 하드웨어 | 동일 | 동일 |
| 카메라 | 4대 | 4대 |
| 프리징 | ❌ 없음 | ✅ 발생 |

**차이점 추정:**
1. 전원 품질 (주방 환경, 전압 변동)
2. 환경 온도 (주방이 더 더움)
3. 개별 기기 품질 차이

---

## 관련 커밋

- `bb67d93` - Increase camera init delay to 4s for IVC stability

---

## 모니터링 항목

1. 프리징 재발 여부
2. 딜레이 4초로 충분한지
3. 장시간 운영 안정성

---

## 추가 조치 (필요시)

1. 딜레이 더 증가 (4초 → 5초, 6초)
2. 카메라 3대로 운영 (observe 1대 비활성화)
3. 현장 PC 교체
4. UPS 설치 (전원 안정화)
