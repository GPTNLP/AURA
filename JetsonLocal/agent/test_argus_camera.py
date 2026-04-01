import os
import time
import cv2


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def argus_pipeline(sensor_id: int, width: int, height: int, fps: int, flip_method: int) -> str:
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} ! "
        f"video/x-raw(memory:NVMM), "
        f"width=(int){width}, height=(int){height}, "
        f"format=(string)NV12, framerate=(fraction){fps}/1 ! "
        f"nvvidconv flip-method={flip_method} ! "
        f"video/x-raw, width=(int){width}, height=(int){height}, format=(string)BGRx ! "
        f"videoconvert ! "
        f"video/x-raw, format=(string)BGR ! "
        f"appsink drop=true max-buffers=1 sync=false"
    )


def main():
    sensor_id = env_int("CAMERA_SENSOR_ID", 0)
    width = env_int("CAMERA_WIDTH", 1280)
    height = env_int("CAMERA_HEIGHT", 720)
    fps = env_int("CAMERA_FPS", 30)
    flip_method = env_int("CAMERA_FLIP_METHOD", 0)

    pipeline = argus_pipeline(sensor_id, width, height, fps, flip_method)
    print("[INFO] opening pipeline:")
    print(pipeline)

    cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
    print("[INFO] cap.isOpened() =", cap.isOpened())

    if not cap.isOpened():
        print("[FAIL] Could not open pipeline")
        return

    print("[INFO] warming up...")
    for i in range(12):
        ret, frame = cap.read()
        print(f"[WARMUP {i+1}/12] ret={ret} frame_none={frame is None}")
        time.sleep(0.08)

    print("[INFO] probing frames...")
    good = 0
    for i in range(20):
        ret, frame = cap.read()
        ok = ret and frame is not None and getattr(frame, "size", 0) > 0
        print(f"[FRAME {i+1}/20] ret={ret} ok={ok}")
        if ok:
            print(f"[FRAME {i+1}] shape={frame.shape}")
            good += 1
        time.sleep(0.05)

    cap.release()

    if good > 0:
        print(f"[PASS] Got {good} usable frames")
    else:
        print("[FAIL] No usable frames received")


if __name__ == "__main__":
    main()