import os
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from ultralytics import YOLO


class YoloService:
    """
    Loads YOLO models once, reuses for all requests.
    Designed for FastAPI endpoint usage.
    """

    def __init__(
        self,
        component_weights: str = "component_best.pt",
        color_weights: str = "colorcode_best.pt",
        component_conf: float = 0.5,
        component_imgsz: int = 640,
        color_conf: float = 0.5,
        color_imgsz: int = 320,
    ):
        self.component_conf = component_conf
        self.component_imgsz = component_imgsz
        self.color_conf = color_conf
        self.color_imgsz = color_imgsz

        # Resolve weights relative to this file (backend folder)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        comp_path = component_weights if os.path.isabs(component_weights) else os.path.join(base_dir, component_weights)
        color_path = color_weights if os.path.isabs(color_weights) else os.path.join(base_dir, color_weights)

        if not os.path.exists(comp_path):
            raise RuntimeError(f"Missing component model weights: {comp_path}")
        if not os.path.exists(color_path):
            raise RuntimeError(f"Missing color model weights: {color_path}")

        self.component_model = YOLO(comp_path)
        self.color_model = YOLO(color_path)

    @staticmethod
    def _clamp(v: int, lo: int, hi: int) -> int:
        return max(lo, min(hi, v))

    def predict(self, bgr: np.ndarray) -> Dict[str, Any]:
        """
        Returns component detections + optional resistor value text for resistors.
        """
        H, W = bgr.shape[:2]

        comp_res = self.component_model.predict(
            bgr,
            conf=self.component_conf,
            imgsz=self.component_imgsz,
            verbose=False,
        )[0]

        detections: List[Dict[str, Any]] = []

        # Safety: if no boxes
        if comp_res is None or comp_res.boxes is None or len(comp_res.boxes) == 0:
            return {"width": W, "height": H, "detections": detections}

        for box in comp_res.boxes:
            cls_id = int(box.cls[0])
            label = self.component_model.names.get(cls_id, str(cls_id))
            conf = float(box.conf[0])

            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0]]
            x1 = self._clamp(x1, 0, W - 1)
            x2 = self._clamp(x2, 0, W - 1)
            y1 = self._clamp(y1, 0, H - 1)
            y2 = self._clamp(y2, 0, H - 1)
            if x2 <= x1 or y2 <= y1:
                continue

            det: Dict[str, Any] = {
                "label": label,
                "confidence": conf,
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
            }

            # Stage 2: if resistor, run color model on ROI
            if str(label).lower() == "resistor":
                crop = bgr[y1:y2, x1:x2]
                if crop.size != 0:
                    val_res = self.color_model.predict(
                        crop,
                        conf=self.color_conf,
                        imgsz=self.color_imgsz,
                        verbose=False,
                    )[0]

                    if val_res is not None and val_res.boxes is not None and len(val_res.boxes) > 0:
                        best_idx = int(val_res.boxes.conf.argmax())
                        value_cls = int(val_res.boxes.cls[best_idx])
                        value_name = self.color_model.names.get(value_cls, str(value_cls))

                        # match your teammate formatting idea
                        spoken_text = str(value_name).replace(" ohms", "") + " resistor"
                        det["resistor_value"] = value_name
                        det["spoken_text"] = spoken_text

            detections.append(det)

        return {"width": W, "height": H, "detections": detections}


def decode_image_bytes(image_bytes: bytes) -> np.ndarray:
    """
    Supports jpg/png bytes -> BGR image.
    """
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image")
    return img