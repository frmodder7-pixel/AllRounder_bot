"""Owner-only admin dashboard, right inside Telegram.
Only the OWNER_ID set in the environment can open or use it. 🔒"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

import config
import db

PANEL_HOME = (
    "👑 <b>Admin Dashboard</b> — <i>by BLITEX</i>\n\n"
    "Welcome back, boss. Manage your bot from here.\n"
    "🔒 This panel is visible to <b>you only</b>."
)


def _is_owner(user_id: int) -> bool:
    return bool(config.OWNER_ID) and user_id == config.OWNER_ID


def _home_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Stats", callback_data="panel:stats"),
         InlineKeyboardButton("👤 Users", callback_data="panel:users")],
        [InlineKeyboardButton("👥 Groups", callback_data="panel:groups"),
         InlineKeyboardButton("📣 Broadcast", callback_data="panel:bc")],
        [InlineKeyboardButton("🧠 AI", callback_data="panel:ai"),
         InlineKeyboardButton("📚 Rules & FAQ", callback_data="panel:knowledge")],
        [InlineKeyboardButton("🛡️ Moderation", callback_data="panel:moderation")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="panel:home"),
         InlineKeyboardButton("❌ Close", callback_data="panel:close")],
    ])


def _back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="panel:home")]])


async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update.effective_user.id):
        await update.message.reply_text("⛔ This dashboard is for the bot owner only.")
        return
    await update.message.reply_html(PANEL_HOME, reply_markup=_home_kb())


async def panel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not _is_owner(q.from_user.id):
        await q.answer("Owner only. 🔒", show_alert=True)
        return
    await q.answer()
    action = q.data.split(":", 1)[1]

    if action == "close":
        await q.edit_message_text("✅ Dashboard closed. Send /admin to reopen.")
        return
    if action == "home":
        await q.edit_message_text(PANEL_HOME, parse_mode="HTML", reply_markup=_home_kb())
        return

    if action == "stats":
        users, groups = db.stats()
        text = (
            f"📊 <b>Overview</b>\n\n"
            f"👤 Total users: <b>{users}</b>\n"
            f"👥 Total groups: <b>{groups}</b>"
        )
    elif action == "users":
        rows = db.list_users(30)
        if rows:
            lines = []
            for r in rows:
                uname = f"@{r['username']}" if r["username"] else "—"
                lines.append(f"• <code>{r['user_id']}</code> {r['name'] or ''} ({uname})")
            text = "👤 <b>Recent users</b> (latest 30)\n\n" + "\n".join(lines)
        else:
            text = "👤 No users have started the bot yet."
    elif action == "groups":
        rows = db.list_chats(30)
        if rows:
            lines = [f"• <code>{r['chat_id']}</code> {r['title'] or '(private)'}" for r in rows]
            text = "👥 <b>Groups using the bot</b> (latest 30)\n\n" + "\n".join(lines)
        else:
            text = "👥 The bot isn't in any tracked groups yet."
    elif action == "bc":
        text = (
            "📣 <b>Broadcast</b>\n\n"
            "To send a message to <b>all users</b>:\n"
            "1. Write or forward the message\n"
            "2. <b>Reply</b> to it with <code>/broadcast</code>\n"
            "3. Confirm with <code>/broadcast confirm</code>\n\n"
            "The confirmation step helps avoid accidental mass messages."
        )
    elif action == "ai":
        text = (
            "🧠 <b>AI Controls</b>\n\n"
            "Group admins can use:\n"
            "• <code>/ai</code> — show AI settings\n"
            "• <code>/ai on</code> — allow active group AI\n"
            "• <code>/ai mentions</code> — reply only when mentioned/replied\n"
            "• <code>/ai privateonly</code> — group AI quiet, private chat works\n"
            "• <code>/ai off</code> — disable group AI\n"
            "• <code>/aimod on</code> — conservative AI moderation"
        )
    elif action == "knowledge":
        text = (
            "📚 <b>Rules & FAQ</b>\n\n"
            "Group admins can use:\n"
            "• <code>/setrules no spam | respect everyone</code>\n"
            "• <code>/rules</code>\n"
            "• <code>/faqadd fees What are fees? | Fees are 500/month.</code>\n"
            "• <code>/faq</code> or <code>/faq fees</code>\n"
            "• <code>/faqauto on</code> or <code>/faqauto off</code>\n\n"
            "FAQ auto-answer only replies from saved FAQs."
        )
    elif action == "moderation":
        text = (
            "🛡️ <b>Moderation</b>\n\n"
            "Use these in the group:\n"
            "• Reply + <code>/ban reason</code>\n"
            "• Reply + <code>/mute 10m reason</code>\n"
            "• Reply + <code>/warn reason</code>\n"
            "• <code>/warnlist</code>\n"
            "• <code>/antilink on</code> / <code>off</code>\n"
            "• <code>/antiflood on</code> / <code>off</code>\n"
            "• <code>/aimod on</code> / <code>off</code>"
        )
    else:
        text = PANEL_HOME

    await q.edit_message_text(text, parse_mode="HTML", reply_markup=_back_kb())


def register(app: Application):
    app.add_handler(CommandHandler("admin", panel))
    app.add_handler(CommandHandler("panel", panel))
    app.add_handler(CommandHandler("dashboard", panel))
    app.add_handler(CallbackQueryHandler(panel_cb, pattern=r"^panel:"))
