"""Admin & moderation. Every action explains its reason, so the group
always knows *why* the bot did something."""
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from telegram import ChatPermissions, Update
from telegram.constants import ChatType
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

import config
import db
from utils import admin_only, is_admin, mention, parse_duration, resolve_target

MUTED = ChatPermissions(can_send_messages=False)
UNMUTED = ChatPermissions(
    can_send_messages=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_invite_users=True,
)


def _reason(text):
    return f"\n📋 <b>Reason:</b> {text}" if text else "\n📋 <b>Reason:</b> not specified"


# ============ BAN / KICK ============
@admin_only
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name, reason = await resolve_target(update, context)
    if not uid:
        await update.message.reply_html("Reply to a user or pass <code>@user / id</code> to ban.")
        return
    if await is_admin(context, update.effective_chat.id, uid):
        await update.message.reply_text("😅 I won't ban an admin.")
        return
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, uid)
        await update.message.reply_html(f"🔨 Banned {mention(uid, name)}.{_reason(reason)}\n{config.SIGNATURE}")
    except Exception as e:
        await update.message.reply_text(f"❌ Couldn't ban: {e}")


@admin_only
async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name, _ = await resolve_target(update, context)
    if not uid:
        await update.message.reply_html("Reply to a user or pass <code>@user / id</code> to unban.")
        return
    try:
        await context.bot.unban_chat_member(update.effective_chat.id, uid, only_if_banned=True)
        await update.message.reply_html(f"✅ Unbanned {mention(uid, name)}.")
    except Exception as e:
        await update.message.reply_text(f"❌ Couldn't unban: {e}")


@admin_only
async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name, reason = await resolve_target(update, context)
    if not uid:
        await update.message.reply_html("Reply to a user or pass <code>@user / id</code> to kick.")
        return
    if await is_admin(context, update.effective_chat.id, uid):
        await update.message.reply_text("😅 I won't kick an admin.")
        return
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, uid)
        await context.bot.unban_chat_member(update.effective_chat.id, uid, only_if_banned=True)
        await update.message.reply_html(f"👢 Kicked {mention(uid, name)}.{_reason(reason)}")
    except Exception as e:
        await update.message.reply_text(f"❌ Couldn't kick: {e}")


# ============ MUTE / UNMUTE ============
@admin_only
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name, rest = await resolve_target(update, context)
    if not uid:
        await update.message.reply_html(
            "Reply to a user or pass <code>@user / id</code>.\n"
            "Optional duration: <code>/mute @user 10m spamming</code> (s/m/h/d)."
        )
        return
    if await is_admin(context, update.effective_chat.id, uid):
        await update.message.reply_text("😅 I won't mute an admin.")
        return

    seconds, reason = None, rest
    if rest:
        first, *tail = rest.split(maxsplit=1)
        secs = parse_duration(first)
        if secs:
            seconds, reason = secs, (tail[0] if tail else None)

    until = datetime.now(timezone.utc) + timedelta(seconds=seconds) if seconds else None
    try:
        await context.bot.restrict_chat_member(update.effective_chat.id, uid, MUTED, until_date=until)
        dur = f" for <b>{rest.split()[0]}</b>" if seconds else ""
        await update.message.reply_html(f"🔇 Muted {mention(uid, name)}{dur}.{_reason(reason)}")
    except Exception as e:
        await update.message.reply_text(f"❌ Couldn't mute: {e}")


@admin_only
async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name, _ = await resolve_target(update, context)
    if not uid:
        await update.message.reply_html("Reply to a user or pass <code>@user / id</code> to unmute.")
        return
    try:
        await context.bot.restrict_chat_member(update.effective_chat.id, uid, UNMUTED)
        await update.message.reply_html(f"🔊 Unmuted {mention(uid, name)}.")
    except Exception as e:
        await update.message.reply_text(f"❌ Couldn't unmute: {e}")


# ============ WARN SYSTEM ============
@admin_only
async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name, reason = await resolve_target(update, context)
    if not uid:
        await update.message.reply_html("Reply to a user or pass <code>@user / id</code> to warn.")
        return
    if await is_admin(context, update.effective_chat.id, uid):
        await update.message.reply_text("😅 Admins can't be warned.")
        return
    count = db.add_warn(update.effective_chat.id, uid)
    if count >= config.WARN_LIMIT:
        try:
            await context.bot.ban_chat_member(update.effective_chat.id, uid)
        except Exception:
            pass
        db.reset_warns(update.effective_chat.id, uid)
        await update.message.reply_html(
            f"🔨 {mention(uid, name)} reached <b>{config.WARN_LIMIT} warns</b> and was banned.{_reason(reason)}"
        )
    else:
        await update.message.reply_html(
            f"⚠️ Warned {mention(uid, name)} — <b>{count}/{config.WARN_LIMIT}</b>.{_reason(reason)}"
        )


@admin_only
async def warns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name, _ = await resolve_target(update, context)
    if not uid:
        uid, name = update.effective_user.id, update.effective_user.first_name
    count = db.get_warns(update.effective_chat.id, uid)
    await update.message.reply_html(f"⚠️ {mention(uid, name)} has <b>{count}/{config.WARN_LIMIT}</b> warns.")


@admin_only
async def resetwarns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name, _ = await resolve_target(update, context)
    if not uid:
        await update.message.reply_html("Reply to a user or pass <code>@user / id</code>.")
        return
    db.reset_warns(update.effective_chat.id, uid)
    await update.message.reply_html(f"✅ Cleared warns for {mention(uid, name)}.")


# ============ MESSAGE TOOLS ============
@admin_only
async def pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to the message you want to pin.")
        return
    await context.bot.pin_chat_message(
        update.effective_chat.id, update.message.reply_to_message.message_id, disable_notification=False
    )


@admin_only
async def unpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.unpin_chat_message(update.effective_chat.id)
    await update.message.reply_text("📌 Unpinned the latest pinned message.")


@admin_only
async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to a message to delete it.")
        return
    try:
        await context.bot.delete_message(update.effective_chat.id, update.message.reply_to_message.message_id)
        await context.bot.delete_message(update.effective_chat.id, update.message.message_id)
    except Exception:
        pass


async def _delete_later(context: ContextTypes.DEFAULT_TYPE):
    chat_id, message_id = context.job.data
    try:
        await context.bot.delete_message(chat_id, message_id)
    except Exception:
        pass


@admin_only
async def purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to the message to purge from (deletes up to here).")
        return
    chat_id = update.effective_chat.id
    start = update.message.reply_to_message.message_id
    end = update.message.message_id
    deleted = 0
    for mid in range(start, end + 1):
        try:
            await context.bot.delete_message(chat_id, mid)
            deleted += 1
        except Exception:
            pass
    note = await context.bot.send_message(chat_id, f"🧹 Purged {deleted} messages.")
    context.job_queue.run_once(_delete_later, 3, data=(chat_id, note.message_id))


# ============ ANTI-LINK / ANTI-FLOOD toggles ============
@admin_only
async def antilink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    arg = (context.args[0].lower() if context.args else "")
    if arg not in ("on", "off"):
        cur = db.get_setting(update.effective_chat.id, "antilink", "off")
        await update.message.reply_html(f"Anti-link is <b>{cur}</b>. Use <code>/antilink on|off</code>.")
        return
    db.set_setting(update.effective_chat.id, "antilink", arg)
    await update.message.reply_html(f"🔗 Anti-link turned <b>{arg}</b>.")


@admin_only
async def antiflood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    arg = (context.args[0].lower() if context.args else "")
    if arg not in ("on", "off"):
        cur = db.get_setting(update.effective_chat.id, "antiflood", "off")
        await update.message.reply_html(f"Anti-flood is <b>{cur}</b>. Use <code>/antiflood on|off</code>.")
        return
    db.set_setting(update.effective_chat.id, "antiflood", arg)
    await update.message.reply_html(f"🌊 Anti-flood turned <b>{arg}</b> (mutes anyone sending 6+ msgs / 5s).")


# ============ The moderation watcher (runs before everything) ============
_LINK_RE = filters.Regex(r"(https?://|www\.|t\.me/|telegram\.me/|\.com|\.net|\.org|\.in|\.io)")
_flood = defaultdict(lambda: deque(maxlen=6))  # (chat,user) -> recent timestamps
_BADWORDS = {"badword1", "badword2"}  # edit this set to your liking


async def moderation_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not user or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    # Never moderate admins
    if await is_admin(context, chat.id, user.id):
        return

    text = (msg.text or msg.caption or "").lower()

    # Bad words
    if text and any(w in text.split() for w in _BADWORDS):
        try:
            await msg.delete()
            await context.bot.send_message(chat.id, f"🚫 Removed a message from {mention(user.id, user.first_name)}.\n📋 <b>Reason:</b> banned word.", parse_mode="HTML")
        except Exception:
            pass
        return

    # Anti-link
    if db.get_setting(chat.id, "antilink", "off") == "on" and text:
        if any(t in text for t in ("http://", "https://", "www.", "t.me/", ".com", ".net", ".org", ".io", ".in")):
            try:
                await msg.delete()
                await context.bot.send_message(chat.id, f"🔗 Deleted a link from {mention(user.id, user.first_name)}.\n📋 <b>Reason:</b> anti-link is on.", parse_mode="HTML")
            except Exception:
                pass
            return

    # Anti-flood
    if db.get_setting(chat.id, "antiflood", "off") == "on":
        key = (chat.id, user.id)
        now = time.time()
        dq = _flood[key]
        dq.append(now)
        if len(dq) == dq.maxlen and (now - dq[0]) < 5:
            try:
                await context.bot.restrict_chat_member(
                    chat.id, user.id, MUTED,
                    until_date=datetime.now(timezone.utc) + timedelta(minutes=10),
                )
                await context.bot.send_message(chat.id, f"🌊 Muted {mention(user.id, user.first_name)} for 10m.\n📋 <b>Reason:</b> flooding the chat.", parse_mode="HTML")
                dq.clear()
            except Exception:
                pass


def register(app: Application):
    cmds = {
        "ban": ban, "unban": unban, "kick": kick,
        "mute": mute, "unmute": unmute,
        "warn": warn, "warns": warns, "resetwarns": resetwarns,
        "pin": pin, "unpin": unpin, "del": delete, "purge": purge,
        "antilink": antilink, "antiflood": antiflood,
    }
    for name, fn in cmds.items():
        app.add_handler(CommandHandler(name, fn))
    # Moderation runs in an early group so it can act before other listeners.
    app.add_handler(
        MessageHandler((filters.TEXT | filters.CAPTION) & ~filters.COMMAND, moderation_watch),
        group=-1,
    )
