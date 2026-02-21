import cv2
from ultralytics import YOLO

#camera
#REPLACE WITH SAM at earliest convenience
model = YOLO("yolov11s-face.pt")
cap = cv2.VideoCapture(0)
#value of how much of the screen should be used for centering
pct = 50
while True: #iterate forever (add sleep function later)
    ret, frame = cap.read()
    h, w = frame.shape[:2]

    #Ignore the height, we dont care if the robot is looked up/down upon right now.
    leftBound = int(w*((100-pct)/2)/100)
    rightBound = int(w*((100+pct)/2)/100)

    #use model to determine if a face
    results = model(frame, conf=0.4)
    res = results[0]
    out = frame.copy()

    #Draw central column for visualization
    cv2.rectangle(out, (leftBound, 0), (rightBound, h), (255, 0, 0), 2)
    cv2.putText(out, f"center column ({pct}%)", (leftBound + 6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
    boxes = getattr(res, "boxes", None)

    if boxes is not None and len(boxes): #A face is present
        xyxy = boxes.xyxy
        confs = boxes.conf

        #To build a box
        for i, (x1, y1, x2, y2) in enumerate(xyxy):
            x1, y1, x2, y2 = map(int, (x1, y1, x2, y2))
            cx = (x1 + x2) // 2 

            inside = leftBound <= cx <= rightBound
            color = (0, 255, 0) if inside else (0, 0, 255)

            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
            cv2.circle(out, (cx, (y1 + y2) // 2), 3, color, -1)

            conf = confs[i] if confs is not None else None
            label = f"face{f' {conf:.2f}' if conf is not None else ''}"
            cv2.putText(out, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            cv2.putText(out, "centered" if inside else "off-center", (x1, y2 + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    else: #A face is not present
        cv2.putText(out, "!!No face detected!!", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

    cv2.imshow("Facial detection", out)
    if (cv2.waitKey(1) & 0xFF == ord("q")) or cv2.getWindowProperty("Facial detection", cv2.WND_PROP_VISIBLE) < 1:
        break #kill if either the q key is pressed or the window is manually closed

cap.release()
cv2.destroyAllWindows() #good credit