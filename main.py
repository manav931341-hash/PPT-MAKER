"""
main.py — FastAPI backend.

Endpoints:
  POST /auth/register
  POST /auth/login
  POST /start
  POST /respond
  POST /upload-reference/{session_id}
  POST /refine/{session_id}
  GET  /download/{session_id}/{filename}
  GET  /session/{session_id}
  GET  /history/{user_id}
  GET  /sessions/{user_id}
  GET  /health
  GET  /stream/{session_id}   ← SSE live status
"""

import os
import json
import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, AsyncGenerator

from dotenv import load_dotenv
load_dotenv()

from fastapi import (
    FastAPI, HTTPException, Depends, UploadFile, File,
    Header, BackgroundTasks, Request
)
from fastapi.responses import FileResponse as FRResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from models import (
    RegisterRequest, LoginRequest, AuthResponse,
    StartRequest, RespondRequest, RefineRequest,
    CheckpointResponse, CheckpointOption,
    FileResponse, ReferenceUploadResponse,
    HistoryItem, SessionSummary,
)
from database import (
    init_db, create_user, get_user_by_credentials, get_user_by_api_key,
    load_session, save_session, get_user_history, get_user_sessions,
)
import agent as _agent
from parsers.reference_parser import parse_reference_file

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Goal-to-File Agent API",
    description="Natural language → PPTX / XLSX with AI",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SSE event queue per session
_sse_queues: dict = {}


# ── DB init on startup ────────────────────────────────────────────────────────
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
    except Exception as e:
        print(f"⚠️  DB init skipped (MySQL not available): {e}")
    yield


# ── API Key middleware ────────────────────────────────────────────────────────
def _get_optional_user(x_api_key: Optional[str] = Header(default=None)) -> Optional[dict]:
    """Returns user dict if valid API key provided, else None (open access fallback)."""
    if x_api_key:
        user = get_user_by_api_key(x_api_key)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return user
    return None


def _require_user(x_api_key: Optional[str] = Header(default=None)) -> dict:
    """Strict auth — requires valid API key."""
    user = _get_optional_user(x_api_key)
    if not user:
        raise HTTPException(status_code=401, detail="API key required. Pass X-Api-Key header.")
    return user


# ── SSE helpers ───────────────────────────────────────────────────────────────
def _sse_push(session_id: str, event: str, data: str):
    if session_id in _sse_queues:
        _sse_queues[session_id].append(f"event: {event}\ndata: {data}\n\n")


async def _sse_generator(session_id: str) -> AsyncGenerator[str, None]:
    _sse_queues[session_id] = []
    try:
        while True:
            if _sse_queues[session_id]:
                yield _sse_queues[session_id].pop(0)
            else:
                yield ": heartbeat\n\n"
                await asyncio.sleep(1)
    finally:
        _sse_queues.pop(session_id, None)


# ── Session loader ────────────────────────────────────────────────────────────
def _load_or_404(session_id: str) -> dict:
    sess = load_session(session_id)
    if not sess:
        # Try in-memory fallback (no DB)
        sess = _in_memory_sessions.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return sess


def _save_sess(sess: dict):
    _in_memory_sessions[sess["session_id"]] = sess
    if sess.get("user_id"):
        try:
            save_session(sess["session_id"], sess["user_id"], sess)
        except Exception:
            pass


# In-memory fallback (no MySQL)
_in_memory_sessions: dict = {}


# ── Response builder ──────────────────────────────────────────────────────────
def _build_response(result: dict):
    sess = result.get("session", {})
    _save_sess(sess)

    if result.get("done") or result.get("files"):
        return {
            "type": "file",
            "session_id": sess.get("session_id"),
            "checkpoint": result.get("checkpoint", 5),
            "checkpoint_name": result.get("checkpoint_name", "Done"),
            "message": result.get("message", "Files ready"),
            "files": result.get("files", []),
        }
    else:
        return {
            "type": "checkpoint",
            "session_id": sess.get("session_id"),
            "checkpoint": result.get("checkpoint"),
            "checkpoint_name": result.get("checkpoint_name"),
            "message": result.get("message"),
            "options": result.get("options", []),
        }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


# ── Auth ──────────────────────────────────────────────────────────────────────
@app.post("/auth/register", response_model=AuthResponse)
def register(req: RegisterRequest):
    try:
        user = create_user(req.username, req.email, req.password)
        return AuthResponse(**user)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/auth/login", response_model=AuthResponse)
def login(req: LoginRequest):
    user = get_user_by_credentials(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return AuthResponse(**user)


# ── Agent flow ────────────────────────────────────────────────────────────────
@app.post("/start")
def start(req: StartRequest, user: Optional[dict] = Depends(_get_optional_user)):
    user_id = user["id"] if user else req.user_id
    try:
        result = _agent.start(req.goal, user_id)
        return _build_response(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/respond")
def respond(req: RespondRequest, user: Optional[dict] = Depends(_get_optional_user)):
    sess = _load_or_404(req.session_id)
    if user:
        sess["user_id"] = user["id"]
    try:
        result = _agent.respond(sess, req.choice, req.extra or "")
        return _build_response(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Reference file upload ─────────────────────────────────────────────────────
@app.post("/upload-reference/{session_id}")
async def upload_reference(
    session_id: str,
    file: UploadFile = File(...),
    user: Optional[dict] = Depends(_get_optional_user),
):
    sess = _load_or_404(session_id)

    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".pptx", ".xlsx"):
        raise HTTPException(status_code=400, detail="Only .pptx or .xlsx files accepted")

    # Save temporarily
    tmp_path = f"/tmp/ref_{session_id}{suffix}"
    content  = await file.read()
    with open(tmp_path, "wb") as f:
        f.write(content)

    file_type = "pptx" if suffix == ".pptx" else "xlsx"
    raw_structure = parse_reference_file(tmp_path, file_type)
    analysis = _agent.analyse_reference(sess, raw_structure, file_type)
    _save_sess(sess)

    return {
        "session_id": session_id,
        "message": (
            f"Reference {file_type.upper()} analysed. "
            f"Detected theme: {analysis.get('detected_theme', 'unknown')}. "
            f"I'll use this as a style guide."
        ),
        "extracted_structure": analysis,
    }


# ── Post-generation chat refinement ──────────────────────────────────────────
@app.post("/refine/{session_id}")
def refine(
    session_id: str,
    req: RefineRequest,
    user: Optional[dict] = Depends(_get_optional_user),
):
    sess = _load_or_404(session_id)
    _sse_push(session_id, "status", "Applying changes...")
    try:
        result = _agent.refine_with_chat(sess, req.message)
        _save_sess(result.get("session", sess))
        _sse_push(session_id, "done", json.dumps(result.get("files", [])))
        return _build_response(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── File download ─────────────────────────────────────────────────────────────
@app.get("/download/{session_id}/{filename}")
def download(session_id: str, filename: str):
    path = os.path.join(OUTPUT_DIR, session_id, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    media = (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        if filename.endswith(".pptx") else
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return FRResponse(path, media_type=media, filename=filename)


# ── SSE streaming ─────────────────────────────────────────────────────────────
@app.get("/stream/{session_id}")
async def stream(session_id: str):
    return StreamingResponse(
        _sse_generator(session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Session & history ─────────────────────────────────────────────────────────
@app.get("/session/{session_id}")
def get_session(session_id: str, user: Optional[dict] = Depends(_get_optional_user)):
    sess = _load_or_404(session_id)
    return {
        "session_id": session_id,
        "goal": sess.get("goal"),
        "state": sess.get("state"),
        "file_type": sess.get("file_type"),
        "style": sess.get("style"),
        "theme_id": sess.get("theme_id"),
        "generated_files": sess.get("generated_files", []),
        "chat_history": sess.get("chat_history", []),
    }


@app.get("/history/{user_id}")
def history(user_id: int, user: dict = Depends(_require_user)):
    if user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        return get_user_history(user_id)
    except Exception:
        return []


@app.get("/sessions/{user_id}")
def sessions(user_id: int, user: dict = Depends(_require_user)):
    if user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        return get_user_sessions(user_id)
    except Exception:
        return []


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
