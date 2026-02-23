# backend/doc_owners.py
import json
from pathlib import Path
from typing import Optional, Dict

OWNERS_PATH = Path(__file__).resolve().parent / "storage" / "doc_owners.json"
OWNERS_PATH.parent.mkdir(parents=True, exist_ok=True)

def _load() -> Dict[str, str]:
    if not OWNERS_PATH.exists():
        return {}
    try:
        obj = json.loads(OWNERS_PATH.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in obj.items()}
    except Exception:
        return {}

def _save(m: Dict[str, str]) -> None:
    OWNERS_PATH.write_text(json.dumps(m, indent=2), encoding="utf-8")

def get_owner(path: str) -> Optional[str]:
    m = _load()
    return m.get(path)

def set_owner(path: str, email: str) -> None:
    m = _load()
    m[path] = (email or "").strip().lower()
    _save(m)

def delete_owner(path: str) -> None:
    m = _load()
    if path in m:
        del m[path]
        _save(m)

def move_owner(src: str, dst: str) -> None:
    m = _load()
    if src in m:
        m[dst] = m[src]
        del m[src]
        _save(m)