# backend/detect_api.py
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from fastapi import APIRouter, UploadFile, File, HTTPException, Request

from security import require_auth, require_ip_allowlist

router = APIRouter(tags=["detect"])
BACKEND_DIR = Path(__file__).resolve().parent

def _resolve_model_path(env_value: str, default_name: str) -> Path:
    s = (env_value or "").strip()
    if not s:
        return BACKEND_DIR / default_name
    p = Path(s)
    if p.is_absolute():
        return p
    parts = [x.lower() for x in p.parts]
    if len(parts) >= 2 and parts[0] in ("backend",) and parts[1] == default_name:
        return BACKEND_DIR / default_name
    return (BACKEND_DIR / p).resolve()

# Model paths (env-overridable)
COMPONENT_MODEL_PATH = _resolve_model_path(os.getenv("AURA_COMPONENT_MODEL", ""), "component_best.pt")
COLOR_MODEL_PATH = _resolve_model_path(os.getenv("AURA_COLOR_MODEL", ""), "colorcode_best.pt")

# Inference knobs (env-overridable)
COMP_CONF = float(os.getenv("AURA_DETECT_CONF", "0.50"))
COMP_IMGSZ = int(os.getenv("AURA_DETECT_IMGSZ", "640"))

COLOR_CONF = float(os.getenv("AURA_COLOR_CONF", "0.50"))
COLOR_IMGSZ = int(os.getenv("AURA_COLOR_IMGSZ", "320"))

AURA_YOLO_DEVICE = os.getenv("AURA_YOLO_DEVICE", "").strip()
RESISTOR_CLASS_NAME = os.getenv("AURA_RESISTOR_CLASS", "resistor").strip().lower()

_component_model = None
_color_model = None

def _import_ultralytics():
    try:
        from ultralytics import YOLO  # type: ignore
        return YOLO
    except Exception as e:
        raise RuntimeError(
            "ultralytics is not installed or failed to import. "
            "Install with: pip install ultralytics"
            f" (detail: {e})"
        )

def _load_models():
    global _component_model, _color_model
    YOLO = _import_ultralytics()

    if _component_model is None:
        if not COMPONENT_MODEL_PATH.exists():
            raise RuntimeError(f"component model not found: {COMPONENT_MODEL_PATH}")
        _component_model = YOLO(str(COMPONENT_MODEL_PATH))

    if _color_model is None:
        if not COLOR_MODEL_PATH.exists():
            raise RuntimeError(f"color model not found: {COLOR_MODEL_PATH}")
        _color_model = YOLO(str(COLOR_MODEL_PATH))

def _label_from_names(names: Any, cls_id: int) -> str:
    try:
        if isinstance(names, dict):
            return str(names.get(cls_id, cls_id))
        if isinstance(names, (list, tuple)):
            return str(names[cls_id])
    except Exception:
        pass
    return str(cls_id)

def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))

@router.post("/api/detect/predict")
async def detect_predict(request: Request, file: UploadFile = File(...)):
    require_ip_allowlist(request)
    require_auth(request)

    try:
        _load_models()
    except Exception as e:
        # 503 = service unavailable (missing ultralytics / model files)
        raise HTTPException(status_code=503, detail=f"Detect not ready: {e}")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")

    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Could not decode image")

    H, W = img.shape[:2]

    # 1) component inference
    predict_kwargs = dict(conf=COMP_CONF, imgsz=COMP_IMGSZ, verbose=False)
    if AURA_YOLO_DEVICE:
        predict_kwargs["device"] = AURA_YOLO_DEVICE

    comp = _component_model.predict(img, **predict_kwargs)[0]

    out: List[Dict[str, Any]] = []
    boxes = getattr(comp, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return {"detections": [], "width": W, "height": H}

    xyxy = boxes.xyxy.cpu().numpy()
    cls = boxes.cls.cpu().numpy().astype(int)
    conf = boxes.conf.cpu().numpy()

    for i in range(len(cls)):
        cls_id = int(cls[i])
        label = _label_from_names(_component_model.names, cls_id)
        score = float(conf[i])

        x1, y1, x2, y2 = [int(v) for v in xyxy[i]]
        x1 = _clamp(x1, 0, W - 1)
        x2 = _clamp(x2, 0, W - 1)
        y1 = _clamp(y1, 0, H - 1)
        y2 = _clamp(y2, 0, H - 1)

        det: Dict[str, Any] = {
            "label": label,
            "class_id": cls_id,
            "confidence": score,
            "box": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
        }

        # 2) if resistor -> run color model on crop
        if str(label).strip().lower() == RESISTOR_CLASS_NAME and x2 > x1 and y2 > y1:
            crop = img[y1:y2, x1:x2]
            if crop is not None and crop.size > 0:
                color_kwargs = dict(conf=COLOR_CONF, imgsz=COLOR_IMGSZ, verbose=False)
                if AURA_YOLO_DEVICE:
                    color_kwargs["device"] = AURA_YOLO_DEVICE

                val = _color_model.predict(crop, **color_kwargs)[0]
                vboxes = getattr(val, "boxes", None)
                if vboxes is not None and len(vboxes) > 0:
                    v_cls = vboxes.cls.cpu().numpy().astype(int)
                    v_conf = vboxes.conf.cpu().numpy()
                    best = int(np.argmax(v_conf))
                    v_id = int(v_cls[best])
                    v_label = _label_from_names(_color_model.names, v_id)
                    det["resistor_value"] = {
                        "label": v_label,
                        "class_id": v_id,
                        "confidence": float(v_conf[best]),
                    }

        out.append(det)

    return {"detections": out, "width": W, "height": H}