"""Start screen, premium inline /help menu, optional AI brain, and
owner-only tools (/stats, /broadcast)."""
import asyncio

import httpx
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
    "fun": ("🎮 Fun",
            "• <code>/joke /quote /fact /meme</code>\n"
            "• <code>/dice /dart /coin</code>\n"
            "• <code>/8ball question</code>\n"
            "• <code>/quiz</code> — trivia poll"),
    "tools": ("🛠️ Tools",
              "• <code>/remind 10m text</code>\n"
              "• <code>/save /get /notes /clear</code>\n"
              "• <code>/calc</code>, <code>/define</code>, <code>/tr en text</code>\n"
              "• <code>/weather city</code>, <code>/time</code>\n"
              "• <code>/id</code>, <code>/info</code>"),
    "ai": ("🧠 AI Brain",
           "Mention me or reply to my message and I'll answer intelligently.\n"
           f"<i>Status: {'✅ enabled' if config.GEMINI_API_KEY else '⚙️ owner can enable with a free key'}</i>"),
}


def _menu_keyboard():
    btns = [
        [InlineKeyboardButton("🎉 Greetings", callback_data="help:greet"),
         InlineKeyboardButton("🛡️ Admin", callback_data="help:admin")],
        [InlineKeyboardButton("🎮 Fun", callback_data="help:fun"),
         InlineKeyboardButton("🛠️ Tools", callback_data="help:tools")],
        [InlineKeyboardButton("🧠 AI Brain", callback_data="help:ai")],
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
    db.track_user(update.effective_user.id)
    if update.effective_chat.type != ChatType.PRIVATE:
        db.track_chat(update.effective_chat.id)
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


# ---------------- AI brain (optional) ----------------
async def _ask_gemini(prompt: str) -> str:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-1.5-flash:generateContent?key={config.GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 400, "temperature": 0.7},
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as c:
        r = await c.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


async def ai_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not config.GEMINI_API_KEY:
        return
    msg = update.effective_message
    if not msg or not msg.text:
        return
    me = context.bot.username
    mentioned = me and f"@{me}".lower() in msg.text.lower()
    replied_to_me = (msg.reply_to_message
                     and msg.reply_to_message.from_user
                     and msg.reply_to_message.from_user.id == context.bot.id)
    is_private = update.effective_chat.type == ChatType.PRIVATE
    if not (mentioned or replied_to_me or is_private):
        return

    question = msg.text.replace(f"@{me}", "").strip() if me else msg.text
    if not question:
        return
    await context.bot.send_chat_action(update.effective_chat.id, "typing")
    try:
        prompt = (
            "You are All Rounder Bot by BLITEX, a helpful, friendly Telegram assistant. "
            "Answer clearly and briefly. When giving advice or a decision, include a short reason. "
            f"User says: {question}"
        )
        answer = await _ask_gemini(prompt)
        await msg.reply_text(answer)
    except Exception:
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
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to the message you want to broadcast.")
        return
    src = update.message.reply_to_message
    sent = failed = 0
    for uid in db.all_user_ids():
        try:
            await context.bot.copy_message(uid, src.chat_id, src.message_id)
            sent += 1
            await asyncio.sleep(0.05)  # gentle rate-limit
        except Exception:
            failed += 1
    await update.message.reply_html(f"📣 Broadcast done.\n✅ Sent: <b>{sent}</b>\n❌ Failed: <b>{failed}</b>")


def register(app: Application):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(help_callback, pattern=r"^help:"))
    # AI runs in a late group so it never interferes with commands/moderation.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_listener), group=2)
