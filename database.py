"""
database.py — MySQL integration for users, sessions, and generation history.
Tables: users, sessions, generation_history
"""

import os
import hashlib
import secrets
import datetime
from typing import Optional
import mysql.connector
from mysql.connector import pooling

# ── connection pool ──────────────────────────────────────────────────────────
_pool: Optional[pooling.MySQLConnectionPool] = None


def get_pool() -> pooling.MySQLConnectionPool:
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="gtf_pool",
            pool_size=5,
            host=os.getenv("MYSQL_HOST", "localhost"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DB", "goal_to_file"),
            autocommit=True,
        )
    return _pool


def get_conn():
    return get_pool().get_connection()


# ── schema bootstrap ─────────────────────────────────────────────────────────
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(80)  NOT NULL UNIQUE,
    email         VARCHAR(200) NOT NULL UNIQUE,
    password_hash VARCHAR(128) NOT NULL,
    created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id   VARCHAR(64)  PRIMARY KEY,
    user_id      INT          NOT NULL,
    goal         TEXT,
    state        VARCHAR(40)  DEFAULT 'C1_INTENT',
    file_type    VARCHAR(10),
    style        VARCHAR(40),
    structure    JSON,
    content      JSON,
    created_at   DATETIME     DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS generation_history (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    user_id      INT          NOT NULL,
    session_id   VARCHAR(64),
    file_type    VARCHAR(10),
    filename     VARCHAR(200),
    goal         TEXT,
    theme        VARCHAR(40),
    created_at   DATETIME     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS api_keys (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    user_id      INT          NOT NULL UNIQUE,
    api_key      VARCHAR(64)  NOT NULL UNIQUE,
    created_at   DATETIME     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""


def init_db():
    """Create all tables if they don't exist."""
    conn = get_conn()
    cur = conn.cursor()
    for stmt in SCHEMA_SQL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            cur.execute(stmt)
    cur.close()
    conn.close()
    print("✅ Database tables initialised.")


# ── password helpers ─────────────────────────────────────────────────────────
def _hash_password(password: str) -> str:
    """Hash password with PBKDF2-HMAC-SHA256 + a fixed app salt.
    Stored as hex. For production use bcrypt, but this is safe for a hackathon."""
    salt = os.getenv("PASSWORD_SALT", "fileforge_default_salt_change_me").encode()
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260000)
    return dk.hex()


def _generate_api_key() -> str:
    return "gtf-" + secrets.token_hex(28)


# ── user CRUD ────────────────────────────────────────────────────────────────
def create_user(username: str, email: str, password: str) -> dict:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
            (username, email, _hash_password(password)),
        )
        user_id = cur.lastrowid
        api_key = _generate_api_key()
        cur.execute(
            "INSERT INTO api_keys (user_id, api_key) VALUES (%s, %s)",
            (user_id, api_key),
        )
        return {"user_id": user_id, "username": username, "email": email, "api_key": api_key}
    finally:
        cur.close()
        conn.close()


def get_user_by_credentials(username: str, password: str) -> Optional[dict]:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT u.id, u.username, u.email, k.api_key "
            "FROM users u LEFT JOIN api_keys k ON k.user_id = u.id "
            "WHERE u.username = %s AND u.password_hash = %s",
            (username, _hash_password(password)),
        )
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()


def get_user_by_api_key(api_key: str) -> Optional[dict]:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT u.id, u.username, u.email FROM users u "
            "JOIN api_keys k ON k.user_id = u.id WHERE k.api_key = %s",
            (api_key,),
        )
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()


# ── session CRUD ─────────────────────────────────────────────────────────────
def save_session(session_id: str, user_id: int, data: dict):
    import json
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO sessions (session_id, user_id, goal, state, file_type, style, structure, content)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE
                 state=VALUES(state), file_type=VALUES(file_type),
                 style=VALUES(style), structure=VALUES(structure),
                 content=VALUES(content), updated_at=CURRENT_TIMESTAMP""",
            (
                session_id, user_id,
                data.get("goal"),
                data.get("state", "C1_INTENT"),
                data.get("file_type"),
                data.get("style"),
                json.dumps(data.get("structure")) if data.get("structure") else None,
                json.dumps(data.get("content")) if data.get("content") else None,
            ),
        )
    finally:
        cur.close()
        conn.close()


def load_session(session_id: str) -> Optional[dict]:
    import json
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM sessions WHERE session_id = %s", (session_id,))
        row = cur.fetchone()
        if row:
            if row.get("structure") and isinstance(row["structure"], str):
                row["structure"] = json.loads(row["structure"])
            if row.get("content") and isinstance(row["content"], str):
                row["content"] = json.loads(row["content"])
        return row
    finally:
        cur.close()
        conn.close()


def get_user_sessions(user_id: int) -> list:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT session_id, goal, state, file_type, style, created_at, updated_at "
            "FROM sessions WHERE user_id = %s ORDER BY updated_at DESC LIMIT 50",
            (user_id,),
        )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


# ── history CRUD ─────────────────────────────────────────────────────────────
def log_generation(user_id: int, session_id: str, file_type: str, filename: str, goal: str, theme: str):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO generation_history (user_id, session_id, file_type, filename, goal, theme) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (user_id, session_id, file_type, filename, goal, theme),
        )
    finally:
        cur.close()
        conn.close()


def get_user_history(user_id: int) -> list:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT * FROM generation_history WHERE user_id = %s ORDER BY created_at DESC LIMIT 100",
            (user_id,),
        )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()
