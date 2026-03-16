import os
import socket
import time
import shutil
from typing import Dict, Any

try:
    import psutil
except Exception:
    psutil = None


START_TIME = time.time()


def get_hostname() -> str:
    return socket.gethostname()


def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def get_uptime_seconds() -> int:
    return int(time.time() - START_TIME)


def get_temperature_c() -> float | None:
    thermal_path = "/sys/class/thermal/thermal_zone0/temp"
    try:
        raw = open(thermal_path, "r", encoding="utf-8").read().strip()
        return round(int(raw) / 1000.0, 1)
    except Exception:
        return None


def get_cpu_percent() -> float | None:
    if psutil:
        try:
            return round(psutil.cpu_percent(interval=0.2), 1)
        except Exception:
            return None
    return None


def get_ram_percent() -> float | None:
    if psutil:
        try:
            return round(psutil.virtual_memory().percent, 1)
        except Exception:
            return None
    return None


def get_disk_percent() -> float | None:
    try:
        total, used, free = shutil.disk_usage("/")
        if total <= 0:
            return None
        return round((used / total) * 100.0, 1)
    except Exception:
        return None


def collect_device_info() -> Dict[str, Any]:
    return {
        "hostname": get_hostname(),
        "local_ip": get_local_ip(),
        "uptime_seconds": get_uptime_seconds(),
        "cpu_percent": get_cpu_percent(),
        "ram_percent": get_ram_percent(),
        "disk_percent": get_disk_percent(),
        "temperature_c": get_temperature_c(),
    }