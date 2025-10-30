# fry_cam_seg_cls_test.py
# 목적:
#  1) YOLOv8 세그 모델로 바스켓 윤곽선 검출
#  2) 바스켓 ROI를 YOLOv8 분류 모델로 empty/filled 판정
#  3) 결과를 화면에 오버레이하고, 상태 변화 시 콘솔에 신호 로그만 출력

# 키:
# ESC: 종료
# s: 현재 프레임과 ROI 저장

import cv2
import numpy as np
import time
from ultralytics import YOLO
from collections import deque
from datetime import datetime

#  사용자 설정 
SEG_MODEL = r"C:/Users/sfwoo/runs/segment/train2/weights/besa.pt"  # 바스켓 세그 모델 파일 위치
CLS_MODEL = r"C:/Users/sfwoo/cls_dataset/runs/classify/train/weights/bestb.pt"   # empty/filled 분류 모델 파일 위치
IMG_SIZE_SEG = 640   # 세그 추론 해상도
IMG_SIZE_CLS = 224   # 분류 추론 해상도
CONF_SEG = 0.5       # 세그 최소 신뢰도
VOTE_N = 7           # 최근 N프레임 다수결
POSITIVE_LABEL = "filled"  # 분류모델에서 "재료 있음"에 해당하는 라벨명

# === 모델 로드 ===
seg_model = YOLO(SEG_MODEL)
cls_model = YOLO(CLS_MODEL)

# 분류 클래스 이름 확인
cls_names = getattr(cls_model.model, "names", None) or getattr(cls_model, "names", None)
print("[INFO] Classify model names:", cls_names)

# === 카메라 설정 ===
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))

# 수동 노출/화이트밸런스 고정
cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)   
cap.set(cv2.CAP_PROP_EXPOSURE, -3)
cap.set(cv2.CAP_PROP_AUTO_WB, 0)
cap.set(cv2.CAP_PROP_WB_TEMPERATURE, 4500)
cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)

time.sleep(2)  # 설정 반영 대기

def largest_contour(mask, min_area=2000):
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    cnt = max(cnts, key=cv2.contourArea)
    if cv2.contourArea(cnt) < min_area:
        return None
    return cnt

def log_signal(state: str):
    # 상태 변화 시 콘솔 로그 
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] SIGNAL -> {state}")

votes = deque(maxlen=VOTE_N)
last_state = None  # "FILLED" / "EMPTY" 상태 변화 감지용

print("[INFO] Press 's' to save current frame/ROI, ESC to quit.")

while True:
    ok, frame = cap.read()
    if not ok:
        break

    vis = frame.copy()
    H, W = frame.shape[:2]

    # 1) 세그로 바스켓 마스크 획득
    r = seg_model.predict(frame, imgsz=IMG_SIZE_SEG, conf=CONF_SEG, verbose=False)[0]
    basket_mask = np.zeros((H, W), np.uint8)

    if r.masks is not None:
        for i, cls_idx in enumerate(r.boxes.cls.cpu().numpy().astype(int)):
            if r.names[cls_idx] == "basket":
                m = (r.masks.data[i].cpu().numpy() > 0.5).astype(np.uint8) * 255
                m = cv2.resize(m, (W, H), interpolation=cv2.INTER_NEAREST)
                basket_mask = np.maximum(basket_mask, m)

    detected = False
    is_filled_frame = False
    roi = None

    if basket_mask.any():
        basket_mask = cv2.morphologyEx(basket_mask, cv2.MORPH_CLOSE, np.ones((5,5), np.uint8), iterations=1)
        cnt = largest_contour(basket_mask)
        if cnt is not None:
            detected = True
            cv2.drawContours(vis, [cnt], -1, (0,255,255), 2)
            cv2.putText(vis, "Basket Detected", (16, 32), 0, 1, (0,255,0), 2)

            # 2) 바스켓 ROI 크롭
            x, y, w, h = cv2.boundingRect(cnt)
            x2, y2 = x + w, y + h
            x, y = max(0, x), max(0, y)
            x2, y2 = min(W, x2), min(H, y2)
            roi = frame[y:y2, x:x2]

            # 3) 분류 추론 (empty / filled)
            cls_res = cls_model.predict(roi, imgsz=IMG_SIZE_CLS, conf=0.0, verbose=False)[0]
            top1_idx = int(cls_res.probs.top1)
            top1_name = cls_res.names[top1_idx]
            prob = float(cls_res.probs.top1conf)
            is_filled_frame = (top1_name.lower() == POSITIVE_LABEL.lower())

            # 표기
            cv2.putText(vis, f"CLS: {top1_name} ({prob:.2f})", (16, 70), 0, 1, (0,255,255), 2)
            cv2.rectangle(vis, (x, y), (x2, y2), (255, 128, 0), 2)

    # 4) 다수결 안정화 + 상태 변화 로그
    if detected:
        votes.append(is_filled_frame)
        filled_stable = (sum(votes) >= (len(votes)//2 + 1))
        state_txt = "FILLED" if filled_stable else "EMPTY"
        color = (0, 0, 255) if filled_stable else (200, 200, 200)
        cv2.putText(vis, f"STATUS: {state_txt}", (16, 110), 0, 1.2, color, 3)

        if state_txt != last_state:
            log_signal(state_txt)
            last_state = state_txt
    else:
        votes.clear()
        cv2.putText(vis, "Basket Not Found", (16, 32), 0, 1, (0,0,255), 2)
        if last_state is not None:
            log_signal("NO_BASKET")
            last_state = None

    cv2.imshow("Fry Cam Test (Seg+Cls)", vis)
    key = cv2.waitKey(1)
    if key == 27:  # ESC
        break
    elif key == ord('s'):
        ts = int(time.time())
        cv2.imwrite(f"frame_{ts}.jpg", vis)
        if roi is not None:
            cv2.imwrite(f"roi_{ts}.jpg", roi)
        print(f"[SAVE] frame_{ts}.jpg / roi_{ts}.jpg")

cap.release()
cv2.destroyAllWindows()
