"""Tiny SQLite layer. Stores per-group settings, warns, notes and the
set of users/groups (used for /stats and /broadcast).

Note: on Render's free tier the disk is wiped on every redeploy, so this
is "good enough" persistence. Swap to a hosted DB later if you need it to
survive deploys.
"""
import sqlite3
import threading

_DB_PATH = "bot.db"
_lock = threading.Lock()
_conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
_conn.row_factory = sqlite3.Row


def init_db() -> None:
    with _lock:
        _conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                chat_id INTEGER, key TEXT, value TEXT,
                PRIMARY KEY (chat_id, key)
            );
            CREATE TABLE IF NOT EXISTS warns (
                chat_id INTEGER, user_id INTEGER, count INTEGER DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS notes (
                chat_id INTEGER, name TEXT, content TEXT,
                PRIMARY KEY (chat_id, name)
            );
            CREATE TABLE IF NOT EXISTS users  (user_id INTEGER PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS chats  (chat_id INTEGER PRIMARY KEY);
            """
        )
        _conn.commit()


# ---------- settings ----------
def set_setting(chat_id: int, key: str, value: str) -> None:
    with _lock:
        _conn.execute(
            "INSERT INTO settings (chat_id, key, value) VALUES (?,?,?) "
            "ON CONFLICT(chat_id, key) DO UPDATE SET value=excluded.value",
            (chat_id, key, value),
        )
        _conn.commit()


def get_setting(chat_id: int, key: str, default=None):
    with _lock:
        row = _conn.execute(
            "SELECT value FROM settings WHERE chat_id=? AND key=?", (chat_id, key)
        ).fetchone()
    return row["value"] if row else default


def del_setting(chat_id: int, key: str) -> None:
    with _lock:
        _conn.execute("DELETE FROM settings WHERE chat_id=? AND key=?", (chat_id, key))
        _conn.commit()


# ---------- warns ----------
def add_warn(chat_id: int, user_id: int) -> int:
    with _lock:
        _conn.execute(
            "INSERT INTO warns (chat_id, user_id, count) VALUES (?,?,1) "
            "ON CONFLICT(chat_id, user_id) DO UPDATE SET count=count+1",
            (chat_id, user_id),
        )
        _conn.commit()
        row = _conn.execute(
            "SELECT count FROM warns WHERE chat_id=? AND user_id=?", (chat_id, user_id)
        ).fetchone()
    return row["count"] if row else 0


def get_warns(chat_id: int, user_id: int) -> int:
    with _lock:
        row = _conn.execute(
            "SELECT count FROM warns WHERE chat_id=? AND user_id=?", (chat_id, user_id)
        ).fetchone()
    return row["count"] if row else 0


def reset_warns(chat_id: int, user_id: int) -> None:
    with _lock:
        _conn.execute("DELETE FROM warns WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        _conn.commit()


# ---------- notes ----------
def save_note(chat_id: int, name: str, content: str) -> None:
    with _lock:
        _conn.execute(
            "INSERT INTO notes (chat_id, name, content) VALUES (?,?,?) "
            "ON CONFLICT(chat_id, name) DO UPDATE SET content=excluded.content",
            (chat_id, name.lower(), content),
        )
        _conn.commit()


def get_note(chat_id: int, name: str):
    with _lock:
        row = _conn.execute(
            "SELECT content FROM notes WHERE chat_id=? AND name=?", (chat_id, name.lower())
        ).fetchone()
    return row["content"] if row else None


def list_notes(chat_id: int):
    with _lock:
        rows = _conn.execute(
            "SELECT name FROM notes WHERE chat_id=? ORDER BY name", (chat_id,)
        ).fetchall()
    return [r["name"] for r in rows]


def del_note(chat_id: int, name: str) -> None:
    with _lock:
        _conn.execute("DELETE FROM notes WHERE chat_id=? AND name=?", (chat_id, name.lower()))
        _conn.commit()


# ---------- tracking ----------
def track_user(user_id: int) -> None:
    with _lock:
        _conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        _conn.commit()


def track_chat(chat_id: int) -> None:
    with _lock:
        _conn.execute("INSERT OR IGNORE INTO chats (chat_id) VALUES (?)", (chat_id,))
        _conn.commit()


def all_user_ids():
    with _lock:
        rows = _conn.execute("SELECT user_id FROM users").fetchall()
    return [r["user_id"] for r in rows]


def stats():
    with _lock:
        u = _conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        g = _conn.execute("SELECT COUNT(*) c FROM chats").fetchone()["c"]
    return u, g
