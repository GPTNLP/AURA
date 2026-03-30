import os
import time
import json
import asyncio
from pathlib import Path
from typing import Any, Dict, Optional, List

import psutil
import serial
import uvicorn
from pypdf import PdfReader

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agent.config import DEFAULT_MODEL, EMBEDDING_MODEL
from agent.db_manager import DBManager
from lightrag_local import LightRAG, OllamaClient, QueryParam

try:
    from jtop import jtop
except Exception:
    jtop = None


APP_HOST = os.getenv("AURA_LOCAL_APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("AURA_LOCAL_APP_PORT", "8000"))

AZURE_BACKEND_URL = os.getenv("AZURE_BACKEND_URL", "").rstrip("/")
SERIAL_PORT = os.getenv("SERIAL_PORT", "/dev/ttyACM0")
SERIAL_BAUD = int(os.getenv("SERIAL_BAUD", "115200"))

AURA_OLLAMA_URL = os.getenv("AURA_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
AURA_CHAT_MODE = os.getenv("AURA_CHAT_MODE", "hybrid").strip().lower()
AURA_TOP_K = int(os.getenv("AURA_TOP_K", "4"))

AUTO_BUILD_ON_STARTUP = os.getenv("AURA_AUTO_BUILD_ON_STARTUP", "1").strip() == "1"
UPLOAD_VECTOR_AFTER_BUILD = os.getenv("AURA_UPLOAD_VECTOR_AFTER_BUILD", "1").strip() == "1"

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="AURA Edge Local App")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

db_manager = DBManager()


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        try:
            self.active_connections.remove(websocket)
        except ValueError:
            pass

    async def broadcast(self, message: dict):
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)

        for d in dead:
            self.disconnect(d)


ui_manager = ConnectionManager()

rag_system: Optional[LightRAG] = None
ollama_client: Optional[OllamaClient] = None
esp_serial: Optional[serial.Serial] = None
gpu_reader = None
build_lock = asyncio.Lock()

app_state: Dict[str, Any] = {
    "status_text": "Booting...",
    "connection": "Offline",
    "db_name": db_manager.get_active_db(),
    "serial_ready": False,
    "ollama_ready": False,
    "rag_ready": False,
    "build_running": False,
    "last_error": "",
    "last_user_text": "",
    "last_ai_text": "",
    "started_at": int(time.time()),
}


def set_status(text: str):
    app_state["status_text"] = text


async def ui_system(msg: str):
    await ui_manager.broadcast({"type": "system", "text": msg})


def get_active_db_name() -> str:
    db_name = db_manager.get_active_db()
    if not db_name:
        db_name = "jetson_local_db"
    return db_name


def get_active_db_path() -> str:
    return str(db_manager.db_dir(get_active_db_name()))


def init_rag_for_active_db():
    global rag_system, ollama_client

    db_name = get_active_db_name()
    db_path = get_active_db_path()

    try:
        os.makedirs(db_path, exist_ok=True)

        rag_system = LightRAG(
            working_dir=db_path,
            llm_model_name=DEFAULT_MODEL,
            embed_model_name=EMBEDDING_MODEL,
            ollama_base_url=AURA_OLLAMA_URL,
        )

        ollama_client = OllamaClient(
            base_url=AURA_OLLAMA_URL,
            embed_model=EMBEDDING_MODEL,
            llm_model=DEFAULT_MODEL,
        )

        app_state["db_name"] = db_name
        app_state["rag_ready"] = True
        app_state["last_error"] = ""
    except Exception as e:
        rag_system = None
        ollama_client = None
        app_state["rag_ready"] = False
        app_state["last_error"] = f"RAG init failed: {e}"


async def reload_rag_for_selected_db():
    set_status("Switching database...")
    init_rag_for_active_db()
    await check_ollama_ready()
    set_status("Ready")


def map_move_command(text: str) -> Optional[str]:
    if not text:
        return None

    raw = text.strip().lower()

    direct = {
        "f": "F",
        "forward": "F",
        "b": "B",
        "backward": "B",
        "l": "L",
        "left": "L",
        "r": "R",
        "right": "R",
        "s": "S",
        "stop": "S",
    }

    if raw in direct:
        return direct[raw]

    if "forward" in raw:
        return "F"
    if "backward" in raw or "back" in raw:
        return "B"
    if "left" in raw:
        return "L"
    if "right" in raw:
        return "R"
    if "stop" in raw:
        return "S"

    return None


def init_hardware():
    global esp_serial

    try:
        esp_serial = serial.Serial(
            SERIAL_PORT,
            SERIAL_BAUD,
            timeout=0,
            write_timeout=0.25,
        )
        app_state["serial_ready"] = True
        app_state["last_error"] = ""
    except Exception as e:
        esp_serial = None
        app_state["serial_ready"] = False
        app_state["last_error"] = f"Serial init failed: {e}"


def init_gpu_reader():
    global gpu_reader

    if jtop is None:
        gpu_reader = None
        return

    try:
        gpu_reader = jtop()
        gpu_reader.start()
    except Exception:
        gpu_reader = None


async def check_ollama_ready():
    if ollama_client is None:
        app_state["ollama_ready"] = False
        return

    try:
        await ollama_client.embed("ready")
        app_state["ollama_ready"] = True
    except Exception:
        app_state["ollama_ready"] = False


def read_gpu_percent() -> Optional[float]:
    global gpu_reader

    if gpu_reader is None:
        return None

    try:
        stats = gpu_reader.stats
        if isinstance(stats, dict):
            gpu = stats.get("GPU")
            if isinstance(gpu, (int, float)):
                return float(gpu)
    except Exception:
        return None

    return None


def send_serial_command(cmd: str) -> bool:
    if not cmd or esp_serial is None:
        return False

    try:
        esp_serial.write((cmd.strip() + "\n").encode("utf-8"))
        esp_serial.flush()
        return True
    except Exception as e:
        app_state["serial_ready"] = False
        app_state["last_error"] = f"Serial write failed: {e}"
        return False


def read_serial_lines():
    if esp_serial is None:
        return []

    out = []
    try:
        while esp_serial.in_waiting:
            raw = esp_serial.readline()
            if not raw:
                break
            line = raw.decode("utf-8", errors="ignore").strip()
            if line:
                out.append(line)
    except Exception:
        pass
    return out


def read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def read_pdf_file(path: Path) -> str:
    try:
        reader = PdfReader(str(path))
        parts: List[str] = []
        for page in reader.pages:
            try:
                txt = page.extract_text() or ""
                if txt.strip():
                    parts.append(txt)
            except Exception:
                pass
        return "\n\n".join(parts)
    except Exception:
        return ""


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> List[str]:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []

    chunks: List[str] = []
    i = 0
    n = len(text)

    while i < n:
        j = min(n, i + chunk_size)
        chunk = text[i:j].strip()
        if chunk:
            chunks.append(chunk)
        if j >= n:
            break
        i = max(i + 1, j - overlap)

    return chunks


async def build_active_db_from_temp_sources(force_rebuild: bool = True) -> Dict[str, Any]:
    global rag_system

    async with build_lock:
        db_name = get_active_db_name()
        source_files = db_manager.get_temp_source_files(db_name)

        if not source_files:
            return {
                "ok": False,
                "detail": f'No temp source files found for "{db_name}"',
            }

        app_state["build_running"] = True
        db_manager.write_sync_state(db_name, "building_vector_db")
        set_status("Building vector database...")
        await ui_system(f'Building local DB "{db_name}" from {len(source_files)} source files...')

        if rag_system is None or app_state.get("db_name") != db_name:
            init_rag_for_active_db()

        if rag_system is None:
            app_state["build_running"] = False
            return {"ok": False, "detail": "LightRAG failed to initialize"}

        if force_rebuild:
            rag_system.reset()

        inserted_chunks = 0
        skipped_files = 0
        built_files = 0

        try:
            for file_path in source_files:
                ext = file_path.suffix.lower()

                if ext == ".pdf":
                    text = read_pdf_file(file_path)
                else:
                    text = read_text_file(file_path)

                if not text.strip():
                    skipped_files += 1
                    continue

                rel_source = str(file_path.relative_to(db_manager.tmp_source_dir(db_name))).replace("\\", "/")
                header = f"[SOURCE FILE: {rel_source}]\n\n"
                chunks = chunk_text(header + text)

                for chunk in chunks:
                    await rag_system.ainsert(chunk, meta={"source": rel_source})
                    inserted_chunks += 1

                built_files += 1
                await ui_system(f'Indexed "{rel_source}"')

            rag_system.flush()
            db_manager.mark_built(db_name, chunk_count=inserted_chunks)
            db_manager.set_active_db(db_name)

            upload_result = None
            if UPLOAD_VECTOR_AFTER_BUILD:
                try:
                    upload_result = db_manager.upload_local_vector_db(db_name)
                    await ui_system(f'Uploaded vector DB "{db_name}" back to Azure')
                except Exception as e:
                    await ui_system(f'Build finished, but vector upload failed: {e}')

            db_manager.clear_temp_source_files(db_name)
            await reload_rag_for_selected_db()

            result = {
                "ok": True,
                "db_name": db_name,
                "built_files": built_files,
                "skipped_files": skipped_files,
                "inserted_chunks": inserted_chunks,
                "upload_result": upload_result,
            }
            await ui_system(
                f'Build complete for "{db_name}" - files: {built_files}, chunks: {inserted_chunks}, skipped: {skipped_files}'
            )
            return result

        except Exception as e:
            db_manager.write_sync_state(db_name, "failed", str(e))
            app_state["last_error"] = f"Build failed: {e}"
            await ui_system(f'Build failed for "{db_name}": {e}')
            return {"ok": False, "detail": str(e)}

        finally:
            app_state["build_running"] = False
            set_status("Ready")


async def maybe_answer_rag(user_text: str) -> str:
    if not rag_system:
        return "Local database is not ready yet."

    if not app_state.get("ollama_ready"):
        return "Ollama is not ready yet."

    try:
        result = await rag_system.aquery(
            user_text,
            QueryParam(mode=AURA_CHAT_MODE, top_k=AURA_TOP_K),
        )

        if isinstance(result, dict):
            answer = str(result.get("answer") or "").strip()
        else:
            answer = str(result).strip()

        if not answer:
            return "I could not find an answer."

        return answer
    except Exception as e:
        return f"RAG error: {e}"


async def handle_user_message(user_text: str):
    user_text = (user_text or "").strip()
    if not user_text:
        return

    app_state["last_user_text"] = user_text
    await ui_manager.broadcast({"type": "chat", "sender": "user", "text": user_text})

    low = user_text.lower().strip()
    if low in ("build db", "build database", "rebuild db", "rebuild database"):
        result = await build_active_db_from_temp_sources(force_rebuild=True)
        reply = "Build complete." if result.get("ok") else f'Build failed: {result.get("detail", "unknown error")}'
        app_state["last_ai_text"] = reply
        await ui_manager.broadcast({"type": "chat", "sender": "ai", "text": reply})
        return

    move = map_move_command(user_text)
    if move:
        set_status("Sending movement command...")
        ok = send_serial_command(move)

        if ok:
            reply = f"Movement command sent: {move}"
        else:
            reply = "Failed to send movement command to ESP32."

        app_state["last_ai_text"] = reply
        await ui_manager.broadcast({"type": "chat", "sender": "ai", "text": reply})
        set_status("Ready")
        return

    set_status("Processing...")
    reply = await maybe_answer_rag(user_text)
    app_state["last_ai_text"] = reply
    await ui_manager.broadcast({"type": "chat", "sender": "ai", "text": reply})
    set_status("Ready")


async def telemetry_loop():
    await asyncio.sleep(1)

    while True:
        cpu_percent = psutil.cpu_percent(interval=None)
        ram_percent = psutil.virtual_memory().percent
        gpu_percent = read_gpu_percent()

        if AZURE_BACKEND_URL:
            app_state["connection"] = "Connected"
        else:
            app_state["connection"] = "Local only"

        payload = {
            "type": "telemetry",
            "cpu_percent": cpu_percent,
            "ram_percent": ram_percent,
            "gpu_percent": gpu_percent,
            "db_name": app_state.get("db_name", get_active_db_name()),
            "connection": app_state.get("connection", "Offline"),
            "status_text": app_state.get("status_text", "Ready"),
            "serial_ready": app_state.get("serial_ready", False),
            "ollama_ready": app_state.get("ollama_ready", False),
            "rag_ready": app_state.get("rag_ready", False),
            "build_running": app_state.get("build_running", False),
        }
        await ui_manager.broadcast(payload)

        for line in read_serial_lines():
            await ui_manager.broadcast({"type": "system", "text": f"ESP32: {line}"})

        await asyncio.sleep(1.0)


@app.on_event("startup")
async def startup_event():
    set_status("Booting...")
    init_hardware()
    init_gpu_reader()
    init_rag_for_active_db()
    await check_ollama_ready()

    db_name = get_active_db_name()
    if AUTO_BUILD_ON_STARTUP and db_manager.has_temp_source_files(db_name) and not db_manager.has_local_db(db_name):
        await ui_system(f'Found downloaded source docs for "{db_name}". Starting local build...')
        await build_active_db_from_temp_sources(force_rebuild=True)

    set_status("Ready")
    asyncio.create_task(telemetry_loop())


@app.on_event("shutdown")
async def shutdown_event():
    global gpu_reader, esp_serial

    try:
        if gpu_reader is not None:
            gpu_reader.close()
    except Exception:
        pass

    try:
        if esp_serial is not None:
            esp_serial.close()
    except Exception:
        pass


@app.get("/")
async def serve_ui():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ui_manager.connect(websocket)

    await websocket.send_json(
        {
            "type": "telemetry",
            "cpu_percent": 0,
            "ram_percent": 0,
            "gpu_percent": None,
            "db_name": app_state.get("db_name", get_active_db_name()),
            "connection": app_state.get("connection", "Offline"),
            "status_text": app_state.get("status_text", "Ready"),
            "serial_ready": app_state.get("serial_ready", False),
            "ollama_ready": app_state.get("ollama_ready", False),
            "rag_ready": app_state.get("rag_ready", False),
            "build_running": app_state.get("build_running", False),
        }
    )

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
            except Exception:
                data = {"type": "chat", "text": raw}

            msg_type = str(data.get("type") or "chat").strip().lower()

            if msg_type == "chat":
                await handle_user_message(str(data.get("text") or ""))

            elif msg_type == "move":
                value = str(data.get("value") or "").strip()
                move = map_move_command(value)
                if move:
                    ok = send_serial_command(move)
                    await websocket.send_json(
                        {
                            "type": "system",
                            "text": f'Move "{move}" {"sent" if ok else "failed"}',
                        }
                    )

            elif msg_type == "set_db":
                db_name = str(data.get("value") or "").strip()
                if db_name:
                    db_manager.set_active_db(db_name)
                    await reload_rag_for_selected_db()
                    await websocket.send_json(
                        {
                            "type": "system",
                            "text": f'Active database changed to "{db_name}"',
                        }
                    )

            elif msg_type == "build_db":
                result = await build_active_db_from_temp_sources(force_rebuild=True)
                await websocket.send_json(
                    {
                        "type": "system",
                        "text": "Build complete" if result.get("ok") else f'Build failed: {result.get("detail", "unknown error")}',
                    }
                )

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong", "ts": int(time.time())})

    except WebSocketDisconnect:
        ui_manager.disconnect(websocket)


if __name__ == "__main__":
    uvicorn.run(app, host=APP_HOST, port=APP_PORT)