import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from api_client import ApiClient
from config import (
    AGENT_LOG_FILE,
    CAMERA_READY_DEFAULT,
    CONFIG_REFRESH_SECONDS,
    DEVICE_ID,
    DEVICE_NAME,
    DEVICE_SOFTWARE_VERSION,
    DEVICE_TYPE,
    HEARTBEAT_SECONDS,
    INPUT_MODE,
    OFFLINE_RETRY_SECONDS,
    OLLAMA_READY_DEFAULT,
    PENDING_LOGS_FILE,
    PENDING_STATUS_FILE,
    RUNTIME_FILE,
    SERIAL_PORT,
    STATUS_SECONDS,
    VECTOR_DB_READY_DEFAULT,
)
from db_manager import DBManager

try:
    import serial
except Exception:
    serial = None


def _now_ts() -> int:
    return int(time.time())


def _safe_read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _safe_write_json(path: Path, data: Any):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        pass


def _append_jsonl(path: Path, row: Dict[str, Any]):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


FAST_MOVE_MAP = {
    "forward": "F",
    "backward": "B",
    "left": "L",
    "right": "R",
    "stop": "S",
    "f": "F",
    "b": "B",
    "l": "L",
    "r": "R",
    "s": "S",
}


class AuraJetsonAgent:
    def __init__(self):
        self.api = ApiClient()
        self.db = DBManager(self.api)

        self.serial_conn = None
        self.serial_ready = False
        self.last_serial_error = ""

        self.command_poll_seconds = float(os.getenv("DEVICE_COMMAND_POLL_SECONDS", "0.08"))
        self.serial_baud = int(os.getenv("SERIAL_BAUD", "115200"))

        self.last_heartbeat_ts = 0.0
        self.last_status_ts = 0.0
        self.last_config_ts = 0.0
        self.last_command_ts = 0.0

        self.last_command_id: Optional[str] = None
        self.registered = False

        self.runtime = _safe_read_json(Path(RUNTIME_FILE), {})
        self.runtime.setdefault("started_at", _now_ts())
        self.runtime.setdefault("last_selected_db", self.db.get_active_db())
        self.runtime.setdefault("last_command", None)
        self.runtime.setdefault("last_command_at", None)
        self.runtime.setdefault("serial_port", SERIAL_PORT)
        self._save_runtime()

    def _save_runtime(self):
        _safe_write_json(Path(RUNTIME_FILE), self.runtime)

    def log_local(self, level: str, event: str, message: str, **extra):
        row = {
            "ts": _now_ts(),
            "level": level,
            "event": event,
            "message": message,
            **extra,
        }
        _append_jsonl(Path(AGENT_LOG_FILE), row)
        print(f"[{level.upper()}] {event}: {message}")

    def queue_status_fallback(self, payload: Dict[str, Any]):
        _append_jsonl(Path(PENDING_STATUS_FILE), payload)

    def queue_log_fallback(self, payload: Dict[str, Any]):
        _append_jsonl(Path(PENDING_LOGS_FILE), payload)

    def connect_serial(self):
        if serial is None:
            self.serial_ready = False
            self.last_serial_error = "pyserial not installed"
            self.log_local("error", "serial", self.last_serial_error)
            return

        try:
            self.serial_conn = serial.Serial(
                SERIAL_PORT,
                self.serial_baud,
                timeout=0,
                write_timeout=0.25,
            )
            time.sleep(0.2)
            self.serial_ready = True
            self.last_serial_error = ""
            self.log_local("info", "serial", f"Connected to serial {SERIAL_PORT} @ {self.serial_baud}")
        except Exception as e:
            self.serial_conn = None
            self.serial_ready = False
            self.last_serial_error = str(e)
            self.log_local("error", "serial", f"Failed to open serial {SERIAL_PORT}: {e}")

    def read_serial_lines(self, max_lines: int = 20):
        if not self.serial_conn or not self.serial_ready:
            return

        try:
            count = 0
            while self.serial_conn.in_waiting and count < max_lines:
                raw = self.serial_conn.readline()
                if not raw:
                    break
                try:
                    line = raw.decode("utf-8", errors="ignore").strip()
                except Exception:
                    line = ""
                if line:
                    self.log_local("info", "esp32_rx", line)
                count += 1
        except Exception as e:
            self.serial_ready = False
            self.last_serial_error = str(e)
            self.log_local("error", "serial", f"Serial read error: {e}")

    def send_serial_line(self, line: str) -> bool:
        if not line:
            return False
        if not self.serial_conn or not self.serial_ready:
            return False

        try:
            payload = (line.strip() + "\n").encode("utf-8")
            self.serial_conn.write(payload)
            self.serial_conn.flush()
            self.runtime["last_command"] = line.strip()
            self.runtime["last_command_at"] = _now_ts()
            self._save_runtime()
            self.log_local("info", "esp32_tx", line.strip())
            return True
        except Exception as e:
            self.serial_ready = False
            self.last_serial_error = str(e)
            self.log_local("error", "serial", f"Serial write error: {e}")
            return False

    def ensure_db_ready(self, db_name: str):
        if not db_name:
            return

        if self.db.activate_if_local(db_name):
            self.runtime["last_selected_db"] = db_name
            self._save_runtime()
            self.log_local("info", "db", f'Using cached local DB "{db_name}"')
            return

        self.log_local("info", "db", f'No local DB cache for "{db_name}", trying Azure vector sync')
        self.db.write_sync_state(db_name, "downloading_vector_bundle")

        db_dir = self.db.db_dir(db_name)
        db_dir.mkdir(parents=True, exist_ok=True)

        pulled_any = False
        for fn in ["db.json", "meta.json", "embeddings.npy", "faiss.index", "chunks.jsonl", "stats.json"]:
            dest = db_dir / fn
            try:
                self.api.download_vector_file(db_name, fn, str(dest))
                pulled_any = True
            except Exception:
                pass

        if pulled_any and self.db.activate_if_local(db_name):
            self.runtime["last_selected_db"] = db_name
            self._save_runtime()
            self.log_local("info", "db", f'Pulled vector cache from Azure for "{db_name}"')
            return

        try:
            manifest = self.api.get_source_manifest(db_name)
            files = list(manifest.get("files") or [])
            if files:
                self.db.download_source_files(db_name, files)
                self.db.write_sync_state(
                    db_name,
                    "source_docs_ready",
                    "Source files downloaded. Waiting for local vector build step.",
                )
                self.log_local(
                    "info",
                    "db",
                    f'Downloaded {len(files)} source files for "{db_name}" into temp storage',
                )
            else:
                self.db.write_sync_state(db_name, "failed", "No vector files and no source files found")
                self.log_local("error", "db", f'No vector files or source files found for "{db_name}"')
        except Exception as e:
            self.db.write_sync_state(db_name, "failed", str(e))
            self.log_local("error", "db", f'Failed to prepare DB "{db_name}": {e}')

    def refresh_selected_db(self):
        try:
            data = self.api.get_selected_db(DEVICE_ID)
            if not isinstance(data, dict):
                return

            selected_db = str(data.get("selected_db") or "").strip()
            if not selected_db:
                return

            current_db = self.db.get_active_db()
            if selected_db != current_db:
                self.log_local("info", "db_selection", f'Azure selected DB changed: "{current_db}" -> "{selected_db}"')
                self.ensure_db_ready(selected_db)

            self.last_config_ts = time.time()
        except Exception as e:
            self.log_local("error", "db_selection", f"Selected DB refresh failed: {e}")

    def make_register_payload(self) -> Dict[str, Any]:
        return {
            "device_id": DEVICE_ID,
            "name": DEVICE_NAME,
            "device_type": DEVICE_TYPE,
            "software_version": DEVICE_SOFTWARE_VERSION,
            "input_mode": INPUT_MODE,
            "serial_port": SERIAL_PORT,
        }

    def make_heartbeat_payload(self) -> Dict[str, Any]:
        return {
            "device_id": DEVICE_ID,
            "ts": _now_ts(),
            "software_version": DEVICE_SOFTWARE_VERSION,
            "selected_db": self.db.get_active_db(),
        }

    def make_status_payload(self) -> Dict[str, Any]:
        sync_state = self.db.read_sync_state()
        return {
            "device_id": DEVICE_ID,
            "ts": _now_ts(),
            "status": "online",
            "input_mode": INPUT_MODE,
            "serial_ready": bool(self.serial_ready),
            "serial_port": SERIAL_PORT,
            "serial_error": self.last_serial_error,
            "camera_ready": bool(CAMERA_READY_DEFAULT),
            "vector_db_ready": bool(VECTOR_DB_READY_DEFAULT),
            "ollama_ready": bool(OLLAMA_READY_DEFAULT),
            "selected_db": self.db.get_active_db(),
            "local_dbs": self.db.list_local_dbs(),
            "db_sync_state": sync_state,
            "last_command": self.runtime.get("last_command"),
            "last_command_at": self.runtime.get("last_command_at"),
        }

    def do_register(self):
        try:
            self.api.register(self.make_register_payload())
            self.registered = True
            self.log_local("info", "register", "Device registered")
        except Exception as e:
            self.registered = False
            self.log_local("error", "register", f"Register failed: {e}")

    def do_heartbeat(self):
        payload = self.make_heartbeat_payload()
        try:
            self.api.heartbeat(payload)
            self.last_heartbeat_ts = time.time()
        except Exception as e:
            self.log_local("error", "heartbeat", f"Heartbeat failed: {e}")

    def do_status(self):
        payload = self.make_status_payload()
        try:
            self.api.status(payload)
            self.last_status_ts = time.time()
        except Exception as e:
            self.queue_status_fallback(payload)
            self.log_local("error", "status", f"Status failed: {e}")

    def normalize_move_text(self, raw: str) -> Optional[str]:
        if not raw:
            return None

        s = raw.strip()
        low = s.lower()

        if low in ("f", "b", "l", "r", "s"):
            return low.upper()

        if low.startswith("move:"):
            move = low.split(":", 1)[1].strip()
            return FAST_MOVE_MAP.get(move)

        if low in FAST_MOVE_MAP:
            return FAST_MOVE_MAP[low]

        return None

    def send_move_command(self, move: str) -> bool:
        key = self.normalize_move_text(move)
        if not key:
            return False
        return self.send_serial_line(key)

    def try_handle_command_payload(self, cmd: Dict[str, Any]) -> bool:
        command_id = cmd.get("command_id") or cmd.get("id") or cmd.get("uuid")
        command_type = str(cmd.get("type") or cmd.get("command_type") or "").strip().lower()
        value = cmd.get("value")
        text = cmd.get("command") or cmd.get("cmd") or cmd.get("message") or cmd.get("text")

        handled = False

        if command_type in ("move", "movement", "control"):
            if isinstance(value, str):
                handled = self.send_move_command(value)
            elif isinstance(text, str):
                handled = self.send_move_command(text)

        elif isinstance(text, str):
            maybe_move = self.normalize_move_text(text)
            if maybe_move:
                handled = self.send_move_command(maybe_move)
            else:
                handled = self.send_serial_line(text)

        if not handled and command_type in ("select_db", "database"):
            db_name = str(value or text or "").strip()
            if db_name:
                self.ensure_db_ready(db_name)
                handled = True

        if command_id:
            try:
                self.api.ack_command(
                    {
                        "device_id": DEVICE_ID,
                        "command_id": command_id,
                        "ok": bool(handled),
                        "ts": _now_ts(),
                    }
                )
            except Exception as e:
                self.log_local("error", "command_ack", f"Ack failed: {e}")

        if handled:
            self.last_command_id = str(command_id or "")
            self.last_command_ts = time.time()

        return handled

    def poll_command_once(self):
        try:
            data = self.api.get_next_command(DEVICE_ID)
            if not isinstance(data, dict):
                return

            if not data:
                return
            if data.get("ok") is True and not any(k in data for k in ("command", "cmd", "type", "id", "command_id", "message", "text", "value")):
                return
            if data.get("command") is None and data.get("cmd") is None and data.get("text") is None and data.get("value") is None and not data.get("type"):
                return

            handled = self.try_handle_command_payload(data)
            if handled:
                self.log_local("info", "command", f"Handled command: {data}")
            else:
                self.log_local("warning", "command", f"Unhandled command payload: {data}")
        except Exception as e:
            self.log_local("error", "command_poll", f"Command poll failed: {e}")

    def boot(self):
        self.connect_serial()
        self.do_register()

        boot_db = self.db.get_active_db()
        if boot_db:
            self.ensure_db_ready(boot_db)

        self.do_status()
        self.refresh_selected_db()
        self.do_heartbeat()

    def run_forever(self):
        self.boot()

        while True:
            now = time.time()

            if not self.serial_ready and serial is not None:
                self.connect_serial()

            self.read_serial_lines()

            if (now - self.last_heartbeat_ts) >= HEARTBEAT_SECONDS:
                self.do_heartbeat()

            if (now - self.last_status_ts) >= STATUS_SECONDS:
                self.do_status()

            if (now - self.last_config_ts) >= CONFIG_REFRESH_SECONDS:
                self.refresh_selected_db()

            self.poll_command_once()
            time.sleep(self.command_poll_seconds)


def main():
    agent = AuraJetsonAgent()

    while True:
        try:
            agent.run_forever()
        except KeyboardInterrupt:
            raise
        except Exception as e:
            agent.log_local("error", "main", f"Agent crashed: {e}")
            time.sleep(OFFLINE_RETRY_SECONDS)


if __name__ == "__main__":
    main()