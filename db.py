"""Database layer that works with BOTH PostgreSQL and SQLite.

• If the env var DATABASE_URL is set (Railway Postgres) -> PostgreSQL,
  so all data is PERMANENT and survives every redeploy. ✅
• Otherwise -> a local SQLite file (handy for testing; resets on redeploy).

All ids use BIGINT (Telegram ids are large). Queries are written with
'?' placeholders and auto-translated to '%s' for Postgres.
"""
import os
import threading

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
_USE_PG = DATABASE_URL.startswith("postgres")

if _USE_PG:
    import psycopg2
    from psycopg2.pool import SimpleConnectionPool

    _pool = SimpleConnectionPool(1, 5, dsn=DATABASE_URL)
else:
    import sqlite3

    _sqlite = sqlite3.connect("bot.db", check_same_thread=False)
    _sqlite.row_factory = sqlite3.Row

_lock = threading.Lock()


def _q(query: str) -> str:
    return query.replace("?", "%s") if _USE_PG else query


def _run(query: str, params=(), fetch=None):
    """Execute a query. fetch in {None, 'one', 'all'}. Returns dict / list[dict] / None."""
    q = _q(query)
    if _USE_PG:
        conn = _pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(q, params)
                if fetch == "one":
                    row = cur.fetchone()
                    result = dict(zip([d[0] for d in cur.description], row)) if row else None
                elif fetch == "all":
                    cols = [d[0] for d in cur.description]
                    result = [dict(zip(cols, r)) for r in cur.fetchall()]
                else:
                    result = None
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            _pool.putconn(conn)
    else:
        with _lock:
            cur = _sqlite.execute(q, params)
            if fetch == "one":
                row = cur.fetchone()
                result = dict(row) if row else None
            elif fetch == "all":
                result = [dict(r) for r in cur.fetchall()]
            else:
                result = None
            _sqlite.commit()
            return result


_SCHEMA = [
    "CREATE TABLE IF NOT EXISTS settings (chat_id BIGINT, key TEXT, value TEXT, PRIMARY KEY (chat_id, key))",
    "CREATE TABLE IF NOT EXISTS warns (chat_id BIGINT, user_id BIGINT, count INTEGER DEFAULT 0, PRIMARY KEY (chat_id, user_id))",
    "CREATE TABLE IF NOT EXISTS notes (chat_id BIGINT, name TEXT, content TEXT, PRIMARY KEY (chat_id, name))",
    "CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, name TEXT, username TEXT)",
    "CREATE TABLE IF NOT EXISTS chats (chat_id BIGINT PRIMARY KEY, title TEXT)",
    "CREATE TABLE IF NOT EXISTS activity (chat_id BIGINT, user_id BIGINT, day TEXT, count INTEGER DEFAULT 0, name TEXT, PRIMARY KEY (chat_id, user_id, day))",
    "CREATE TABLE IF NOT EXISTS points (chat_id BIGINT, user_id BIGINT, total INTEGER DEFAULT 0, name TEXT, PRIMARY KEY (chat_id, user_id))",
    "CREATE TABLE IF NOT EXISTS daily (chat_id BIGINT, user_id BIGINT, last_day TEXT, streak INTEGER DEFAULT 0, PRIMARY KEY (chat_id, user_id))",
    "CREATE TABLE IF NOT EXISTS weekly (chat_id BIGINT, user_id BIGINT, week TEXT, count INTEGER DEFAULT 0, name TEXT, PRIMARY KEY (chat_id, user_id, week))",
]


def init_db() -> None:
    for stmt in _SCHEMA:
        _run(stmt)


# ---------- settings ----------
def set_setting(chat_id: int, key: str, value: str) -> None:
    _run(
        "INSERT INTO settings (chat_id, key, value) VALUES (?,?,?) "
        "ON CONFLICT (chat_id, key) DO UPDATE SET value=excluded.value",
        (chat_id, key, value),
    )


def get_setting(chat_id: int, key: str, default=None):
    row = _run("SELECT value FROM settings WHERE chat_id=? AND key=?", (chat_id, key), "one")
    return row["value"] if row else default


def del_setting(chat_id: int, key: str) -> None:
    _run("DELETE FROM settings WHERE chat_id=? AND key=?", (chat_id, key))


# ---------- warns ----------
def add_warn(chat_id: int, user_id: int) -> int:
    _run(
        "INSERT INTO warns (chat_id, user_id, count) VALUES (?,?,1) "
        "ON CONFLICT (chat_id, user_id) DO UPDATE SET count=warns.count+1",
        (chat_id, user_id),
    )
    row = _run("SELECT count FROM warns WHERE chat_id=? AND user_id=?", (chat_id, user_id), "one")
    return row["count"] if row else 0


def get_warns(chat_id: int, user_id: int) -> int:
    row = _run("SELECT count FROM warns WHERE chat_id=? AND user_id=?", (chat_id, user_id), "one")
    return row["count"] if row else 0


def reset_warns(chat_id: int, user_id: int) -> None:
    _run("DELETE FROM warns WHERE chat_id=? AND user_id=?", (chat_id, user_id))


# ---------- notes ----------
def save_note(chat_id: int, name: str, content: str) -> None:
    _run(
        "INSERT INTO notes (chat_id, name, content) VALUES (?,?,?) "
        "ON CONFLICT (chat_id, name) DO UPDATE SET content=excluded.content",
        (chat_id, name.lower(), content),
    )


def get_note(chat_id: int, name: str):
    row = _run("SELECT content FROM notes WHERE chat_id=? AND name=?", (chat_id, name.lower()), "one")
    return row["content"] if row else None


def list_notes(chat_id: int):
    rows = _run("SELECT name FROM notes WHERE chat_id=? ORDER BY name", (chat_id,), "all")
    return [r["name"] for r in rows]


def del_note(chat_id: int, name: str) -> None:
    _run("DELETE FROM notes WHERE chat_id=? AND name=?", (chat_id, name.lower()))


# ---------- tracking ----------
def track_user(user_id: int, name: str = None, username: str = None) -> None:
    _run(
        "INSERT INTO users (user_id, name, username) VALUES (?,?,?) "
        "ON CONFLICT (user_id) DO UPDATE SET "
        "name=COALESCE(excluded.name, users.name), "
        "username=COALESCE(excluded.username, users.username)",
        (user_id, name, username),
    )


def track_chat(chat_id: int, title: str = None) -> None:
    _run(
        "INSERT INTO chats (chat_id, title) VALUES (?,?) "
        "ON CONFLICT (chat_id) DO UPDATE SET title=COALESCE(excluded.title, chats.title)",
        (chat_id, title),
    )


def all_user_ids():
    rows = _run("SELECT user_id FROM users", (), "all")
    return [r["user_id"] for r in rows]


def list_users(limit: int = 30):
    return _run("SELECT user_id, name, username FROM users ORDER BY user_id DESC LIMIT ?", (limit,), "all")


def list_chats(limit: int = 30):
    return _run("SELECT chat_id, title FROM chats ORDER BY chat_id DESC LIMIT ?", (limit,), "all")


def stats():
    u = _run("SELECT COUNT(*) AS c FROM users", (), "one")["c"]
    g = _run("SELECT COUNT(*) AS c FROM chats", (), "one")["c"]
    return u, g


# ---------- activity & points (leaderboard) ----------
def bump_activity(chat_id: int, user_id: int, day: str, name: str) -> None:
    _run(
        "INSERT INTO activity (chat_id, user_id, day, count, name) VALUES (?,?,?,1,?) "
        "ON CONFLICT (chat_id, user_id, day) DO UPDATE SET count=activity.count+1, name=excluded.name",
        (chat_id, user_id, day, name),
    )
    _run(
        "INSERT INTO points (chat_id, user_id, total, name) VALUES (?,?,1,?) "
        "ON CONFLICT (chat_id, user_id) DO UPDATE SET total=points.total+1, name=excluded.name",
        (chat_id, user_id, name),
    )


def add_points(chat_id: int, user_id: int, name: str, amount: int) -> int:
    _run(
        "INSERT INTO points (chat_id, user_id, total, name) VALUES (?,?,?,?) "
        "ON CONFLICT (chat_id, user_id) DO UPDATE SET total=points.total+?, name=excluded.name",
        (chat_id, user_id, amount, name, amount),
    )
    row = _run("SELECT total FROM points WHERE chat_id=? AND user_id=?", (chat_id, user_id), "one")
    return row["total"] if row else amount


def bump_weekly(chat_id: int, user_id: int, week: str, name: str) -> None:
    _run(
        "INSERT INTO weekly (chat_id, user_id, week, count, name) VALUES (?,?,?,1,?) "
        "ON CONFLICT (chat_id, user_id, week) DO UPDATE SET count=weekly.count+1, name=excluded.name",
        (chat_id, user_id, week, name),
    )


def top_weekly(chat_id: int, week: str, limit: int = 1):
    return _run(
        "SELECT user_id, name, count FROM weekly WHERE chat_id=? AND week=? ORDER BY count DESC LIMIT ?",
        (chat_id, week, limit), "all",
    )


def claim_daily(chat_id: int, user_id: int, today: str, yesterday: str):
    """Handle a /daily claim. Returns (already_claimed, streak)."""
    row = _run("SELECT last_day, streak FROM daily WHERE chat_id=? AND user_id=?", (chat_id, user_id), "one")
    if row and row["last_day"] == today:
        return True, row["streak"]
    if row and row["last_day"] == yesterday:
        streak = row["streak"] + 1
    else:
        streak = 1
    _run(
        "INSERT INTO daily (chat_id, user_id, last_day, streak) VALUES (?,?,?,?) "
        "ON CONFLICT (chat_id, user_id) DO UPDATE SET last_day=excluded.last_day, streak=excluded.streak",
        (chat_id, user_id, today, streak),
    )
    return False, streak


def weeks_active_chats(week: str):
    rows = _run("SELECT DISTINCT chat_id FROM weekly WHERE week=?", (week,), "all")
    return [r["chat_id"] for r in rows]


def top_today(chat_id: int, day: str, limit: int = 5):
    return _run(
        "SELECT user_id, name, count FROM activity WHERE chat_id=? AND day=? ORDER BY count DESC LIMIT ?",
        (chat_id, day, limit), "all",
    )


def top_alltime(chat_id: int, limit: int = 10):
    return _run(
        "SELECT user_id, name, total FROM points WHERE chat_id=? ORDER BY total DESC LIMIT ?",
        (chat_id, limit), "all",
    )


def my_rank(chat_id: int, user_id: int):
    """Return (total_points, rank) for a user in a chat, or (0, None)."""
    row = _run("SELECT total FROM points WHERE chat_id=? AND user_id=?", (chat_id, user_id), "one")
    if not row:
        return 0, None
    higher = _run(
        "SELECT COUNT(*) AS c FROM points WHERE chat_id=? AND total > ?", (chat_id, row["total"]), "one"
    )["c"]
    return row["total"], higher + 1


def all_active_chats(day: str):
    rows = _run("SELECT DISTINCT chat_id FROM activity WHERE day=?", (day,), "all")
    return [r["chat_id"] for r in rows]
