import os
import sys
import time
from pathlib import Path
from typing import Optional

import cv2


SENSOR_ID = 0
WIDTH = 1280
HEIGHT = 720
FPS = 30
FLIP_METHOD = 0
PROBE_SECONDS = 8
SAVE_DIR = Path(__file__).resolve().parent / "camera_test_output"


def build_argus_pipeline(
    sensor_id: int = SENSOR_ID,
    width: int = WIDTH,
    height: int = HEIGHT,
    fps: int = FPS,
    flip_method: int = FLIP_METHOD,
    sensor_mode: Optional[int] = None,
    use_bufapi: bool = True,
) -> str:
    sensor_mode_part = f"sensor-mode={sensor_mode} " if sensor_mode is not None else ""
    bufapi_part = "bufapi-version=true " if use_bufapi else ""

    return (
        f"nvarguscamerasrc sensor-id={sensor_id} {sensor_mode_part}{bufapi_part}! "
        f"video/x-raw(memory:NVMM), "
        f"width=(int){width}, "
        f"height=(int){height}, "
        f"format=(string)NV12, "
        f"framerate=(fraction){fps}/1 ! "
        f"queue max-size-buffers=1 leaky=downstream ! "
        f"nvvidconv flip-method={flip_method} ! "
        f"video/x-raw, "
        f"width=(int){width}, "
        f"height=(int){height}, "
        f"format=(string)BGRx ! "
        f"videoconvert ! "
        f"video/x-raw, format=(string)BGR ! "
        f"appsink drop=true max-buffers=1 sync=false"
    )


def build_v4l2_pipeline(
    device: str = "/dev/video0",
    width: int = WIDTH,
    height: int = HEIGHT,
    fps: int = FPS,
) -> str:
    return (
        f"v4l2src device={device} ! "
        f"video/x-raw, "
        f"width=(int){width}, "
        f"height=(int){height}, "
        f"framerate=(fraction){fps}/1 ! "
        f"videoconvert ! "
        f"video/x-raw, format=(string)BGR ! "
        f"appsink drop=true max-buffers=1 sync=false"
    )


def probe_capture(cap: cv2.VideoCapture, name: str, seconds: int = PROBE_SECONDS) -> bool:
    start = time.time()
    frames = 0
    first_frame = None
    last_frame = None

    while time.time() - start < seconds:
        ok, frame = cap.read()
        if ok and frame is not None and getattr(frame, "size", 0) > 0:
            if first_frame is None:
                first_frame = frame.copy()
            last_frame = frame.copy()
            frames += 1
            print(f"[{name}] frame {frames}: shape={frame.shape}")
        else:
            print(f"[{name}] no frame")
        time.sleep(0.03)

    if frames == 0:
        return False

    SAVE_DIR.mkdir(parents=True, exist_ok=True)

    if first_frame is not None:
        cv2.imwrite(str(SAVE_DIR / f"{name}_first.jpg"), first_frame)

    if last_frame is not None:
        cv2.imwrite(str(SAVE_DIR / f"{name}_last.jpg"), last_frame)

    print(f"[{name}] success, captured {frames} frames")
    print(f"[{name}] saved images to: {SAVE_DIR}")
    return True


def try_pipeline(name: str, pipeline: str) -> bool:
    print("\n" + "=" * 80)
    print(f"TRYING: {name}")
    print(pipeline)
    print("=" * 80)

    cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

    if not cap.isOpened():
        print(f"[{name}] FAILED: cap did not open")
        return False

    try:
        time.sleep(1.5)
        success = probe_capture(cap, name)
        if not success:
            print(f"[{name}] FAILED: opened, but no usable frames")
            return False
        return True
    finally:
        cap.release()
        time.sleep(1.0)


def main() -> int:
    print("OpenCV version:", cv2.__version__)
    print("Python version:", sys.version)
    print("Save dir:", SAVE_DIR)

    pipelines = [
        (
            "argus_bufapi_auto",
            build_argus_pipeline(
                sensor_id=SENSOR_ID,
                width=WIDTH,
                height=HEIGHT,
                fps=FPS,
                flip_method=FLIP_METHOD,
                sensor_mode=None,
                use_bufapi=True,
            ),
        ),
        (
            "argus_legacy_auto",
            build_argus_pipeline(
                sensor_id=SENSOR_ID,
                width=WIDTH,
                height=HEIGHT,
                fps=FPS,
                flip_method=FLIP_METHOD,
                sensor_mode=None,
                use_bufapi=False,
            ),
        ),
        (
            "argus_bufapi_mode_3",
            build_argus_pipeline(
                sensor_id=SENSOR_ID,
                width=WIDTH,
                height=HEIGHT,
                fps=FPS,
                flip_method=FLIP_METHOD,
                sensor_mode=3,
                use_bufapi=True,
            ),
        ),
        (
            "argus_legacy_mode_3",
            build_argus_pipeline(
                sensor_id=SENSOR_ID,
                width=WIDTH,
                height=HEIGHT,
                fps=FPS,
                flip_method=FLIP_METHOD,
                sensor_mode=3,
                use_bufapi=False,
            ),
        ),
        (
            "v4l2_dev_video0",
            build_v4l2_pipeline(
                device="/dev/video0",
                width=WIDTH,
                height=HEIGHT,
                fps=FPS,
            ),
        ),
        (
            "v4l2_dev_video1",
            build_v4l2_pipeline(
                device="/dev/video1",
                width=WIDTH,
                height=HEIGHT,
                fps=FPS,
            ),
        ),
    ]

    passed = []

    for name, pipeline in pipelines:
        try:
            ok = try_pipeline(name, pipeline)
            if ok:
                passed.append(name)
        except Exception as e:
            print(f"[{name}] EXCEPTION: {e}")
            time.sleep(1.0)

    print("\n" + "#" * 80)
    print("RESULTS")
    print("#" * 80)

    if passed:
        print("Working pipelines:")
        for name in passed:
            print(f"  - {name}")
        return 0

    print("No pipelines produced usable frames.")
    print("Check:")
    print("  1. camera ribbon seating")
    print("  2. no other process is holding Argus")
    print("  3. /dev/video* availability")
    print("  4. nvargus-daemon health")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())