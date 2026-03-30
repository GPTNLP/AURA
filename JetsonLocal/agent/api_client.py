import os
from typing import Any, Dict, List, Optional

import requests

from config import API_BASE_URL, DEVICE_SHARED_SECRET


class ApiClient:
    def __init__(self):
        self.base_url = API_BASE_URL.rstrip("/")
        self.timeout = 20

    def _url(self, path: str) -> str:
        if not self.base_url:
            raise RuntimeError("AZURE_BACKEND_URL is not set")
        return f"{self.base_url}{path}"

    def _json_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-Device-Secret": DEVICE_SHARED_SECRET,
        }

    def _device_headers(self) -> Dict[str, str]:
        return {
            "X-Device-Secret": DEVICE_SHARED_SECRET,
        }

    def health(self) -> Dict[str, Any]:
        r = requests.get(self._url("/health"), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def register(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = requests.post(
            self._url("/device/register"),
            json=payload,
            headers=self._json_headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def heartbeat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = requests.post(
            self._url("/device/heartbeat"),
            json=payload,
            headers=self._json_headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = requests.post(
            self._url("/device/status"),
            json=payload,
            headers=self._json_headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def log(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = requests.post(
            self._url("/device/logs"),
            json=payload,
            headers=self._json_headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def get_config(self, device_id: str) -> Dict[str, Any]:
        r = requests.get(
            self._url("/device/config"),
            params={"device_id": device_id},
            headers=self._device_headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def get_next_command(self, device_id: str) -> Dict[str, Any]:
        r = requests.get(
            self._url("/device/command/next"),
            params={"device_id": device_id},
            headers=self._device_headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def ack_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = requests.post(
            self._url("/device/command/ack"),
            json=payload,
            headers=self._json_headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    # -----------------------------
    # Documents / database sync
    # -----------------------------
    def download_document(self, path: str, dest_path: str):
        """
        Pull a source PDF/TXT/MD file from Azure.
        IMPORTANT:
        backend route must allow X-Device-Secret auth for Jetson pulls,
        otherwise this will 401/403.
        """
        r = requests.get(
            self._url("/api/documents/download"),
            params={"path": path},
            headers=self._device_headers(),
            stream=True,
            timeout=self.timeout,
        )
        r.raise_for_status()

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

    def download_vector_file(self, db_name: str, filename: str, dest_path: str):
        r = requests.get(
            self._url(f"/api/databases/{db_name}/sync_down/{filename}"),
            headers=self._device_headers(),
            stream=True,
            timeout=self.timeout,
        )
        r.raise_for_status()

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

    def upload_vector_db(self, db_name: str, working_dir: str):
        """
        Upload local Jetson vectorized DB files back to Azure.
        """
        url = self._url(f"/api/databases/{db_name}/sync_up")
        files = []
        allowed = ["faiss.index", "embeddings.npy", "meta.json", "db.json"]

        try:
            for fn in allowed:
                fp = os.path.join(working_dir, fn)
                if os.path.exists(fp):
                    files.append(("files", (fn, open(fp, "rb"))))

            if not files:
                return {"ok": False, "saved": [], "detail": "No vector files found to upload"}

            r = requests.post(
                url,
                files=files,
                headers={"X-Device-Secret": DEVICE_SHARED_SECRET},
                timeout=120,
            )
            r.raise_for_status()
            return r.json()
        finally:
            for _, (_, f) in files:
                try:
                    f.close()
                except Exception:
                    pass

    def get_database_config(self, db_name: str) -> Dict[str, Any]:
        """
        Existing Azure route requires normal auth right now.
        If you want Jetson to read this directly using only device secret,
        backend will need a small auth change later.
        """
        r = requests.get(
            self._url(f"/api/databases/{db_name}/config"),
            headers=self._device_headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def get_database_stats(self, db_name: str) -> Dict[str, Any]:
        r = requests.get(
            self._url(f"/api/databases/{db_name}/stats"),
            headers=self._device_headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()
    
    def get_source_manifest(self, db_name: str) -> Dict[str, Any]:
        r = requests.get(
            self._url(f"/api/databases/{db_name}/source_manifest"),
            headers=self._device_headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()