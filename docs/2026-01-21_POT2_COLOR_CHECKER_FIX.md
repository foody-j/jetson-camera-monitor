# POT2 Color Checker 수정 작업 기록

**날짜:** 2026-01-21
**담당자:** Claude Code + youngjin
**상태:** ✅ 완료

## 문제 상황

Jetson2 INTEGRATED 시스템에서 POT2(우측 튀김솥) 색상 변화 측정이 작동하지 않는 문제 발생:
- GUI에 "색상변화: --" 만 표시됨
- 색상 변화 값이 전혀 업데이트되지 않음
- AI 기능 전체가 작동하지 않는 것으로 보임

## 진단 과정

### 1단계: 에러 로깅 추가
**커밋:** `4812b5d` (2026-01-21 10:16:57)

**문제 발견:**
- 기존 코드에서 `except: pass`로 모든 에러를 조용히 무시
- 실제 에러가 발생해도 사용자가 알 수 없음

**변경 내용:**
```python
# Before
except:
    pass

# After
except Exception as e:
    print(f"[POT2 색상] 예외 발생: {type(e).__name__}: {e}")
    self.frying_right_color_diff_label.config(text="색상변화: ERR")
```

**결과:** 에러 메시지 출력 가능하도록 개선했으나 여전히 메시지가 나오지 않음

---

### 2단계: Color Checker 결과 전체 로깅
**커밋:** `73646a6` (2026-01-21 10:26:40)

**추가 디버깅:**
```python
color_result = self.color_checker_right.measure(frame)
print(f"[POT2 색상 DEBUG] color_result = {color_result}")  # DEBUG
```

**결과:** 디버그 메시지조차 출력되지 않음 → 코드 자체가 실행되지 않는 것으로 판단

---

### 3단계: 카메라 및 상태 플래그 로깅
**커밋:** `7878541` (2026-01-21 10:34:00)

**추가 디버깅:**
```python
ret, frame = self.frying_right_cap.read()
print(f"[POT2 카메라 DEBUG] ret={ret}, frying_running={self.frying_running}, pot2_collecting={self.pot2_collecting}")
```

**결과:**
- 조리 중: `pot2_collecting=True` 확인됨
- 하지만 색상 체크 코드는 여전히 실행 안 됨

---

### 4단계: 근본 원인 발견 및 수정
**커밋:** `08391f2` (2026-01-21 10:52:01)

**근본 원인:**
```python
# POT2(우측) 카메라 처리 함수에서
if self.frying_running or self.pot1_collecting:  # ← 잘못된 조건!
    # 색상 체크 코드 실행
```

**문제:**
- POT2 카메라인데 `pot1_collecting` 상태를 체크
- POT2만 단독으로 조리 중일 때 `pot1_collecting=False`
- 따라서 색상 체크 코드가 실행되지 않음

**해결책:**
```python
# POT1 (좌측) 카메라
if self.frying_running or self.pot1_collecting:
    # 색상 체크...

# POT2 (우측) 카메라
if self.frying_running or self.pot2_collecting:  # ← 수정!
    # 색상 체크...
```

---

## 최종 수정 내용

### 파일: `jetson2_frying_ai/JETSON2_INTEGRATED.py`

#### 1. POT1 카메라 (1883번 줄)
```python
if self.frying_running or self.pot1_collecting:
```

#### 2. POT2 카메라 (2023번 줄)
```python
if self.frying_running or self.pot2_collecting:  # pot1 → pot2로 수정
```

#### 3. 에러 로깅 개선 (1957-1960번 줄, 2092-2095번 줄)
```python
else:
    # Error case
    self.frying_right_color_diff_label.config(text="색상변화: --")
    print(f"[POT2 색상] 에러: {color_result.get('error', 'unknown')}")
except Exception as e:
    print(f"[POT2 색상] 예외 발생: {type(e).__name__}: {e}")
    self.frying_right_color_diff_label.config(text="색상변화: ERR")
```

---

## 작동 원리

### Color Checker (SimpleColorChecker)

1. **Baseline 설정 (CHARGING 시작 시):**
   - 첫 프레임에서 튀김의 초기 색상 저장
   - HSV 색공간으로 변환하여 통계치 추출

2. **실시간 측정 (조리 중):**
   - 매 프레임마다 현재 색상과 기준 색상 비교
   - 가중 유클리드 거리 계산:
     ```python
     color_diff = 2.0 * delta_h + 0.5 * delta_s + 1.5 * delta_v
     ```

3. **DISCHARGE 조건 판정:**
   ```python
   if (running_time >= target_time) and (color_diff >= 25.0):
       # 배출 신호 전송
   ```

### HSV 마스킹
- **색상 범위:** (8, 40, 80) ~ (30, 255, 255)
- **대상:** 노란색~주황색 튀김 영역만 추출
- **후처리:** Morphology (open/close) 노이즈 제거

---

## 테스트 방법

### 현장 배포
```bash
cd ~/jetson-food-ai
git pull
cd jetson2_frying_ai
python3 JETSON2_INTEGRATED.py
```

### 정상 작동 시 터미널 출력
```
[POT2 카메라 DEBUG] ret=True, frying_running=False, pot2_collecting=True
[POT2 색상 DEBUG] color_result = {'color_diff': 8.5, 'current_color': {...}, 'progress_pct': 34.0}
```

### GUI 확인
- "색상변화: 8.5" (실시간 업데이트)
- "Progress: 34%" (시각화)
- Color Diff >= 25.0 시 자동 DISCHARGE

---

## 커밋 이력

| 커밋 | 시간 | 내용 |
|------|------|------|
| `4812b5d` | 10:16:57 | 에러 로깅 추가 (silent exception 제거) |
| `73646a6` | 10:26:40 | Color checker 결과 전체 로깅 |
| `7878541` | 10:34:00 | 카메라/상태 플래그 디버깅 로깅 |
| `08391f2` | 10:52:01 | **근본 원인 수정 (pot1 → pot2)** |

---

## 교훈

1. **Silent Exception의 위험성**
   - `except: pass`는 디버깅을 극도로 어렵게 만듦
   - 최소한 `except Exception as e: print(e)` 필요

2. **변수명 일관성**
   - POT1/POT2 독립적인 상태 관리 필요
   - 공유 변수와 독립 변수의 명확한 구분

3. **점진적 디버깅**
   - 코드 실행 경로를 단계별로 추적
   - 로그를 통해 실제 실행 여부 확인

---

## 향후 작업

- [ ] 디버그 로그 제거 또는 DEBUG 플래그로 제어
- [ ] POT1/POT2 독립성 코드 리뷰
- [ ] Color threshold (25.0) 현장 테스트 및 조정

---

**문서 작성:** 2026-01-21
**마지막 업데이트:** 2026-01-21
