"""
models.py — Pydantic request/response models for the entire API.
"""

from typing import Optional, List, Any, Dict
from pydantic import BaseModel, EmailStr


# ── Auth ─────────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    user_id: int
    username: str
    email: str
    api_key: str


# ── Agent flow ────────────────────────────────────────────────────────────────
class StartRequest(BaseModel):
    goal: str
    user_id: Optional[int] = None          # optional when auth disabled


class RespondRequest(BaseModel):
    session_id: str
    choice: str                             # "A" / "B" / "C" / "confirm" / free text
    extra: Optional[str] = None            # extra modification instruction
    user_id: Optional[int] = None


class CheckpointOption(BaseModel):
    key: str
    label: str
    description: str


class CheckpointResponse(BaseModel):
    session_id: str
    checkpoint: int
    checkpoint_name: str
    message: str
    options: Optional[List[CheckpointOption]] = None
    data: Optional[Dict[str, Any]] = None


class FileResponse(BaseModel):
    session_id: str
    message: str
    files: List[Dict[str, str]]             # [{"filename": "...", "download_url": "..."}]


# ── Upload reference ──────────────────────────────────────────────────────────
class ReferenceUploadResponse(BaseModel):
    session_id: str
    message: str
    extracted_structure: Dict[str, Any]


# ── Chat refinement ───────────────────────────────────────────────────────────
class RefineRequest(BaseModel):
    session_id: str
    message: str
    user_id: Optional[int] = None


class RefineResponse(BaseModel):
    session_id: str
    message: str
    regenerated: bool
    files: Optional[List[Dict[str, str]]] = None


# ── History ───────────────────────────────────────────────────────────────────
class HistoryItem(BaseModel):
    id: int
    session_id: str
    file_type: str
    filename: str
    goal: str
    theme: str
    created_at: Any


class SessionSummary(BaseModel):
    session_id: str
    goal: Optional[str]
    state: str
    file_type: Optional[str]
    style: Optional[str]
    created_at: Any
    updated_at: Any
