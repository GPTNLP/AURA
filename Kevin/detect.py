import os
print("Current working directory:", os.getcwd())

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
print("Changed working directory to:", os.getcwd())

from ultralytics import YOLO
import cv2


def main():
    # -------- Load BOTH models --------
    component_model = YOLO("component_best.pt")     # your original component detector
    color_model     = YOLO("colorcode_best.pt")     # your resistor-value model (new)

    # (Optional) quick sanity print
    # print("Component classes:", component_model.names)
    # print("Color-code classes:", color_model.names)

    # -------- Performance knobs --------
    CAM_W, CAM_H, CAM_FPS = 640, 480, 30
    INFER_EVERY = 4          # run YOLO every N frames
    IMGSZ = 640              # component model imgsz: try 640, 512, 416
    CONF = 0.5
    COLOR_IMGSZ = 320        # smaller is faster for cropped resistor
    COLOR_CONF = 0.5
    # ----------------------------------

    # Your original (unused) gst string kept intact
    gst = (
        "nvarguscamerasrc sensor-id=0 ! "
        f"video/x-raw(memory:NVMM), width={CAM_W}, height={CAM_H}, framerate={CAM_FPS}/1 ! "
        "nvvidconv ! video/x-raw, format=BGRx ! "
        "videoconvert ! video/x-raw, format=BGR ! "
        "appsink drop=1 sync=false max-buffers=1"
    )

    # Your original VideoCapture (kept intact)
    cap = cv2.VideoCapture(
        "nvarguscamerasrc sensor-id=0 ! "
        "video/x-raw(memory:NVMM), width=1920, height=1080, framerate=30/1 ! "
        "nvvidconv ! video/x-raw, format=BGRx ! "
        "videoconvert ! video/x-raw, format=BGR ! appsink",
        cv2.CAP_GSTREAMER
    )

    if not cap.isOpened():
        print("Error: Could not open CSI camera.")
        return

    win = "YOLOv8  Electronic Components"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    print("Press 'q' to quit (or close the window).")

    frame_i = 0
    last_result = None  # store last component detections
    last_frame_for_result = None  # store the frame used for last_result inference

    # Helper: safe clamp
    def clamp(v, lo, hi):
        return max(lo, min(hi, v))

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame.")
            break

        frame_i += 1

        # Run component inference every N frames
        if (frame_i % INFER_EVERY) == 0 or last_result is None:
            last_frame_for_result = frame.copy()
            last_result = component_model.predict(
                last_frame_for_result, conf=CONF, imgsz=IMGSZ, verbose=False
            )[0]

        # Always display the *current* live frame
        display = frame.copy()

        # Draw component detections on current frame
        if last_result is not None:
            display = last_result.plot(img=display)

            # ----- Stage 2: if resistor found, run color model on cropped ROI -----
            # Note: we use the CURRENT frame for crop so it lines up with display.
            # If you'd rather use the exact frame used for last_result, replace `frame` with `last_frame_for_result`.
            H, W = frame.shape[:2]

            for box in last_result.boxes:
                cls_id = int(box.cls[0])
                comp_label = component_model.names.get(cls_id, str(cls_id))

                # Adjust this if your class name isn't exactly "resistor"
                if comp_label.lower() != "resistor":
                    continue

                x1, y1, x2, y2 = map(int, box.xyxy[0])

                # Clamp to image bounds (prevents crashes)
                x1 = clamp(x1, 0, W - 1)
                x2 = clamp(x2, 0, W - 1)
                y1 = clamp(y1, 0, H - 1)
                y2 = clamp(y2, 0, H - 1)

                # Ensure valid box
                if x2 <= x1 or y2 <= y1:
                    continue

                crop = frame[y1:y2, x1:x2]
                if crop.size == 0:
                    continue

                # Run colorcode/value model on cropped resistor
                value_result = color_model.predict(
                    crop, conf=COLOR_CONF, imgsz=COLOR_IMGSZ, verbose=False
                )[0]

                if value_result is None or value_result.boxes is None or len(value_result.boxes) == 0:
                    # If you want, show "unknown" above resistor
                    # cv2.putText(display, "unknown resistor", (x1, max(0, y1 - 10)),
                    #             cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    continue

                # Take the highest-confidence prediction from the crop
                best_idx = int(value_result.boxes.conf.argmax())
                value_cls = int(value_result.boxes.cls[best_idx])
                value_name = color_model.names.get(value_cls, str(value_cls))

                # Format text how you want
                spoken_text = value_name.replace(" ohms", "") + " resistor"

                # Put text above the resistor bbox
                cv2.putText(
                    display,
                    spoken_text,
                    (x1, max(0, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2
                )

        cv2.imshow(win, display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break

        if frame_i > 10:
            vis = cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE)
            if vis >= 0 and vis < 1:
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

