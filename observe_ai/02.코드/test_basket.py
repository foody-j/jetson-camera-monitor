import time
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


# ================== 사용자 설정 ==================
SEG_MODEL_PATH = r"C:\Users\sfwoo\runs\segment\train12\weights\best.pt"  # 바스켓 세그 best.pt
CLS_MODEL_PATH = r"C:\Users\sfwoo\runs\classify\train1\weights\best.pt" # filled/empty 분류 best.pt

CAM_INDEX = 0                 # 보통 0
FRAME_W, FRAME_H = 1920, 1536 # 가능하면 카메라 캡처 설정(안 먹히면 자동)
SEG_IMGSZ = 640               # 세그 추론 입력 크기 (CPU면 640 추천)
CLS_IMGSZ = 224               # 분류 입력 크기 (224~256 추천)
SEG_CONF = 0.25               # 세그 confidence (오탐 많으면 0.35~0.5)
CLS_SMOOTH_N = 7              # 분류 결과 스무딩(최근 N프레임 다수결)
INNER_MARGIN = 0.15           # 바스켓 bbox에서 내부만 쓰는 비율(테두리 제거)
PAD = 10                      # bbox 약간 여유
USE_MASK_OVERLAY = True       # 화면에 마스크 테두리/채우기 표시
USE_MASK_FOR_CROP = False     # 내부 ROI 만들 때 마스크 기반(느림) vs bbox 기반(빠름)
# =================================================


def clamp_int(v, lo, hi):
    return max(lo, min(int(v), hi))


def pick_rightmost(boxes_xyxy: np.ndarray) -> int:
    """xyxy(N,4)에서 중심 x가 가장 큰 인덱스"""
    cx = (boxes_xyxy[:, 0] + boxes_xyxy[:, 2]) / 2.0
    return int(np.argmax(cx))


def square_crop(img, x1, y1, x2, y2):
    """사각형을 중심 기준으로 정사각형으로 맞춰(비율 유지) 크롭"""
    H, W = img.shape[:2]
    w = x2 - x1
    h = y2 - y1
    side = max(w, h)
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    nx1 = clamp_int(cx - side / 2, 0, W - 1)
    ny1 = clamp_int(cy - side / 2, 0, H - 1)
    nx2 = clamp_int(cx + side / 2, 0, W - 1)
    ny2 = clamp_int(cy + side / 2, 0, H - 1)
    if nx2 <= nx1 or ny2 <= ny1:
        return None
    return img[ny1:ny2, nx1:nx2].copy(), (nx1, ny1, nx2, ny2)


def overlay_mask(frame, mask01: np.ndarray, alpha=0.35):
    """0/1 마스크를 화면에 덧칠(색은 고정이지만 기능용)"""
    # mask01: HxW, dtype=bool or 0/1
    if mask01.dtype != np.uint8:
        m = (mask01.astype(np.uint8) * 255)
    else:
        m = mask01 * 255 if mask01.max() <= 1 else mask01

    colored = frame.copy()
    colored[m > 0] = (0, 255, 0)  # 초록
    return cv2.addWeighted(frame, 1 - alpha, colored, alpha, 0)


def majority_vote(seq):
    if not seq:
        return None
    # 가장 많이 나온 값
    return max(set(seq), key=seq.count)


def main():
    seg_model = YOLO(SEG_MODEL_PATH)
    cls_model = YOLO(CLS_MODEL_PATH)

    cap = cv2.VideoCapture(CAM_INDEX, cv2.CAP_DSHOW)  # 윈도우면 DSHOW가 안정적인 경우 많음
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)

    if not cap.isOpened():
        print("Camera open failed.")
        return

    # 분류 결과 스무딩 버퍼
    cls_hist = []

    prev_t = time.time()
    while True:
        ok, frame = cap.read()
        if not ok:
            break

        H, W = frame.shape[:2]

        # -------- 1) 세그 추론 --------
        r = seg_model.predict(frame, imgsz=SEG_IMGSZ, conf=SEG_CONF, verbose=False)[0]

        state = "NO_BASKET"   # 외부로 넘기기 좋은 상태 값(신호 담당자가 사용 가능)
        chosen_bbox = None
        chosen_mask = None

        if r.boxes is not None and len(r.boxes) > 0:
            boxes = r.boxes.xyxy.cpu().numpy()  # (N,4)
            idx = pick_rightmost(boxes)
            x1, y1, x2, y2 = boxes[idx]

            # bbox 정리
            x1 = clamp_int(x1 - PAD, 0, W - 1)
            y1 = clamp_int(y1 - PAD, 0, H - 1)
            x2 = clamp_int(x2 + PAD, 0, W - 1)
            y2 = clamp_int(y2 + PAD, 0, H - 1)
            chosen_bbox = (x1, y1, x2, y2)

            # -------- 2) 화면 오버레이(테두리) --------
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)  # 노랑 박스

            if USE_MASK_OVERLAY and r.masks is not None and len(r.masks) > idx:
                # r.masks.data: (N, mh, mw) 모델 내부 해상도 기반
                m = r.masks.data[idx].cpu().numpy().astype(np.uint8)  # 0/1
                # 원본 크기로 리사이즈
                m = cv2.resize(m, (W, H), interpolation=cv2.INTER_NEAREST)
                chosen_mask = m
                frame = overlay_mask(frame, m, alpha=0.30)

            # -------- 3) 내부 ROI 만들기(비율 유지) --------
            bw = x2 - x1
            bh = y2 - y1
            mx = int(bw * INNER_MARGIN)
            my = int(bh * INNER_MARGIN)
            ix1 = clamp_int(x1 + mx, 0, W - 1)
            iy1 = clamp_int(y1 + my, 0, H - 1)
            ix2 = clamp_int(x2 - mx, 0, W - 1)
            iy2 = clamp_int(y2 - my, 0, H - 1)

            roi_img = None

            if ix2 > ix1 and iy2 > iy1:
                if USE_MASK_FOR_CROP and chosen_mask is not None:
                    # 마스크 기반 내부 ROI: 배경 제거 후 크롭(느림)
                    cut = frame.copy()
                    cut[chosen_mask == 0] = 0
                    # 내부 박스 영역
                    inner = cut[iy1:iy2, ix1:ix2].copy()
                    # 정사각 비율 유지
                    sq = square_crop(inner, 0, 0, inner.shape[1], inner.shape[0])
                    if sq is not None:
                        roi_img, _ = sq
                else:
                    # bbox 기반 내부 ROI(빠름)
                    inner = frame[iy1:iy2, ix1:ix2].copy()
                    sq = square_crop(inner, 0, 0, inner.shape[1], inner.shape[0])
                    if sq is not None:
                        roi_img, _ = sq

            # -------- 4) 분류(filled/empty) --------
            if roi_img is not None and roi_img.size > 0:
                # 분류 모델 입력 사이즈로 리사이즈
                roi_resized = cv2.resize(roi_img, (CLS_IMGSZ, CLS_IMGSZ), interpolation=cv2.INTER_AREA)

                cr = cls_model.predict(roi_resized, imgsz=CLS_IMGSZ, verbose=False)[0]
                # Ultralytics classify 결과: cr.probs.top1, cr.names
                top1 = int(cr.probs.top1)
                label = cr.names[top1]  # "filled" / "empty" 같은 클래스명
                conf = float(cr.probs.top1conf)

                # 스무딩(최근 N프레임 다수결)
                cls_hist.append(label)
                if len(cls_hist) > CLS_SMOOTH_N:
                    cls_hist.pop(0)

                smooth_label = majority_vote(cls_hist) or label
                state = smooth_label.upper()  # "FILLED" / "EMPTY"

                # 화면 표시
                cv2.putText(frame, f"IN_BASKET: {smooth_label} ({conf:.2f})",
                            (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2)

                # 작은 미리보기(우측 상단)
                thumb = cv2.resize(roi_resized, (240, 240), interpolation=cv2.INTER_AREA)
                frame[20:260, W-260:W-20] = thumb
                cv2.rectangle(frame, (W-260, 20), (W-20, 260), (255, 255, 255), 2)
            else:
                cls_hist.clear()
                cv2.putText(frame, "IN_BASKET: ROI_NOT_READY",
                            (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2)

        else:
            cls_hist.clear()
            cv2.putText(frame, "NO_BASKET_DETECTED",
                        (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2)

        # -------- FPS 표시 --------
        now = time.time()
        fps = 1.0 / max(1e-6, (now - prev_t))
        prev_t = now
        cv2.putText(frame, f"FPS: {fps:.1f}", (20, 110),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        # state는 여기서 신호 담당자에게 넘길 값이라고 보면 됨
        # 예: print(state)
        # print(state)

        cv2.imshow("Basket Seg + Fill/Empty", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == 27 or key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
