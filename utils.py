"""Shared helpers: admin checks, target resolution, mentions, durations."""
import functools
import re
from html import escape

from telegram import Update
from telegram.constants import ChatMemberStatus, ChatType
from telegram.ext import ContextTypes

import config

_ADMIN_STATUSES = (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)


def mention(user_id: int, name: str) -> str:
    """Clickable HTML mention that works even without a @username."""
    return f'<a href="tg://user?id={user_id}">{escape(name or str(user_id))}</a>'


async def is_admin(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in _ADMIN_STATUSES
    except Exception:
        return False


async def bot_is_admin(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> bool:
    return await is_admin(context, chat_id, context.bot.id)


def group_only(func):
    """Decorator: command only works inside groups."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            await update.effective_message.reply_text("This command only works inside a group. 👥")
            return
        return await func(update, context)
    return wrapper


def admin_only(func):
    """Decorator: only group admins may run the command, and the bot must be admin too."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        user = update.effective_user
        if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            await update.effective_message.reply_text("This command only works inside a group. 👥")
            return
        if not await is_admin(context, chat.id, user.id):
            await update.effective_message.reply_text("⛔ You need to be an <b>admin</b> to use this.", parse_mode="HTML")
            return
        if not await bot_is_admin(context, chat.id):
            await update.effective_message.reply_text("⚠️ Please make <b>me an admin</b> first so I can do that.", parse_mode="HTML")
            return
        return await func(update, context)
    return wrapper


async def resolve_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Find the user a moderation command is aimed at.
    Supports: reply, @username, numeric id, or a text-mention.
    Returns (user_id, name, reason) or (None, None, None)."""
    msg = update.effective_message
    args = list(context.args or [])

    # 1) Reply is the most reliable
    if msg.reply_to_message and msg.reply_to_message.from_user:
        u = msg.reply_to_message.from_user
        return u.id, u.full_name, (" ".join(args) or None)

    if not args:
        return None, None, None

    target = args[0]
    reason = " ".join(args[1:]) or None

    # 2) text-mention entity carries the user object directly
    for ent in (msg.entities or []):
        if ent.type == "text_mention" and ent.user:
            return ent.user.id, ent.user.full_name, reason

    # 3) @username -> resolve via Telegram
    if target.startswith("@"):
        try:
            chat = await context.bot.get_chat(target)
            return chat.id, (chat.full_name or chat.title or target), reason
        except Exception:
            return None, None, None

    # 4) numeric id
    if target.lstrip("-").isdigit():
        uid = int(target)
        name = str(uid)
        try:
            c = await context.bot.get_chat(uid)
            name = c.full_name or c.title or name
        except Exception:
            pass
        return uid, name, reason

    return None, None, None


_DURATION_RE = re.compile(r"^(\d+)\s*([smhd])$", re.IGNORECASE)
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_duration(text: str):
    """'10m' -> 600 seconds. Returns None if not a duration."""
    if not text:
        return None
    m = _DURATION_RE.match(text.strip())
    if not m:
        return None
    return int(m.group(1)) * _UNIT_SECONDS[m.group(2).lower()]
