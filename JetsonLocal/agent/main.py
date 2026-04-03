import sys
import os
import time
import socket
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any, Callable, Optional

import psutil
import uvicorn
from fastapi import FastAPI

# -------------------------------------------------------------------
# PATH SETUP
# -------------------------------------------------------------------
AGENT_DIR = Path(__file__).resolve().parent
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

# -------------------------------------------------------------------
# IMPORTS
# -------------------------------------------------------------------
import core.config as cfg
from cloud.api_client import ApiClient
from hardware.serial_link import serial_link
from hardware.camera import camera_service
from ai.rag_manager import rag_manager

# -------------------------------------------------------------------
# CONFIG HELPERS
# -------------------------------------------------------------------
DEVICE_ID = getattr(cfg, "DEVICE_ID", "jetson-001")
DEVICE_NAME = getattr(cfg, "DEVICE_NAME", "AURA Jetson")
DEVICE_TYPE = getattr(cfg, "DEVICE_TYPE", "jetson")
DEVICE_SOFTWARE_VERSION = getattr(cfg, "DEVICE_SOFTWARE_VERSION", "0.1.0")

HEARTBEAT_SECONDS = float(getattr(cfg, "DEVICE_HEARTBEAT_SECONDS", 10))
STATUS_SECONDS = float(getattr(cfg, "DEVICE_STATUS_SECONDS", 2))
POLL_SECONDS = float(getattr(cfg, "DEVICE_POLL_SECONDS", 0.5))

api = ApiClient()

# -------------------------------------------------------------------
# GLOBAL STATE
# -------------------------------------------------------------------
runtime_state = {
    "started_at": time.time(),
    "registered": False,
    "last_register_ok": None,
    "last_register_error": None,
    "last_status_ok": None,
    "last_status_error": None,
    "last_command_ok": None,
    "last_command_error": None,
}

# -------------------------------------------------------------------
# SMALL UTILS
# -------------------------------------------------------------------
def _now() -> int:
    return int(time.time())


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _get_cpu_temp_c() -> Optional[float]:
    thermal_paths = [
        "/sys/devices/virtual/thermal/thermal_zone0/temp",
        "/sys/class/thermal/thermal_zone0/temp",
    ]

    for path in thermal_paths:
        try:
            if os.path.exists(path):
                raw = Path(path).read_text().strip()
                value = float(raw)
                if value > 1000:
                    value /= 1000.0
                return round(value, 1)
        except Exception:
            pass

    try:
        temps = psutil.sensors_temperatures(fahrenheit=False)
        for _, entries in temps.items():
            for entry in entries:
                if entry.current is not None:
                    return round(float(entry.current), 1)
    except Exception:
        pass

    return None


def _get_disk_percent() -> float:
    try:
        return round(psutil.disk_usage("/").percent, 1)
    except Exception:
        return 0.0


def _get_ram_percent() -> float:
    try:
        return round(psutil.virtual_memory().percent, 1)
    except Exception:
        return 0.0


def _get_cpu_percent() -> float:
    try:
        return round(psutil.cpu_percent(interval=None), 1)
    except Exception:
        return 0.0


def _get_uptime_seconds() -> int:
    try:
        return int(time.time() - psutil.boot_time())
    except Exception:
        return int(time.time() - runtime_state["started_at"])


def _find_wifi_signal_dbm() -> Optional[int]:
    candidates = [
        "/proc/net/wireless",
    ]

    for path in candidates:
        try:
            if not os.path.exists(path):
                continue

            text = Path(path).read_text()
            lines = [line.strip() for line in text.splitlines() if ":" in line]
            if not lines:
                continue

            # Typical format: wlan0: ... link level noise
            # level is often negative-ish encoded or absolute depending on driver
            parts = lines[0].replace(":", " ").split()
            if len(parts) >= 4:
                level = float(parts[3].rstrip("."))
                if level > 0:
                    level = level - 256
                return int(level)
        except Exception:
            pass

    return None


def _find_battery_percent() -> Optional[float]:
    battery_dirs = [
        "/sys/class/power_supply/BAT0",
        "/sys/class/power_supply/battery",
    ]

    for base in battery_dirs:
        try:
            cap = Path(base) / "capacity"
            if cap.exists():
                return round(float(cap.read_text().strip()), 1)
        except Exception:
            pass

    return None


def _find_battery_voltage() -> Optional[float]:
    battery_dirs = [
        "/sys/class/power_supply/BAT0",
        "/sys/class/power_supply/battery",
    ]

    for base in battery_dirs:
        try:
            vp = Path(base) / "voltage_now"
            if vp.exists():
                value = float(vp.read_text().strip())
                if value > 1000:
                    value /= 1_000_000.0
                return round(value, 2)
        except Exception:
            pass

    return None


def collect_filometrics() -> dict:
    camera_status = {}
    try:
        camera_status = camera_service.get_status()
    except Exception as e:
        camera_status = {"camera_ready": False, "last_error": str(e)}

    payload = {
        "device_id": DEVICE_ID,
        "device_name": DEVICE_NAME,
        "device_type": DEVICE_TYPE,
        "software_version": DEVICE_SOFTWARE_VERSION,
        "hostname": socket.gethostname(),
        "local_ip": _get_local_ip(),
        "online": True,
        "last_seen_at": _now(),
        "metrics": {
            "cpu_percent": _get_cpu_percent(),
            "cpu_temp_c": _get_cpu_temp_c(),
            "ram_percent": _get_ram_percent(),
            "disk_percent": _get_disk_percent(),
            "wifi_dbm": _find_wifi_signal_dbm(),
            "battery_percent": _find_battery_percent(),
            "battery_voltage": _find_battery_voltage(),
            "uptime_seconds": _get_uptime_seconds(),
        },
        "camera": camera_status,
    }

    return payload


# -------------------------------------------------------------------
# API CALL ADAPTERS
# These try several likely method names/signatures so this still works
# even if your teammate changed ApiClient during the repo reorg.
# -------------------------------------------------------------------
def _call_api_method(method_names: list[str], arg_builders: list[Callable[[Callable[..., Any]], tuple[list[Any], dict[str, Any]]]]):
    last_error = None

    for method_name in method_names:
        method = getattr(api, method_name, None)
        if method is None:
            continue

        for builder in arg_builders:
            try:
                args, kwargs = builder(method)
                return method(*args, **kwargs)
            except TypeError as e:
                last_error = e
                continue
            except Exception as e:
                last_error = e
                raise

    if last_error:
        raise last_error

    raise AttributeError(f"No matching ApiClient method found among: {method_names}")


def register_with_cloud() -> Any:
    payload = {
        "device_id": DEVICE_ID,
        "device_name": DEVICE_NAME,
        "device_type": DEVICE_TYPE,
        "software_version": DEVICE_SOFTWARE_VERSION,
        "hostname": socket.gethostname(),
        "local_ip": _get_local_ip(),
    }

    return _call_api_method(
        ["register_device", "register", "device_register"],
        [
            lambda _m: ([payload], {}),
            lambda _m: ([DEVICE_ID, payload], {}),
            lambda _m: ([], payload),
        ],
    )


def send_status_to_cloud(payload: dict) -> Any:
    return _call_api_method(
        [
            "send_status",
            "update_status",
            "post_status",
            "heartbeat",
            "send_device_status",
            "device_status",
            "status",
        ],
        [
            lambda _m: ([payload], {}),
            lambda _m: ([DEVICE_ID, payload], {}),
            lambda _m: ([], payload),
        ],
    )


def get_next_command_from_cloud() -> dict:
    return _call_api_method(
        ["get_next_command", "poll_command", "next_command"],
        [
            lambda _m: ([DEVICE_ID], {}),
            lambda _m: ([], {"device_id": DEVICE_ID}),
            lambda _m: ([], {}),
        ],
    )


def ack_command_to_cloud(payload: dict) -> Any:
    return _call_api_method(
        ["ack_command", "acknowledge_command", "command_ack"],
        [
            lambda _m: ([payload], {}),
            lambda _m: ([DEVICE_ID, payload], {}),
            lambda _m: ([], payload),
        ],
    )


# -------------------------------------------------------------------
# BACKGROUND TASKS
# -------------------------------------------------------------------
async def registration_loop():
    while True:
        try:
            result = await asyncio.to_thread(register_with_cloud)
            runtime_state["registered"] = True
            runtime_state["last_register_ok"] = _now()
            runtime_state["last_register_error"] = None
            print(f"[REGISTER] success: {result}")
            await asyncio.sleep(max(HEARTBEAT_SECONDS, 10))
        except Exception as e:
            runtime_state["registered"] = False
            runtime_state["last_register_error"] = str(e)
            print(f"[REGISTER] failed: {e}")
            await asyncio.sleep(5)


async def status_loop():
    await asyncio.sleep(1.0)

    while True:
        try:
            payload = collect_filometrics()
            result = await asyncio.to_thread(send_status_to_cloud, payload)
            runtime_state["last_status_ok"] = _now()
            runtime_state["last_status_error"] = None
            print(f"[STATUS] sent: {result}")
        except Exception as e:
            runtime_state["last_status_error"] = str(e)
            print(f"[STATUS] failed: {e}")

        await asyncio.sleep(max(STATUS_SECONDS, 1))


async def command_loop():
    while True:
        try:
            result = await asyncio.to_thread(get_next_command_from_cloud)
            command = {}
            if isinstance(result, dict):
                command = result.get("command") or {}

            if command:
                cmd_id = command.get("id")
                cmd = (command.get("command") or "").strip().lower()
                payload = command.get("payload") or {}

                print(f"[COMMAND] received: {cmd} payload={payload}")

                if cmd in {"forward", "backward", "left", "right", "stop"}:
                    try:
                        serial_link.send_command(cmd, payload.get("value", ""))
                        ack_payload = {
                            "command_id": cmd_id,
                            "device_id": DEVICE_ID,
                            "status": "completed",
                        }
                        await asyncio.to_thread(ack_command_to_cloud, ack_payload)
                        runtime_state["last_command_ok"] = _now()
                        runtime_state["last_command_error"] = None
                    except Exception as e:
                        ack_payload = {
                            "command_id": cmd_id,
                            "device_id": DEVICE_ID,
                            "status": "failed",
                            "note": str(e),
                        }
                        await asyncio.to_thread(ack_command_to_cloud, ack_payload)
                        runtime_state["last_command_error"] = str(e)

        except Exception as e:
            runtime_state["last_command_error"] = str(e)
            print(f"[COMMAND] poll failed: {e}")

        await asyncio.sleep(max(POLL_SECONDS, 0.1))


# -------------------------------------------------------------------
# FASTAPI APP
# -------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[STARTUP] connecting serial")
    try:
        serial_link.connect()
    except Exception as e:
        print(f"[SERIAL] connect failed: {e}")

    print("[STARTUP] initializing rag")
    try:
        rag_manager.initialize()
    except Exception as e:
        print(f"[RAG] init failed: {e}")

    asyncio.create_task(registration_loop())
    asyncio.create_task(status_loop())
    asyncio.create_task(command_loop())

    print("[STARTUP] background loops started")
    yield
    print("[SHUTDOWN] complete")


app = FastAPI(title="AURA Jetson Agent", lifespan=lifespan)


@app.get("/health")
async def health():
    return {
        "ok": True,
        "device_id": DEVICE_ID,
        "registered": runtime_state["registered"],
        "last_register_ok": runtime_state["last_register_ok"],
        "last_register_error": runtime_state["last_register_error"],
        "last_status_ok": runtime_state["last_status_ok"],
        "last_status_error": runtime_state["last_status_error"],
        "last_command_ok": runtime_state["last_command_ok"],
        "last_command_error": runtime_state["last_command_error"],
    }


@app.get("/status")
async def status():
    return collect_filometrics()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)