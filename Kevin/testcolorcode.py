import os
print("Current working directory:", os.getcwd())

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
print("Changed working directory to:", os.getcwd())

from ultralytics import YOLO
import cv2


def main():
    # -------- Load ONLY color code model --------
    model = YOLO("colorcode_best.pt")

    # -------- Performance knobs --------
    CAM_W, CAM_H, CAM_FPS = 1280, 720, 30   # <- use 720p for smoother live YOLO
    INFER_EVERY = 4
    IMGSZ = 640
    CONF = 0.5
    # ----------------------------------

    gst = (
        "nvarguscamerasrc sensor-id=0 ! "
        f"video/x-raw(memory:NVMM), width={CAM_W}, height={CAM_H}, framerate={CAM_FPS}/1 ! "
        "nvvidconv ! video/x-raw, format=BGRx ! "
        "videoconvert ! video/x-raw, format=BGR ! "
        "appsink drop=true sync=false"
    )

    cap = cv2.VideoCapture(gst, cv2.CAP_GSTREAMER)

    if not cap.isOpened():
        print("Error: Could not open CSI camera.")
        return

    win = "YOLOv8  Resistor Color Code Detection"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    print("Press 'q' to quit.")

    frame_i = 0
    last_result = None

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            print("Failed to grab frame.")
            break

        frame_i += 1

        # Run inference every N frames
        if (frame_i % INFER_EVERY) == 0 or last_result is None:
            last_result = model.predict(
                frame,
                conf=CONF,
                imgsz=IMGSZ,
                verbose=False
            )[0]

        display = frame.copy()

        if last_result is not None:
            display = last_result.plot(img=display)

        cv2.imshow(win, display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break

        if frame_i > 10:
            vis = cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE)
            if 0 <= vis < 1:
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
