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

# ------------------------------------------------------------------
# PATH SETUP
# ------------------------------------------------------------------
AGENT_DIR = Path(__file__).resolve().parent
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

# ------------------------------------------------------------------
# IMPORTS
# ------------------------------------------------------------------
import core.config as cfg
from cloud.api_client import ApiClient
from hardware.serial_link import serial_link
from hardware.camera import camera_service

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
DEVICE_ID = getattr(cfg, "DEVICE_ID", "jetson-001")
DEVICE_NAME = getattr(cfg, "DEVICE_NAME", "AURA Jetson")
DEVICE_TYPE = getattr(cfg, "DEVICE_TYPE", "jetson")
DEVICE_SOFTWARE_VERSION = getattr(cfg, "DEVICE_SOFTWARE_VERSION", "0.1.0")

HEARTBEAT_SECONDS = float(getattr(cfg, "DEVICE_HEARTBEAT_SECONDS", 10))
STATUS_SECONDS = float(getattr(cfg, "DEVICE_STATUS_SECONDS", 2))
POLL_SECONDS = float(getattr(cfg, "DEVICE_POLL_SECONDS", 0.5))

api = ApiClient()

# ------------------------------------------------------------------
# GLOBALS
# ------------------------------------------------------------------
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

last_register_message = None
last_status_message = None
last_command_message = None


# ------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------
def quiet_print(prefix: str, message: str) -> None:
    print(f"{prefix} {message}")


def now_ts() -> int:
    return int(time.time())


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_cpu_percent() -> float:
    try:
        return round(psutil.cpu_percent(interval=None), 1)
    except Exception:
        return 0.0


def get_ram_percent() -> float:
    try:
        return round(psutil.virtual_memory().percent, 1)
    except Exception:
        return 0.0


def get_disk_percent() -> float:
    try:
        return round(psutil.disk_usage("/").percent, 1)
    except Exception:
        return 0.0


def get_uptime_seconds() -> int:
    try:
        return int(time.time() - psutil.boot_time())
    except Exception:
        return int(time.time() - runtime_state["started_at"])


def get_cpu_temp_c() -> Optional[float]:
    paths = [
        "/sys/devices/virtual/thermal/thermal_zone0/temp",
        "/sys/class/thermal/thermal_zone0/temp",
    ]

    for path in paths:
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


def get_wifi_dbm() -> Optional[int]:
    try:
        text = Path("/proc/net/wireless").read_text()
        lines = [line.strip() for line in text.splitlines() if ":" in line]
        if not lines:
            return None

        parts = lines[0].replace(":", " ").split()
        if len(parts) >= 4:
            level = float(parts[3].rstrip("."))
            if level > 0:
                level = level - 256
            return int(level)
    except Exception:
        pass

    return None


def get_battery_percent() -> Optional[float]:
    candidates = [
        "/sys/class/power_supply/BAT0/capacity",
        "/sys/class/power_supply/battery/capacity",
    ]

    for path in candidates:
        try:
            p = Path(path)
            if p.exists():
                return round(float(p.read_text().strip()), 1)
        except Exception:
            pass

    return None


def get_battery_voltage() -> Optional[float]:
    candidates = [
        "/sys/class/power_supply/BAT0/voltage_now",
        "/sys/class/power_supply/battery/voltage_now",
    ]

    for path in candidates:
        try:
            p = Path(path)
            if p.exists():
                value = float(p.read_text().strip())
                if value > 1000:
                    value /= 1_000_000.0
                return round(value, 2)
        except Exception:
            pass

    return None


def get_gpu_percent() -> Optional[float]:
    # Jetson-specific GPU util can vary by board/setup.
    # Return None if not available instead of fake data.
    candidates = [
        "/sys/devices/gpu.0/load",
        "/sys/class/devfreq/17000000.ga10b/load",
    ]

    for path in candidates:
        try:
            p = Path(path)
            if p.exists():
                raw = float(p.read_text().strip())
                if raw > 100:
                    raw = raw / 10.0
                return round(raw, 1)
        except Exception:
            pass

    return None


def collect_payload() -> dict:
    battery_percent = get_battery_percent()
    battery_voltage = get_battery_voltage()
    cpu_percent = get_cpu_percent()
    cpu_temp_c = get_cpu_temp_c()
    ram_percent = get_ram_percent()
    disk_percent = get_disk_percent()
    gpu_percent = get_gpu_percent()
    wifi_dbm = get_wifi_dbm()
    uptime_seconds = get_uptime_seconds()

    try:
        camera_status = camera_service.get_status()
    except Exception as e:
        camera_status = {
            "camera_ready": False,
            "last_error": str(e),
        }

    thermals_state = "ok"
    if cpu_temp_c is not None:
        if cpu_temp_c >= 80:
            thermals_state = "warn"
        elif cpu_temp_c >= 70:
            thermals_state = "warn"

    payload = {
        # --------------------------------------------------------------
        # Core identity / heartbeat
        # --------------------------------------------------------------
        "device_id": DEVICE_ID,
        "device_name": DEVICE_NAME,
        "device_type": DEVICE_TYPE,
        "software_version": DEVICE_SOFTWARE_VERSION,
        "hostname": socket.gethostname(),
        "local_ip": get_local_ip(),
        "online": True,
        "last_seen_at": now_ts(),

        # --------------------------------------------------------------
        # TOP-LEVEL COMPAT FIELDS
        # Put everything here too so frontend/backend can read directly
        # --------------------------------------------------------------
        "battery": battery_percent,
        "battery_percent": battery_percent,
        "battery_voltage": battery_voltage,
        "voltage": battery_voltage,

        "cpu": cpu_percent,
        "cpu_usage": cpu_percent,
        "cpu_percent": cpu_percent,
        "cpu_temp": cpu_temp_c,
        "cpu_temp_c": cpu_temp_c,

        "ram": ram_percent,
        "ram_usage": ram_percent,
        "ram_percent": ram_percent,
        "memory": ram_percent,
        "memory_percent": ram_percent,

        "gpu": gpu_percent,
        "gpu_usage": gpu_percent,
        "gpu_percent": gpu_percent,

        "disk": disk_percent,
        "disk_percent": disk_percent,

        "wifi": wifi_dbm,
        "wifi_dbm": wifi_dbm,

        "uptime": uptime_seconds,
        "uptime_seconds": uptime_seconds,

        # --------------------------------------------------------------
        # Nested metrics
        # --------------------------------------------------------------
        "metrics": {
            "battery": battery_percent,
            "battery_percent": battery_percent,
            "battery_voltage": battery_voltage,
            "voltage": battery_voltage,
            "cpu": cpu_percent,
            "cpu_usage": cpu_percent,
            "cpu_percent": cpu_percent,
            "cpu_temp": cpu_temp_c,
            "cpu_temp_c": cpu_temp_c,
            "ram": ram_percent,
            "ram_usage": ram_percent,
            "ram_percent": ram_percent,
            "memory": ram_percent,
            "memory_percent": ram_percent,
            "gpu": gpu_percent,
            "gpu_usage": gpu_percent,
            "gpu_percent": gpu_percent,
            "disk_percent": disk_percent,
            "wifi_dbm": wifi_dbm,
            "uptime": uptime_seconds,
            "uptime_seconds": uptime_seconds,
        },

        # --------------------------------------------------------------
        # UI health blocks
        # --------------------------------------------------------------
        "system_health": {
            "motors": "ok",
            "sensors": "ok",
            "thermals": thermals_state,
        },
        "health": {
            "motors": "ok",
            "sensors": "ok",
            "thermals": thermals_state,
        },
        "motors_status": "ok",
        "sensors_status": "ok",
        "thermals_status": thermals_state,

        # --------------------------------------------------------------
        # Camera
        # --------------------------------------------------------------
        "camera": camera_status,
        "camera_ready": camera_status.get("camera_ready", False),
    }

    return payload


# ------------------------------------------------------------------
# API ADAPTERS
# ------------------------------------------------------------------
def call_api_method(
    method_names: list[str],
    arg_builders: list[Callable[[Callable[..., Any]], tuple[list[Any], dict[str, Any]]]],
):
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


def register_with_cloud():
    payload = {
        "device_id": DEVICE_ID,
        "device_name": DEVICE_NAME,
        "device_type": DEVICE_TYPE,
        "software_version": DEVICE_SOFTWARE_VERSION,
        "hostname": socket.gethostname(),
        "local_ip": get_local_ip(),
    }

    return call_api_method(
        ["register_device", "register", "device_register"],
        [
            lambda _m: ([payload], {}),
            lambda _m: ([DEVICE_ID, payload], {}),
            lambda _m: ([], payload),
        ],
    )


def send_status_to_cloud(payload: dict):
    return call_api_method(
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


def get_next_command_from_cloud():
    return call_api_method(
        ["get_next_command", "poll_command", "next_command"],
        [
            lambda _m: ([DEVICE_ID], {}),
            lambda _m: ([], {"device_id": DEVICE_ID}),
            lambda _m: ([], {}),
        ],
    )


def ack_command_to_cloud(payload: dict):
    return call_api_method(
        ["ack_command", "acknowledge_command", "command_ack"],
        [
            lambda _m: ([payload], {}),
            lambda _m: ([DEVICE_ID, payload], {}),
            lambda _m: ([], payload),
        ],
    )


# ------------------------------------------------------------------
# LOOPS
# ------------------------------------------------------------------
async def registration_loop():
    global last_register_message

    while True:
        try:
            result = await asyncio.to_thread(register_with_cloud)
            runtime_state["registered"] = True
            runtime_state["last_register_ok"] = now_ts()
            runtime_state["last_register_error"] = None

            msg = f"ok device_id={DEVICE_ID}"
            if msg != last_register_message:
                quiet_print("[REGISTER]", msg)
                last_register_message = msg

        except Exception as e:
            runtime_state["registered"] = False
            runtime_state["last_register_error"] = str(e)

            msg = str(e)
            if msg != last_register_message:
                quiet_print("[REGISTER]", f"failed: {msg}")
                last_register_message = msg

        await asyncio.sleep(max(HEARTBEAT_SECONDS, 10))


async def status_loop():
    global last_status_message

    await asyncio.sleep(1.0)

    while True:
        try:
            payload = collect_payload()
            await asyncio.to_thread(send_status_to_cloud, payload)

            runtime_state["last_status_ok"] = now_ts()
            runtime_state["last_status_error"] = None

            cpu = payload.get("cpu_percent")
            ram = payload.get("ram_percent")
            batt = payload.get("battery_percent")
            gpu = payload.get("gpu_percent")

            msg = f"ok cpu={cpu} ram={ram} batt={batt} gpu={gpu}"
            if msg != last_status_message:
                quiet_print("[STATUS]", msg)
                last_status_message = msg

        except Exception as e:
            runtime_state["last_status_error"] = str(e)

            msg = f"failed: {e}"
            if msg != last_status_message:
                quiet_print("[STATUS]", msg)
                last_status_message = msg

        await asyncio.sleep(max(STATUS_SECONDS, 1.0))


async def command_loop():
    global last_command_message

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

                if cmd in {"forward", "backward", "left", "right", "stop"}:
                    try:
                        serial_link.send_command(cmd, payload.get("value", ""))
                        ack_payload = {
                            "command_id": cmd_id,
                            "device_id": DEVICE_ID,
                            "status": "completed",
                        }
                        await asyncio.to_thread(ack_command_to_cloud, ack_payload)
                        runtime_state["last_command_ok"] = now_ts()
                        runtime_state["last_command_error"] = None

                        msg = f"ok {cmd}"
                        if msg != last_command_message:
                            quiet_print("[COMMAND]", msg)
                            last_command_message = msg

                    except Exception as e:
                        ack_payload = {
                            "command_id": cmd_id,
                            "device_id": DEVICE_ID,
                            "status": "failed",
                            "note": str(e),
                        }
                        await asyncio.to_thread(ack_command_to_cloud, ack_payload)
                        runtime_state["last_command_error"] = str(e)

                        msg = f"failed {cmd}: {e}"
                        if msg != last_command_message:
                            quiet_print("[COMMAND]", msg)
                            last_command_message = msg

        except Exception as e:
            runtime_state["last_command_error"] = str(e)
            msg = f"poll failed: {e}"
            if msg != last_command_message:
                quiet_print("[COMMAND]", msg)
                last_command_message = msg

        await asyncio.sleep(max(POLL_SECONDS, 0.25))


# ------------------------------------------------------------------
# FASTAPI
# ------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        serial_link.connect()
    except Exception as e:
        quiet_print("[SERIAL]", f"connect failed: {e}")

    asyncio.create_task(registration_loop())
    asyncio.create_task(status_loop())
    asyncio.create_task(command_loop())

    quiet_print("[STARTUP]", "filometrics agent running")
    yield
    quiet_print("[SHUTDOWN]", "done")


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
    return collect_payload()


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        access_log=False,
        log_level="warning",
    )