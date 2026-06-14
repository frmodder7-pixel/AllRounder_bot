"""Start screen, premium inline /help menu, optional AI brain, and
owner-only tools (/stats, /broadcast)."""
import asyncio
import html

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import ai
import config
import db

# ---------------- help content ----------------
HELP_PAGES = {
    "greet": ("🎉 Greetings & Social",
              "• Auto welcome / goodbye messages\n"
              "• <code>/setwelcome</code>, <code>/setgoodbye</code> (admins) — use {name}, {group}\n"
              "• 🎂 Tag someone with “happy birthday” → I wish them!\n"
              "• I reply to hi / hello / good morning automatically"),
    "admin": ("🛡️ Admin & Moderation",
              "• <code>/ban /unban /kick</code>\n"
              "• <code>/mute [10m] /unmute</code>\n"
              "• <code>/warn /warns /resetwarns</code> (auto-ban at limit)\n"
              "• <code>/pin /unpin /del /purge</code>\n"
              "• <code>/antilink on|off</code>, <code>/antiflood on|off</code>\n"
              "<i>Every action shows a reason.</i>"),
    "fun": ("🎮 Fun (Desi Style 🇮🇳)",
            "• <code>/joke</code> — Hinglish jokes (AI = unlimited!) 😂\n"
            "• <code>/shayari</code> — desi shayari 🌹\n"
            "• <code>/roast</code> — playful roast 🔥 (reply to target)\n"
            "• <code>/compliment</code> — sweet compliment 💖\n"
            "• <code>/cricket</code> — live scores 🏏\n"
            "• <code>/score team</code> — match by team 🔍\n"
            "• <code>/quote /fact /meme</code>\n"
            "• <code>/dice /dart /coin</code>\n"
            "• <code>/8ball question</code>\n"
            "• <code>/quiz</code> — trivia poll\n"
            "• <code>/truth /dare /riddle /guess</code>\n"
            "• <code>/wordchain /rapid /predict</code>\n"
            "<i>Plus auto festival wishes 🎊 (Diwali, Holi, Eid…)</i>"),
    "engage": ("🏆 Daily, Games & Ranks",
               "• <code>/leaderboard</code> (or /top) — all-time Top-10 🏆\n"
               "• <code>/today</code> — today's Top-5 🔥\n"
               "• <code>/rank</code>, <code>/profile</code> — points, level & rank 🎯\n"
               "• <code>/wallet</code>, <code>/shop</code>, <code>/buy</code>, <code>/give</code> — coins 🪙\n"
               "• <code>/daily</code> — daily bonus + streak 🎁🔥\n"
               "• <code>/wordgame</code> — scramble game, +15 pts 🎮\n\n"
               "<i>Every message = 1 point!</i>\n"
               "🌅 7:00 AM — Good Morning + Aaj ka Vichaar\n"
               "🌙 11:00 PM — Good Night\n"
               "🏆 10:00 PM — Today's Champions\n"
               "👑 Sunday 8:00 PM — Member of the Week (+50 pts)!"),
    "tools": ("🛠️ Tools",
              "• <code>/remind 10m text</code>\n"
              "• <code>/save /get /notes /clear</code>\n"
              "• <code>/calc</code>, <code>/define</code>, <code>/tr en text</code>\n"
              "• <code>/weather city</code>, <code>/time</code>\n"
              "• <code>/id</code>, <code>/info</code>"),
    "ai": ("🧠 AI Brain",
           "Mention me or reply to my message and I'll answer intelligently.\n"
           "• <code>/ask</code> — ask directly\n"
           "• <code>/summary</code> — summarize recent group chat\n"
           "• <code>/ai</code> — group AI settings\n"
           "• <code>/aimod on</code> — admin-only smart moderation\n"
           "• <code>/setrules</code>, <code>/rules</code>, <code>/faqadd</code>, <code>/faq</code>\n"
           f"<i>Status: {'✅ enabled' if config.GEMINI_API_KEY else '⚙️ owner can enable with a free key'}</i>"),
}


def _menu_keyboard():
    btns = [
        [InlineKeyboardButton("🎉 Greetings", callback_data="help:greet"),
         InlineKeyboardButton("🛡️ Admin", callback_data="help:admin")],
        [InlineKeyboardButton("🎮 Fun", callback_data="help:fun"),
         InlineKeyboardButton("🛠️ Tools", callback_data="help:tools")],
        [InlineKeyboardButton("🏆 Daily & Ranks", callback_data="help:engage"),
         InlineKeyboardButton("🧠 AI Brain", callback_data="help:ai")],
    ]
    return InlineKeyboardMarkup(btns)


def _back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="help:home")]])


HOME_TEXT = (
    f"✨ <b>{config.BRAND}</b> <i>{config.TAG}</i> ✨\n\n"
    "Your premium all-in-one group assistant — greetings, moderation, "
    "fun, tools and an AI brain. 🚀\n\n"
    "👉 Add me to your group and make me <b>admin</b>.\n"
    "Pick a category below to see commands:"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.track_user(u.id, u.full_name, u.username)
    if update.effective_chat.type != ChatType.PRIVATE:
        db.track_chat(update.effective_chat.id, update.effective_chat.title)
    me = await context.bot.get_me()
    add_url = f"https://t.me/{me.username}?startgroup=true"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add me to your group", url=add_url)],
        [InlineKeyboardButton("📖 Help & Commands", callback_data="help:home")],
    ])
    await update.message.reply_html(HOME_TEXT, reply_markup=kb)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(HOME_TEXT, reply_markup=_menu_keyboard())


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    page = q.data.split(":", 1)[1]
    if page == "home":
        await q.edit_message_text(HOME_TEXT, parse_mode="HTML", reply_markup=_menu_keyboard())
        return
    title, body = HELP_PAGES[page]
    await q.edit_message_text(f"<b>{title}</b>\n\n{body}\n\n{config.SIGNATURE}",
                              parse_mode="HTML", reply_markup=_back_keyboard())


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 Pong! I'm online and fast.")


async def ai_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_only(update):
        await update.message.reply_text("⛔ Owner only.")
        return
    model = html.escape(config.GEMINI_MODEL)
    if not ai.is_enabled():
        await update.message.reply_html(
            f"🧠 Gemini: <b>disabled</b>\n"
            f"Model: <code>{model}</code>\n"
            "Set <code>GEMINI_API_KEY</code> in Railway Variables or local <code>.env</code>."
        )
        return
    await context.bot.send_chat_action(update.effective_chat.id, "typing")
    answer = await ai.ask("Reply with exactly: Gemini OK", max_tokens=20, temperature=0.2)
    if answer:
        await update.message.reply_html(
            f"🧠 Gemini: <b>OK</b>\n"
            f"Model: <code>{html.escape(ai.active_model())}</code>\n"
            f"Test reply: <code>{html.escape(answer[:120])}</code>"
        )
        return
    error = html.escape(ai.last_error() or "unknown error")
    await update.message.reply_html(
        f"🧠 Gemini: <b>failing</b>\n"
        f"Model: <code>{model}</code>\n"
        f"Last error: <code>{error}</code>"
    )


# ---------------- AI brain (optional) ----------------
async def ai_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ai.is_enabled():
        return
    msg = update.effective_message
    if not msg or not msg.text:
        return
    is_private = update.effective_chat.type == ChatType.PRIVATE
    mode = db.get_setting(update.effective_chat.id, "ai_mode", "mentions") if not is_private else "on"
    if mode == "off" or (mode == "privateonly" and not is_private):
        return
    me = context.bot.username
    mentioned = me and f"@{me}".lower() in msg.text.lower()
    replied_to_me = (msg.reply_to_message
                     and msg.reply_to_message.from_user
                     and msg.reply_to_message.from_user.id == context.bot.id)
    if mode != "on" and not (mentioned or replied_to_me or is_private):
        return

    question = msg.text.replace(f"@{me}", "").strip() if me else msg.text
    if not question:
        return
    chat_key = f"listener:{update.effective_chat.id}"
    user_key = f"listener:{update.effective_chat.id}:{update.effective_user.id}"
    if not ai.allow_request(chat_key, 12, 60) or not ai.allow_request(user_key, 4, 60):
        await msg.reply_text("⏳ AI limit reached for a moment. Try again shortly.")
        return
    await context.bot.send_chat_action(update.effective_chat.id, "typing")
    prompt = (
        "You are All Rounder Bot by BLITEX, a helpful, friendly Telegram assistant for "
        "Indian users. Reply in a warm, casual Hinglish style (Hindi written in English "
        "letters, mixed with English) — like a friendly desi dost. Keep it clear and brief. "
        "When giving advice or a decision, include a short reason. "
        f"User says: {question}"
    )
    answer = await ai.ask(prompt)
    if answer:
        await msg.reply_text(answer)
    else:
        await msg.reply_text("🤖 My AI brain is busy right now — try again in a moment.")


# ---------------- owner tools ----------------
def _owner_only(update: Update) -> bool:
    return config.OWNER_ID and update.effective_user.id == config.OWNER_ID


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_only(update):
        await update.message.reply_text("⛔ Owner only.")
        return
    users, groups = db.stats()
    await update.message.reply_html(
        f"📊 <b>{config.BRAND} stats</b>\n👤 Users: <b>{users}</b>\n👥 Groups: <b>{groups}</b>"
    )


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_only(update):
        await update.message.reply_text("⛔ Owner only.")
        return
    if context.args and context.args[0].lower() == "confirm":
        pending = context.user_data.pop("broadcast_pending", None)
        if not pending:
            await update.message.reply_text("No pending broadcast. Reply to a message with /broadcast first.")
            return
        src_chat_id, src_message_id = pending
        sent = failed = 0
        for uid in db.all_user_ids():
            try:
                await context.bot.copy_message(uid, src_chat_id, src_message_id)
                sent += 1
                await asyncio.sleep(0.08)
            except Exception:
                failed += 1
        await update.message.reply_html(f"📣 Broadcast done.\n✅ Sent: <b>{sent}</b>\n❌ Failed: <b>{failed}</b>")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to the message you want to broadcast, then send /broadcast.")
        return
    src = update.message.reply_to_message
    context.user_data["broadcast_pending"] = (src.chat_id, src.message_id)
    count = len(db.all_user_ids())
    await update.message.reply_html(
        f"📣 Broadcast prepared for <b>{count}</b> users.\n"
        "Send <code>/broadcast confirm</code> to send it."
    )


def register(app: Application):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("aistatus", ai_status))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(help_callback, pattern=r"^help:"))
    # AI runs in a late group so it never interferes with commands/moderation.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_listener), group=2)
