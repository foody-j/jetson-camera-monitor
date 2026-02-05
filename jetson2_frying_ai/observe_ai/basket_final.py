import cv2
import numpy as np
from ultralytics import YOLO

# ================== 사용자 설정 ==================
SEG_MODEL_PATH = r"C:\Users\sfwoo\Documents\02.cooperation\2.3.robotics\2.3.7.robopy3\test_bt_file\best_v3\left\best_io_l.pt"   # in/out 세그 best.pt
CLS_MODEL_PATH = r"C:\Users\sfwoo\Documents\02.cooperation\2.3.robotics\2.3.7.robopy3\test_bt_file\best_v3\left\best_fe_l.pt"  # filled/empty 분류 best.pt

CAM_INDEX = 0          # 보통 0, 다른 카메라면 1/2...
CAM_W = 1920
CAM_H = 1536
CAM_FPS = 30

SEG_IMGSZ = 640
SEG_CONF  = 0.25

CLS_IMGSZ = 224
INNER_MARGIN = 0.15    # bbox 내부만 쓰기(테두리/배경 영향 줄이기)
PAD = 10               # bbox 여백

USE_MASK_OVERLAY = True    # 세그 마스크 오버레이 표시
SHOW_ALL_DETS = True       # in/out 둘 다 화면에 표시
# =================================================


def clamp_int(v, lo, hi):
    return max(lo, min(int(v), hi))


def overlay_mask(frame, mask01: np.ndarray, alpha=0.30):
    m = (mask01.astype(np.uint8) * 255) if mask01.max() <= 1 else mask01.astype(np.uint8)
    colored = frame.copy()
    colored[m > 0] = (0, 255, 0)  # 초록
    return cv2.addWeighted(frame, 1 - alpha, colored, alpha, 0)


def square_crop(img):
    """입력 img를 중심 기준 정사각형으로 잘라 비율 유지"""
    h, w = img.shape[:2]
    side = min(h, w)
    x1 = (w - side) // 2
    y1 = (h - side) // 2
    return img[y1:y1 + side, x1:x1 + side].copy()


def open_camera(index=0, w=1920, h=1536, fps=30):
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)  # Windows면 CAP_DSHOW가 안정적인 경우 많음
    if not cap.isOpened():
        # DSHOW가 안 되면 기본으로 재시도
        cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        return None

    # 요청값(카메라가 지원 안 하면 무시될 수 있음)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
    cap.set(cv2.CAP_PROP_FPS,          fps)
    return cap


def main():
    seg_model = YOLO(SEG_MODEL_PATH)
    cls_model = YOLO(CLS_MODEL_PATH)

    cap = open_camera(CAM_INDEX, CAM_W, CAM_H, CAM_FPS)
    if cap is None:
        print(f"카메라 열기 실패: index={CAM_INDEX}")
        return

    win = "LIVE (Process Camera)"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            print("프레임 읽기 실패")
            break

        H, W = frame.shape[:2]
        out = frame.copy()

        # 1) 세그(in/out) 추론
        r = seg_model.predict(out, imgsz=SEG_IMGSZ, conf=SEG_CONF, verbose=False)[0]

        state_lines = []
        roi_thumb = None

        if r.boxes is None or len(r.boxes) == 0:
            state_lines.append("STATE: NO_BASKET")
        else:
            boxes_xyxy = r.boxes.xyxy.cpu().numpy()          # (N,4)
            confs = r.boxes.conf.cpu().numpy()               # (N,)
            cls_ids = r.boxes.cls.cpu().numpy().astype(int)  # (N,)
            names = r.names

            # 화면 표시용으로 det들을 confidence 내림차순 정렬
            order = np.argsort(-confs)

            # in/out 모두 표시
            if SHOW_ALL_DETS:
                for rank, i in enumerate(order, start=1):
                    x1, y1, x2, y2 = boxes_xyxy[i]
                    det_conf = float(confs[i])
                    cls_id = int(cls_ids[i])
                    cls_name = names[cls_id]

                    x1i = clamp_int(x1 - PAD, 0, W - 1)
                    y1i = clamp_int(y1 - PAD, 0, H - 1)
                    x2i = clamp_int(x2 + PAD, 0, W - 1)
                    y2i = clamp_int(y2 + PAD, 0, H - 1)

                    cv2.rectangle(out, (x1i, y1i), (x2i, y2i), (0, 255, 255), 2)
                    cv2.putText(out, f"{rank}) {cls_name} det_conf={det_conf:.2f}",
                                (x1i, max(0, y1i - 10)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

                    # 마스크 오버레이 (가능하면)
                    if USE_MASK_OVERLAY and (r.masks is not None) and (len(r.masks.data) > i):
                        m = r.masks.data[i].cpu().numpy().astype(np.uint8)
                        m = cv2.resize(m, (W, H), interpolation=cv2.INTER_NEAREST)
                        out = overlay_mask(out, m, alpha=0.25)

            # 2) filled/empty는 "in" 클래스에서만 수행
            in_indices = [i for i in range(len(cls_ids)) if ("in" in names[int(cls_ids[i])].lower())]

            if len(in_indices) == 0:
                state_lines.append("STATE: NO_IN (only OUT or none)")
            else:
                best_in = max(in_indices, key=lambda i: confs[i])

                x1, y1, x2, y2 = boxes_xyxy[best_in]
                det_conf = float(confs[best_in])
                cls_id = int(cls_ids[best_in])
                cls_name = names[cls_id]

                x1 = clamp_int(x1 - PAD, 0, W - 1)
                y1 = clamp_int(y1 - PAD, 0, H - 1)
                x2 = clamp_int(x2 + PAD, 0, W - 1)
                y2 = clamp_int(y2 + PAD, 0, H - 1)

                # 내부 ROI 계산
                bw = x2 - x1
                bh = y2 - y1
                mx = int(bw * INNER_MARGIN)
                my = int(bh * INNER_MARGIN)
                ix1 = clamp_int(x1 + mx, 0, W - 1)
                iy1 = clamp_int(y1 + my, 0, H - 1)
                ix2 = clamp_int(x2 - mx, 0, W - 1)
                iy2 = clamp_int(y2 - my, 0, H - 1)

                if ix2 <= ix1 or iy2 <= iy1:
                    state_lines.append(f"IN DETECTED ({cls_name} {det_conf:.2f}) but ROI invalid")
                else:
                    inner = frame[iy1:iy2, ix1:ix2].copy()
                    inner_sq = square_crop(inner)
                    inner_sq = cv2.resize(inner_sq, (CLS_IMGSZ, CLS_IMGSZ), interpolation=cv2.INTER_AREA)

                    # 3) 분류
                    cr = cls_model.predict(inner_sq, imgsz=CLS_IMGSZ, verbose=False)[0]
                    top1 = int(cr.probs.top1)
                    fe_label = cr.names[top1]
                    fe_conf = float(cr.probs.top1conf)

                    state_lines.append(f"IN: {cls_name} det_conf={det_conf:.2f}")
                    state_lines.append(f"FE: {fe_label.upper()} ({fe_conf:.2f})")

                    cv2.putText(out, f"FE={fe_label.upper()} {fe_conf:.2f}",
                                (x1, min(H - 10, y2 + 30)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 3)

                    roi_thumb = cv2.resize(inner_sq, (260, 260), interpolation=cv2.INTER_AREA)

                    cv2.rectangle(out, (ix1, iy1), (ix2, iy2), (255, 255, 255), 2)
                    cv2.putText(out, "INNER_ROI(for FE)", (ix1, max(0, iy1 - 10)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # 좌상단 상태 텍스트
        y0 = 50
        for line in state_lines:
            cv2.putText(out, line, (20, y0), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)
            y0 += 40

        # ROI 미리보기 (우상단)
        if roi_thumb is not None:
            out[20:280, W - 280:W - 20] = roi_thumb
            cv2.rectangle(out, (W - 280, 20), (W - 20, 280), (255, 255, 255), 2)
            cv2.putText(out, "ROI(224x224)", (W - 280, 310),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        cv2.imshow(win, out)

        key = cv2.waitKey(1) & 0xFF
        if key == 27 or key == ord('q'):   # ESC or q 종료
            break
        # 's' 누르면 현재 프레임 저장
        if key == ord('s'):
            cv2.imwrite("snapshot.jpg", out)
            print("Saved snapshot.jpg")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
