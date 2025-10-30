# -*- coding: utf-8 -*-
# 실행 흐름:
#  1) 실행 시 Tkinter UI로 모드/시간을 설정한다.
#  2) 카메라/YOLO/배경차분기를 초기화한다.
#  3) 루프:
#     - 현재 시각이 '주간'이면 YOLO로 person을 연속 DETECTION_HOLD_SEC(기본 30초) 동안 감지 시 1회 ON 출력
#     - '야간'이면
#         (a) 밤으로 전환된 뒤, '사람 미감지 10분 연속'이 달성될 때까지 YOLO로 계속 확인
#             → 10분 연속 미감지 시 OFF 1회 출력 후 스냅샷 모드로 전환
#         (b) 스냅샷 모드에서는 배경차분 기반으로 모션 감지 시 프레임 저장

from ultralytics import YOLO
import cv2
from datetime import datetime, time as dtime, timedelta
import time
import os

# ============ 새로 추가: 간단한 시간/모드 설정 UI ============
import tkinter as tk
from tkinter import ttk, messagebox

def _parse_hhmm(txt: str):
    """
    'HH:MM' 형식을 '시/분(int, int)'로 변환.
    - 형식 및 범위(00:00~23:59) 검증 후 정수 튜플 반환.
    """
    txt = txt.strip()
    if len(txt) != 5 or txt[2] != ":":
        raise ValueError("형식은 HH:MM 이어야 합니다.")
    hh = int(txt[:2]); mm = int(txt[3:])
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError("시간은 00:00~23:59 범위여야 합니다.")
    return hh, mm

def get_user_settings():
    """
    실행 시 1회 호출되는 설정 UI.
    - 모드: 자동/주간 강제/야간 강제
    - 주간 시작/종료 시각
    - 확인 시 settings dict 반환, 취소 시에도 현재까지 값 반환
    """
    settings = {"force_mode": None, "start_h":7, "start_m":30, "end_h":19, "end_m":30}
    done = {"ok": False}

    root = tk.Tk()
    root.title("YOLO ROBOT - 시간/모드 설정")
    root.resizable(False, False)

    frm = ttk.Frame(root, padding=12)
    frm.grid(row=0, column=0)

    # 모드 라디오 버튼
    ttk.Label(frm, text="모드 선택").grid(row=0, column=0, sticky="w")
    mode_var = tk.StringVar(value="auto")  # auto/day/night
    modes = [("자동(실시간)", "auto"), ("주간 강제", "day"), ("야간 강제", "night")]
    for i, (label, val) in enumerate(modes, start=1):
        ttk.Radiobutton(frm, text=label, value=val, variable=mode_var).grid(row=0, column=i, padx=(6,0), sticky="w")

    # 주간 시작/종료 시간 입력
    ttk.Label(frm, text="주간 시작 (HH:MM)").grid(row=1, column=0, sticky="w", pady=(10,0))
    start_entry = ttk.Entry(frm, width=8); start_entry.insert(0, "07:30")
    start_entry.grid(row=1, column=1, sticky="w", pady=(10,0))

    ttk.Label(frm, text="주간 종료 (HH:MM)").grid(row=1, column=2, sticky="w", padx=(12,0), pady=(10,0))
    end_entry = ttk.Entry(frm, width=8); end_entry.insert(0, "19:30")
    end_entry.grid(row=1, column=3, sticky="w", pady=(10,0))

    # 확인/취소 버튼 동작
    btn_frm = ttk.Frame(frm); btn_frm.grid(row=2, column=0, columnspan=4, sticky="e", pady=(14,0))
    def on_ok():
        try:
            sh, sm = _parse_hhmm(start_entry.get())
            eh, em = _parse_hhmm(end_entry.get())
            mv = mode_var.get()
            settings["force_mode"] = None if mv == "auto" else mv
            settings["start_h"], settings["start_m"] = sh, sm
            settings["end_h"], settings["end_m"] = eh, em
            done["ok"] = True
            root.destroy()
        except Exception as e:
            messagebox.showerror("입력 오류", str(e))
    def on_cancel():
        root.destroy()
    ttk.Button(btn_frm, text="취소", command=on_cancel).grid(row=0, column=0, padx=6)
    ttk.Button(btn_frm, text="확인", command=on_ok).grid(row=0, column=1)

    root.mainloop()
    return settings

# =========================
# 🔧 테스트/운영 기본값 (UI로 덮어씀)
# =========================
FORCE_MODE = None                 # "day" / "night" 지정 시 강제, None이면 자동
DAY_START = dtime(7, 30)          # 주간 시작 시각
DAY_END   = dtime(19, 30)         # 주간 종료 시각
MODEL_PATH = "yolo12n.pt"         # YOLO 가중치 경로

# 야간(모션) 감지 파라미터
SNAPSHOT_DIR = "Detection"        # 스냅샷 저장 루트 폴더
SAVE_COOLDOWN_SEC = 10            # 스냅샷 최소 저장 간격(초)
MOTION_MIN_AREA = 1500            # 모션으로 인정할 최소 컨투어 면적
MOG2_HISTORY = 500                # 배경차분 history 길이
MOG2_VARTHRESH = 16               # 작을수록 민감(8~16 권장)
BINARY_THRESH = 200               # 전경 이진화 임계값
WARMUP_FRAMES = 30                # 배경 학습 워밍업 프레임 수

# 주간 YOLO 설정
YOLO_CONF = 0.7                   # person 감지 confidence 임계값
YOLO_IMGSZ = 640                  # YOLO 입력 해상도(성능/속도 trade-off)

# 디스플레이 설정(카메라 해상도 그대로, 창만 리사이즈)
WIN_NAME = "YOLOv12 ROBOT Monitor"
WIN_W, WIN_H = 1280, 720

# 연속 감지 요구 시간(초)
DETECTION_HOLD_SEC = 30

# =========================
# 유틸 함수
# =========================
def ensure_dir(path: str):
    """폴더가 없으면 생성."""
    os.makedirs(path, exist_ok=True)

def is_daytime(now: datetime, start_t: dtime, end_t: dtime) -> bool:
    """
    현재(now)가 주간 구간[start_t, end_t]에 포함되는지 판정.
    - 같은 날 기준으로 비교. (자정 교차는 고려하지 않음)
    """
    today_start = now.replace(hour=start_t.hour, minute=start_t.minute, second=0, microsecond=0)
    today_end   = now.replace(hour=end_t.hour,   minute=end_t.minute,   second=0, microsecond=0)
    return today_start <= now <= today_end

def mode_override(now: datetime, force_mode, start_t: dtime, end_t: dtime) -> bool:
    """
    모드 판정:
    - force_mode == "day"  -> 항상 주간(True)
    - force_mode == "night"-> 항상 야간(False)
    - force_mode == None   -> 시간대 기반 자동 주/야 판정
    반환: True=주간, False=야간
    """
    if force_mode == "day":
        return True
    if force_mode == "night":
        return False
    return is_daytime(now, start_t, end_t)

# =========================
# (1) 설정 UI 띄우고 값 반영
# =========================
_user = get_user_settings()
FORCE_MODE = _user["force_mode"]
DAY_START = dtime(_user["start_h"], _user["start_m"])
DAY_END   = dtime(_user["end_h"],   _user["end_m"])

print(f"[CONFIG] mode={FORCE_MODE or 'auto'} | day={DAY_START.strftime('%H:%M')}~{DAY_END.strftime('%H:%M')}")

# =========================
# (2) 초기화
# =========================
model = YOLO(MODEL_PATH)  # YOLO 모델 로드

cap = cv2.VideoCapture(1)  # 카메라 인덱스 1 사용 (Jetson에서 테스트 완료)
# cap.set(3, 640); cap.set(4, 480)  # 필요시 캡처 해상도 강제

# 표시 창 생성 및 크기 설정(원본은 유지, 창만 확대)
cv2.namedWindow(WIN_NAME, cv2.WINDOW_NORMAL)
cv2.resizeWindow(WIN_NAME, WIN_W, WIN_H)

# 야간 모션 감지용 구성요소(배경차분기/모폴로지 커널)
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
bg = cv2.createBackgroundSubtractorMOG2(
    history=MOG2_HISTORY, varThreshold=MOG2_VARTHRESH, detectShadows=True
)
frame_idx = 0
last_snapshot_tick = None  # 마지막 스냅샷 저장 시간(monotonic)

# 상태 변수
on_triggered = False          # 주간 ON 1회만 출력하기 위한 플래그
det_hold_start = None         # 주간 person '연속 감지' 시작 시각

# === 야간 초반 '연속 미감지 10분' 확인 구간 상태 ===
night_check_active = False          # 현재 확인 구간 동작 중인지
night_no_person_deadline = None     # ✅ '사람 미감지 10분' 데드라인 시간 (사람 감지되면 갱신)
off_triggered_once = False          # OFF 1회만 출력

prev_daytime = None  # 이전 루프의 주/야 상태(전환 감지용)

# =========================
# (3) 메인 루프
# =========================
try:
    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            print("Camera read failed. Exiting...")
            break

        now = datetime.now()
        daytime = mode_override(now, FORCE_MODE, DAY_START, DAY_END)

        # --- 주/야 전환 감지 초기화 ---
        if prev_daytime is None:
            prev_daytime = daytime

        # 낮 -> 밤 전환 시: '연속 미감지 10분' 타이머 시작
        if (prev_daytime is True) and (daytime is False):
            night_check_active = True
            night_no_person_deadline = now + timedelta(minutes=10)  # ✅ 시작 시점 기준 10분
            det_hold_start = None           # 낮 연속감지 타이머 리셋
            off_triggered_once = False      # OFF 재출력 방지 플래그 리셋

        # 밤 -> 낮 전환 시: 주간 상태 리셋
        if (prev_daytime is False) and (daytime is True):
            on_triggered = False
            det_hold_start = None
            night_check_active = False
            night_no_person_deadline = None
            off_triggered_once = False

        prev_daytime = daytime

        # ---------- 주간: YOLO로 person 연속 감지 시 ON ----------
        if daytime:
            # YOLO 추론(프레임 단건)
            results = model.predict(frame, conf=YOLO_CONF, imgsz=YOLO_IMGSZ, verbose=False)
            r = results[0]

            # 'person' 클래스 포함 여부 확인
            detected = False
            if r.boxes is not None and r.boxes.cls is not None and len(r.boxes.cls) > 0:
                detected = any(r.names.get(int(c), "") == "person" for c in r.boxes.cls)

            # 연속 감지 시간 누적/판정
            if detected:
                if det_hold_start is None:
                    det_hold_start = now
                else:
                    hold_sec = (now - det_hold_start).total_seconds()
                    if hold_sec >= DETECTION_HOLD_SEC and not on_triggered:
                        print("ON !!!")     # ON은 1회만
                        on_triggered = True
            else:
                det_hold_start = None        # 감지가 끊기면 타이머 리셋

            vis = r.plot()                   # 감지 시각화 프레임
            mode_text = "DAY: YOLO(person; 30s hold)"

        # ---------- 야간 ----------
        else:
            frame_idx += 1

            # 1) '연속 미감지 10분'이 달성될 때까지 YOLO로 계속 확인 (스냅샷 없음)
            if night_check_active:
                results = model.predict(frame, conf=YOLO_CONF, imgsz=YOLO_IMGSZ, verbose=False)
                r = results[0]

                detected = False
                if r.boxes is not None and r.boxes.cls is not None and len(r.boxes.cls) > 0:
                    detected = any(r.names.get(int(c), "") == "person" for c in r.boxes.cls)

                if detected:
                    # ✅ 사람이 한 번이라도 보이면 '미감지 10분' 타이머를 다시 now+10분으로 리셋
                    night_no_person_deadline = now + timedelta(minutes=10)

                # ✅ 데드라인을 넘길 때까지 한 번도 감지되지 않았다면 OFF 후 스냅샷 모드로 전환
                if (night_no_person_deadline is not None) and (now >= night_no_person_deadline):
                    if not off_triggered_once:
                        print("OFF !!!")
                        off_triggered_once = True
                    night_check_active = False  # 확인 구간 종료 → 스냅샷 모드로 전환
                    # 이후 night_no_person_deadline은 사용하지 않음
                    night_no_person_deadline = None

                vis = r.plot()
                # 남은 시간 표시(디버깅에 도움): 데드라인 존재 시
                if night_check_active and night_no_person_deadline is not None:
                    remain = int((night_no_person_deadline - now).total_seconds())
                    mode_text = f"NIGHT: YOLO check until 10min no-person (remain {remain}s)"
                else:
                    mode_text = "NIGHT: YOLO check until 10min no-person"

            # 2) 스냅샷 모드: 배경차분 기반 스냅샷 저장
            else:
                # 배경 학습 워밍업 구간은 단순 표시만
                if frame_idx <= WARMUP_FRAMES:
                    vis = frame.copy()
                else:
                    # 배경차분 → 이진화 → 잡영 제거 → 컨투어 탐색
                    fg = bg.apply(frame)
                    _, thr = cv2.threshold(fg, BINARY_THRESH, 255, cv2.THRESH_BINARY)
                    clean = cv2.morphologyEx(thr, cv2.MORPH_OPEN, kernel, iterations=1)
                    contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                    motion = False
                    vis = frame.copy()
                    for cnt in contours:
                        area = cv2.contourArea(cnt)
                        if area >= MOTION_MIN_AREA:
                            x, y, w, h = cv2.boundingRect(cnt)
                            cv2.rectangle(vis, (x, y), (x+w, y+h), (0, 255, 0), 2)
                            motion = True

                    # 모션 감지 시 스냅샷 저장(쿨다운 적용)
                    if motion:
                        now_tick = time.monotonic()
                        can_save = (last_snapshot_tick is None) or ((now_tick - last_snapshot_tick) >= SAVE_COOLDOWN_SEC)
                        if can_save:
                            day_dir = now.strftime("%Y%m%d")
                            ts_name = now.strftime("%H%M%S")
                            out_dir = os.path.join(SNAPSHOT_DIR, day_dir)
                            os.makedirs(out_dir, exist_ok=True)
                            out_path = os.path.join(out_dir, f"{ts_name}.jpg")
                            cv2.imwrite(out_path, frame)
                            last_snapshot_tick = now_tick
                            print(f"[Detection] Motion detected at {now.strftime('%Y-%m-%d %H:%M:%S')} -> {out_path}")

                mode_text = "NIGHT: MOTION-DETECT (snapshots)"

        # ---------- 디스플레이 ----------
        vis = cv2.resize(vis, (WIN_W, WIN_H))
        sub = (f"time={now.strftime('%H:%M:%S')} | "
               f"{'forced='+FORCE_MODE if FORCE_MODE else 'auto'} | "
               f"day={DAY_START.strftime('%H:%M')}~{DAY_END.strftime('%H:%M')}")
        cv2.putText(vis, mode_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255,255,255), 2, cv2.LINE_AA)
        cv2.putText(vis, sub, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2, cv2.LINE_AA)

        cv2.imshow(WIN_NAME, vis)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

finally:
    # 자원 정리
    cap.release()
    cv2.destroyAllWindows()
