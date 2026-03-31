import time
import cv2
from ultralytics import YOLO

from camera import JetsonCamera


def main():
    component_model = YOLO("../Kevin/component_best.pt")
    color_model = YOLO("../Kevin/colorcode_best.pt")

    print("Models loaded.")

    cam = JetsonCamera()
    cam.start()

    print("Camera started. Press q to quit.")

    last_log_time = 0

    try:
        while True:
            frame = cam.get_frame()
            if frame is None:
                time.sleep(0.01)
                continue

            annotated = frame.copy()
            detections = []

            results = component_model(frame, conf=0.4, verbose=False)

            for r in results:
                for box in r.boxes:
                    cls_id = int(box.cls[0])
                    label = component_model.names[cls_id]
                    conf = float(box.conf[0])

                    x1, y1, x2, y2 = map(int, box.xyxy[0])

                    detections.append(label)

                    cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(
                        annotated,
                        f"{label} {conf:.2f}",
                        (x1, max(y1 - 10, 20)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 0),
                        2,
                    )

                    if "resistor" in label.lower():
                        crop = frame[y1:y2, x1:x2]
                        if crop.size > 0:
                            color_results = color_model(crop, conf=0.3, verbose=False)

                            for cr in color_results:
                                for cbox in cr.boxes:
                                    c_cls = int(cbox.cls[0])
                                    c_label = color_model.names[c_cls]
                                    cx1, cy1, cx2, cy2 = map(int, cbox.xyxy[0])

                                    abs_x1 = x1 + cx1
                                    abs_y1 = y1 + cy1
                                    abs_x2 = x1 + cx2
                                    abs_y2 = y1 + cy2

                                    cv2.rectangle(
                                        annotated,
                                        (abs_x1, abs_y1),
                                        (abs_x2, abs_y2),
                                        (255, 0, 0),
                                        2,
                                    )
                                    cv2.putText(
                                        annotated,
                                        c_label,
                                        (abs_x1, max(abs_y1 - 8, 20)),
                                        cv2.FONT_HERSHEY_SIMPLEX,
                                        0.5,
                                        (255, 0, 0),
                                        2,
                                    )

            now = time.time()
            if now - last_log_time > 1.0:
                print("Detections:", detections)
                last_log_time = now

            cv2.imshow("AURA Live Detection", annotated)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                cv2.imwrite("detection_result_live.jpg", annotated)
                print("Saved detection_result_live.jpg")
                break

    finally:
        cam.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()