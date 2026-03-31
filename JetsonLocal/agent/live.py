import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "models" / "component_best.pt"

model = YOLO(str(MODEL_PATH))


def gstreamer_pipeline():
    return (
        "nvarguscamerasrc ! "
        "video/x-raw(memory:NVMM), width=1920, height=1080, framerate=30/1 ! "
        "nvvidconv ! "
        "video/x-raw, width=1920, height=1080, format=BGRx ! "
        "videoconvert ! "
        "video/x-raw, format=BGR ! appsink drop=true max-buffers=1"
    )


def main():
    cap = cv2.VideoCapture(gstreamer_pipeline(), cv2.CAP_GSTREAMER)

    if not cap.isOpened():
        raise RuntimeError("Could not open Jetson CSI camera.")

    print("Live detection running. Press q to quit.")
    print(f"Using model: {MODEL_PATH}")

    kernel = np.array([
        [0, -1, 0],
        [-1, 5, -1],
        [0, -1, 0]
    ], dtype=np.float32)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame")
            break

        display_frame = cv2.filter2D(frame, -1, kernel)

        h, w = display_frame.shape[:2]

        infer_size = 640
        infer_frame = cv2.resize(display_frame, (infer_size, infer_size))

        results = model(infer_frame, verbose=False, conf=0.25)

        annotated = display_frame.copy()

        scale_x = w / infer_size
        scale_y = h / infer_size

        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())

                label = model.names[cls_id]

                x1 = int(x1 * scale_x)
                x2 = int(x2 * scale_x)
                y1 = int(y1 * scale_y)
                y2 = int(y2 * scale_y)

                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(
                    annotated,
                    f"{label} {conf:.2f}",
                    (x1, max(25, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA,
                )

        cv2.imshow("AURA Live Detection", annotated)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            cv2.imwrite(str(BASE_DIR / "live_capture.jpg"), annotated)
            print("Saved live_capture.jpg")
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()