from typing import Dict, Any
from config import CAMERA_READY_DEFAULT


def get_camera_status() -> Dict[str, Any]:
    return {
        "camera_ready": CAMERA_READY_DEFAULT
    }