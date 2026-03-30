import json
import os
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional

from config import (
    DB_SYNC_STATE_FILE,
    DEFAULT_MODEL,
    EMBEDDING_MODEL,
    LOCAL_DB_NAME,
    SELECTED_DB_FILE,
    TMP_SOURCE_DIR,
    VECTOR_DBS_DIR,
)
from api_client import ApiClient


class DBManager:
    """
    Handles local Jetson vector DB cache.

    Layout:
      storage/vector_dbs/<db_name>/
          db.json
          meta.json
          embeddings.npy
          faiss.index

      storage/state/selected_db.json
      storage/state/db_sync_state.json

      storage/tmp/source_downloads/<db_name>/
          *.pdf / *.txt / *.md
    """

    def __init__(self, api: Optional[ApiClient] = None):
        self.api = api or ApiClient()
        self.vector_root = Path(VECTOR_DBS_DIR)
        self.tmp_root = Path(TMP_SOURCE_DIR)
        self.selected_file = Path(SELECTED_DB_FILE)
        self.sync_state_file = Path(DB_SYNC_STATE_FILE)

        self.vector_root.mkdir(parents=True, exist_ok=True)
        self.tmp_root.mkdir(parents=True, exist_ok=True)

    def db_dir(self, db_name: str) -> Path:
        return self.vector_root / db_name

    def tmp_source_dir(self, db_name: str) -> Path:
        return self.tmp_root / db_name

    def has_local_db(self, db_name: str) -> bool:
        db_dir = self.db_dir(db_name)
        required_any = [
            db_dir / "meta.json",
            db_dir / "chunks.jsonl",
        ]
        return any(p.exists() for p in required_any)

    def list_local_dbs(self) -> List[str]:
        out: List[str] = []
        if not self.vector_root.exists():
            return out
        for p in sorted(self.vector_root.iterdir()):
            if p.is_dir():
                out.append(p.name)
        return out

    def get_active_db(self) -> str:
        if self.selected_file.exists():
            try:
                data = json.loads(self.selected_file.read_text(encoding="utf-8"))
                db_name = str(data.get("selected_db") or "").strip()
                if db_name:
                    return db_name
            except Exception:
                pass
        return LOCAL_DB_NAME

    def set_active_db(self, db_name: str):
        payload = {
            "selected_db": db_name,
            "last_updated": int(time.time()),
        }
        self.selected_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def write_sync_state(self, db_name: str, status: str, detail: str = ""):
        payload = {
            "db_name": db_name,
            "status": status,
            "detail": detail,
            "ts": int(time.time()),
        }
        self.sync_state_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def read_sync_state(self) -> Dict:
        if not self.sync_state_file.exists():
            return {"status": "idle", "ts": int(time.time())}
        try:
            return json.loads(self.sync_state_file.read_text(encoding="utf-8"))
        except Exception:
            return {"status": "idle", "ts": int(time.time())}

    def ensure_db_json(self, db_name: str):
        db_dir = self.db_dir(db_name)
        db_dir.mkdir(parents=True, exist_ok=True)

        db_json = db_dir / "db.json"
        if not db_json.exists():
            payload = {
                "name": db_name,
                "llm_model": DEFAULT_MODEL,
                "embed_model": EMBEDDING_MODEL,
                "engine": "lightrag",
                "built_on": "jetson",
                "updated_ts": int(time.time()),
            }
            db_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def clear_temp_source_files(self, db_name: str):
        tmp_dir = self.tmp_source_dir(db_name)
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def prepare_temp_source_dir(self, db_name: str) -> Path:
        tmp_dir = self.tmp_source_dir(db_name)
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        return tmp_dir

    def download_source_files(self, db_name: str, rel_paths: List[str]) -> List[str]:
        self.write_sync_state(db_name, "downloading_source_docs")
        tmp_dir = self.prepare_temp_source_dir(db_name)

        downloaded: List[str] = []
        for rel_path in rel_paths:
            rel_path = str(rel_path).replace("\\", "/").lstrip("/")
            dest = tmp_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            self.api.download_document(rel_path, str(dest))
            downloaded.append(str(dest))

        return downloaded

    def get_temp_source_files(self, db_name: str) -> List[Path]:
        root = self.tmp_source_dir(db_name)
        if not root.exists():
            return []

        out: List[Path] = []
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in {".pdf", ".txt", ".md"}:
                out.append(p)
        return sorted(out)

    def has_temp_source_files(self, db_name: str) -> bool:
        return len(self.get_temp_source_files(db_name)) > 0

    def get_vector_file_paths(self, db_name: str) -> Dict[str, Path]:
        db_dir = self.db_dir(db_name)
        return {
            "db_json": db_dir / "db.json",
            "meta_json": db_dir / "meta.json",
            "embeddings_npy": db_dir / "embeddings.npy",
            "faiss_index": db_dir / "faiss.index",
            "chunks_jsonl": db_dir / "chunks.jsonl",
            "stats_json": db_dir / "stats.json",
        }

    def upload_local_vector_db(self, db_name: str):
        self.write_sync_state(db_name, "uploading_vector_bundle")
        self.ensure_db_json(db_name)
        return self.api.upload_vector_db(db_name, str(self.db_dir(db_name)))

    def mark_built(self, db_name: str, chunk_count: Optional[int] = None):
        self.ensure_db_json(db_name)
        db_json = self.db_dir(db_name) / "db.json"
        stats_json = self.db_dir(db_name) / "stats.json"

        try:
            data = json.loads(db_json.read_text(encoding="utf-8"))
        except Exception:
            data = {"name": db_name}

        data["updated_ts"] = int(time.time())
        data["built_on"] = "jetson"
        data["engine"] = "lightrag"

        db_json.write_text(json.dumps(data, indent=2), encoding="utf-8")

        stats_payload = {
            "chunk_count": int(chunk_count or 0),
            "vdb_path": str(self.db_dir(db_name)),
            "engine": "lightrag",
            "updated_ts": int(time.time()),
        }
        stats_json.write_text(json.dumps(stats_payload, indent=2), encoding="utf-8")

        self.write_sync_state(db_name, "ready")

    def activate_if_local(self, db_name: str) -> bool:
        if self.has_local_db(db_name):
            self.set_active_db(db_name)
            self.write_sync_state(db_name, "ready", "local cache hit")
            return True
        return False