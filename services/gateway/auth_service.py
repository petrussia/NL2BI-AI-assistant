from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


class AuthService:
    def __init__(self, db_path: Path, secret: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.secret = secret.encode("utf-8")
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'analyst',
                    created_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL COLLATE NOCASE,
                    title TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    settings_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS chat_messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    username TEXT NOT NULL COLLATE NOCASE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    artifacts_json TEXT NOT NULL DEFAULT '[]',
                    created_at INTEGER NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
                    FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_updated
                    ON chat_sessions(username, updated_at DESC);

                CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
                    ON chat_messages(session_id, created_at ASC);
                """
            )

    @staticmethod
    def _now() -> int:
        return int(time.time())

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            120_000,
        ).hex()

    def _token(self, payload: dict[str, Any]) -> str:
        body = _b64url(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
        signature = _b64url(hmac.new(self.secret, body.encode("ascii"), hashlib.sha256).digest())
        return f"{body}.{signature}"

    def verify_token(self, token: str) -> dict[str, Any] | None:
        try:
            body, signature = token.split(".", 1)
            expected = _b64url(hmac.new(self.secret, body.encode("ascii"), hashlib.sha256).digest())
            if not hmac.compare_digest(signature, expected):
                return None
            payload = json.loads(_b64url_decode(body))
        except Exception:
            return None
        if int(payload.get("exp", 0)) < self._now():
            return None
        username = str(payload.get("sub") or "")
        if not username:
            return None
        user = self.get_user(username)
        return user

    def register(self, username: str, password: str) -> dict[str, Any]:
        username = username.strip()
        if len(username) < 3:
            raise ValueError("Username must contain at least 3 characters.")
        if len(password) < 6:
            raise ValueError("Password must contain at least 6 characters.")
        salt = secrets.token_hex(16)
        password_hash = self._hash_password(password, salt)
        now = self._now()
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO users(username, password_hash, password_salt, role, created_at) VALUES (?, ?, ?, ?, ?)",
                    (username, password_hash, salt, "analyst", now),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("User already exists.") from exc
        return self.authenticate(username, password)

    def authenticate(self, username: str, password: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username.strip(),)).fetchone()
        if row is None:
            raise ValueError("Invalid username or password.")
        expected = self._hash_password(password, row["password_salt"])
        if not hmac.compare_digest(expected, row["password_hash"]):
            raise ValueError("Invalid username or password.")
        exp = self._now() + 12 * 3600
        return {
            "username": row["username"],
            "role": row["role"],
            "token": self._token({"sub": row["username"], "role": row["role"], "exp": exp}),
        }

    def get_user(self, username: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT username, role FROM users WHERE username = ?", (username,)).fetchone()
        if row is None:
            return None
        return {"username": row["username"], "role": row["role"]}

    def list_sessions(self, username: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM chat_sessions WHERE username = ? ORDER BY updated_at DESC",
                (username,),
            ).fetchall()
        return [self._session_dict(row) for row in rows]

    def create_session(self, username: str, title: str | None = None) -> dict[str, Any]:
        now = self._now()
        session_id = uuid.uuid4().hex[:12]
        title = (title or "Новый чат").strip() or "Новый чат"
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO chat_sessions(session_id, username, title, created_at, updated_at, settings_json) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, username, title[:120], now, now, "{}"),
            )
            row = conn.execute("SELECT * FROM chat_sessions WHERE session_id = ?", (session_id,)).fetchone()
        return self._session_dict(row)

    def ensure_session(self, username: str, session_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM chat_sessions WHERE username = ? AND session_id = ?",
                (username, session_id),
            ).fetchone()
        if row is None:
            raise KeyError("Chat session not found.")
        return self._session_dict(row)

    def list_messages(self, username: str, session_id: str) -> list[dict[str, Any]]:
        self.ensure_session(username, session_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM chat_messages WHERE username = ? AND session_id = ? ORDER BY created_at ASC",
                (username, session_id),
            ).fetchall()
        return [self._message_dict(row) for row in rows]

    def add_message(
        self,
        *,
        username: str,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        artifacts: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self.ensure_session(username, session_id)
        now = self._now()
        message_id = uuid.uuid4().hex
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_messages(message_id, session_id, username, role, content, metadata_json, artifacts_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    session_id,
                    username,
                    role,
                    content,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    json.dumps(artifacts or [], ensure_ascii=False),
                    now,
                ),
            )
            conn.execute(
                "UPDATE chat_sessions SET updated_at = ?, title = CASE WHEN title = 'Новый чат' AND ? = 'user' THEN ? ELSE title END WHERE session_id = ?",
                (now, role, content[:80], session_id),
            )
            row = conn.execute("SELECT * FROM chat_messages WHERE message_id = ?", (message_id,)).fetchone()
        return self._message_dict(row)

    @staticmethod
    def _session_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "session_id": row["session_id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "settings": json.loads(row["settings_json"] or "{}"),
        }

    @staticmethod
    def _message_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "message_id": row["message_id"],
            "session_id": row["session_id"],
            "role": row["role"],
            "content": row["content"],
            "metadata": json.loads(row["metadata_json"] or "{}"),
            "artifacts": json.loads(row["artifacts_json"] or "[]"),
            "created_at": row["created_at"],
        }

