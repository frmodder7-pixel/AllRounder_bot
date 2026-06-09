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
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY, name TEXT, username TEXT
            );
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY, title TEXT
            );
            CREATE TABLE IF NOT EXISTS activity (
                chat_id INTEGER, user_id INTEGER, day TEXT,
                count INTEGER DEFAULT 0, name TEXT,
                PRIMARY KEY (chat_id, user_id, day)
            );
            CREATE TABLE IF NOT EXISTS points (
                chat_id INTEGER, user_id INTEGER,
                total INTEGER DEFAULT 0, name TEXT,
                PRIMARY KEY (chat_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS daily (
                chat_id INTEGER, user_id INTEGER,
                last_day TEXT, streak INTEGER DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS weekly (
                chat_id INTEGER, user_id INTEGER, week TEXT,
                count INTEGER DEFAULT 0, name TEXT,
                PRIMARY KEY (chat_id, user_id, week)
            );
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
def track_user(user_id: int, name: str = None, username: str = None) -> None:
    with _lock:
        _conn.execute(
            "INSERT INTO users (user_id, name, username) VALUES (?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "name=COALESCE(excluded.name, users.name), "
            "username=COALESCE(excluded.username, users.username)",
            (user_id, name, username),
        )
        _conn.commit()


def track_chat(chat_id: int, title: str = None) -> None:
    with _lock:
        _conn.execute(
            "INSERT INTO chats (chat_id, title) VALUES (?,?) "
            "ON CONFLICT(chat_id) DO UPDATE SET title=COALESCE(excluded.title, chats.title)",
            (chat_id, title),
        )
        _conn.commit()


def all_user_ids():
    with _lock:
        rows = _conn.execute("SELECT user_id FROM users").fetchall()
    return [r["user_id"] for r in rows]


def list_users(limit: int = 30):
    with _lock:
        return _conn.execute(
            "SELECT user_id, name, username FROM users ORDER BY rowid DESC LIMIT ?", (limit,)
        ).fetchall()


def list_chats(limit: int = 30):
    with _lock:
        return _conn.execute(
            "SELECT chat_id, title FROM chats ORDER BY rowid DESC LIMIT ?", (limit,)
        ).fetchall()


def stats():
    with _lock:
        u = _conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        g = _conn.execute("SELECT COUNT(*) c FROM chats").fetchone()["c"]
    return u, g


# ---------- activity & points (leaderboard) ----------
def bump_activity(chat_id: int, user_id: int, day: str, name: str) -> None:
    """+1 to today's message count and +1 to all-time points."""
    with _lock:
        _conn.execute(
            "INSERT INTO activity (chat_id, user_id, day, count, name) VALUES (?,?,?,1,?) "
            "ON CONFLICT(chat_id, user_id, day) DO UPDATE SET count=count+1, name=excluded.name",
            (chat_id, user_id, day, name),
        )
        _conn.execute(
            "INSERT INTO points (chat_id, user_id, total, name) VALUES (?,?,1,?) "
            "ON CONFLICT(chat_id, user_id) DO UPDATE SET total=total+1, name=excluded.name",
            (chat_id, user_id, name),
        )
        _conn.commit()


def add_points(chat_id: int, user_id: int, name: str, amount: int) -> int:
    """Add an arbitrary number of points (games, daily bonus). Returns new total."""
    with _lock:
        _conn.execute(
            "INSERT INTO points (chat_id, user_id, total, name) VALUES (?,?,?,?) "
            "ON CONFLICT(chat_id, user_id) DO UPDATE SET total=total+?, name=excluded.name",
            (chat_id, user_id, amount, name, amount),
        )
        row = _conn.execute(
            "SELECT total FROM points WHERE chat_id=? AND user_id=?", (chat_id, user_id)
        ).fetchone()
        _conn.commit()
    return row["total"] if row else amount


def bump_weekly(chat_id: int, user_id: int, week: str, name: str) -> None:
    with _lock:
        _conn.execute(
            "INSERT INTO weekly (chat_id, user_id, week, count, name) VALUES (?,?,?,1,?) "
            "ON CONFLICT(chat_id, user_id, week) DO UPDATE SET count=count+1, name=excluded.name",
            (chat_id, user_id, week, name),
        )
        _conn.commit()


def top_weekly(chat_id: int, week: str, limit: int = 1):
    with _lock:
        return _conn.execute(
            "SELECT user_id, name, count FROM weekly WHERE chat_id=? AND week=? "
            "ORDER BY count DESC LIMIT ?", (chat_id, week, limit)
        ).fetchall()


def claim_daily(chat_id: int, user_id: int, today: str, yesterday: str):
    """Handle a /daily claim. Returns (already_claimed, streak)."""
    with _lock:
        row = _conn.execute(
            "SELECT last_day, streak FROM daily WHERE chat_id=? AND user_id=?",
            (chat_id, user_id),
        ).fetchone()
        if row and row["last_day"] == today:
            return True, row["streak"]
        if row and row["last_day"] == yesterday:
            streak = row["streak"] + 1
        else:
            streak = 1
        _conn.execute(
            "INSERT INTO daily (chat_id, user_id, last_day, streak) VALUES (?,?,?,?) "
            "ON CONFLICT(chat_id, user_id) DO UPDATE SET last_day=excluded.last_day, streak=excluded.streak",
            (chat_id, user_id, today, streak),
        )
        _conn.commit()
    return False, streak


def weeks_active_chats(week: str):
    with _lock:
        rows = _conn.execute(
            "SELECT DISTINCT chat_id FROM weekly WHERE week=?", (week,)
        ).fetchall()
    return [r["chat_id"] for r in rows]


def top_today(chat_id: int, day: str, limit: int = 5):
    with _lock:
        return _conn.execute(
            "SELECT user_id, name, count FROM activity WHERE chat_id=? AND day=? "
            "ORDER BY count DESC LIMIT ?", (chat_id, day, limit)
        ).fetchall()


def top_alltime(chat_id: int, limit: int = 10):
    with _lock:
        return _conn.execute(
            "SELECT user_id, name, total FROM points WHERE chat_id=? "
            "ORDER BY total DESC LIMIT ?", (chat_id, limit)
        ).fetchall()


def my_rank(chat_id: int, user_id: int):
    """Return (total_points, rank) for a user in a chat, or (0, None)."""
    with _lock:
        row = _conn.execute(
            "SELECT total FROM points WHERE chat_id=? AND user_id=?", (chat_id, user_id)
        ).fetchone()
        if not row:
            return 0, None
        rank = _conn.execute(
            "SELECT COUNT(*) c FROM points WHERE chat_id=? AND total > ?",
            (chat_id, row["total"]),
        ).fetchone()["c"] + 1
    return row["total"], rank


def all_active_chats(day: str):
    """Chat ids that had any activity on a given day (for the nightly job)."""
    with _lock:
        rows = _conn.execute(
            "SELECT DISTINCT chat_id FROM activity WHERE day=?", (day,)
        ).fetchall()
    return [r["chat_id"] for r in rows]
