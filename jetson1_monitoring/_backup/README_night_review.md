# 야간 감지 리뷰 기능 (백업)

**상태**: 개발 완료 - 통합 대기

## 기능 설명

야간(18:00~07:00) 동안 감지된 사진들을 아침 지정 시간에 슬라이드쇼로 보여주는 기능

## 파일 구성

```
_backup/
├── night_review_module.py      # 메인 모듈
├── night_review_config_example.json  # 설정 예시
└── README_night_review.md      # 이 파일
```

## 통합 방법

### 1. config.json에 설정 추가

```json
{
  "night_review_enabled": true,
  "night_review_time": "08:00",
  "night_review_duration_min": 10,
  "night_review_auto_archive": true
}
```

### 2. JETSON1_INTEGRATED.py에 import 추가

```python
from _backup.night_review_module import NightReviewManager
```

### 3. __init__ 에서 매니저 생성

```python
# 야간 리뷰 매니저 초기화
self.night_review_manager = NightReviewManager(self, config)
```

### 4. 메인 루프에서 체크 호출

```python
# update_frame() 또는 별도 타이머에서
self.night_review_manager.check_review_time()
```

## 화면 구성

```
┌─────────────────────────────────────┐
│  🌙 야간 감지 리뷰 (12건)  자동 종료: 09:45  │
├─────────────────────────────────────┤
│                                     │
│          [감지 사진]                  │
│                                     │
├─────────────────────────────────────┤
│  📅 20251217  ⏰ 02:34:15  📂 023415.jpg  │
├─────────────────────────────────────┤
│  [◀ 이전]     3 / 12     [다음 ▶]    │
├─────────────────────────────────────┤
│  [🗑 삭제]  [📁 아카이브]      [✕ 닫기] │
└─────────────────────────────────────┘
```

## 독립 테스트

```bash
cd ~/jetson-food-ai/jetson1_monitoring
python3 _backup/night_review_module.py
```

테스트 창이 뜨고 "리뷰 창 열기" 버튼으로 기능 확인 가능

## 야간 시간대 정의

- **저녁**: 18:00 ~ 23:59 (전날)
- **새벽**: 00:00 ~ 06:59 (당일)

## 저장 경로

- 원본: `~/Detection/YYYYMMDD/HHMMSS.jpg`
- 아카이브: `~/Detection/YYYYMMDD/reviewed/HHMMSS.jpg`
