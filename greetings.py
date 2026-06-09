"""Greetings & social: welcome / goodbye, birthday tag-wishes, and
friendly auto-replies to hellos."""
import random
import re

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import config
import db
from utils import mention, admin_only, group_only

DEFAULT_WELCOME = "👋 Welcome {name} to <b>{group}</b>!\nEnjoy your stay 🎉"
DEFAULT_GOODBYE = "👋 {name} just left {group}. Take care!"

GREETING_RE = re.compile(
    r"^\s*(hi+|hey+|hello+|yo|hola|namaste|good\s*morning|good\s*night|"
    r"good\s*evening|good\s*afternoon|gm|gn)\b[\s!.]*$",
    re.IGNORECASE,
)
GREET_REPLIES = [
    "Hey {name}! 👋",
    "Hello {name}! 😄 How's it going?",
    "Hi there {name}! ✨",
    "Yo {name}! 🙌",
    "Welcome back {name}! 🌟",
]

BIRTHDAY_RE = re.compile(r"happy\s*(birthday|bday|b'day)", re.IGNORECASE)
BIRTHDAY_WISHES = [
    "🎂 <b>Happy Birthday</b> {who}! 🎉🥳 Wishing you a fantastic year ahead!",
    "🥳 Heyyy {who}, <b>Happy Birthday</b>! 🎈 May all your wishes come true! 🎁",
    "🎉 {who}, have the best <b>Birthday</b> ever! 🍰✨",
]


# ---------- new / left members ----------
async def on_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    db.track_chat(chat.id)
    template = db.get_setting(chat.id, "welcome", DEFAULT_WELCOME)
    if template == "off":
        return
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            await update.message.reply_html(
                f"🙏 Thanks for adding me to <b>{chat.title}</b>!\n"
                f"Make me an <b>admin</b> so I can welcome members & keep things clean.\n"
                f"Type /help to see everything I can do. {config.SIGNATURE}"
            )
            continue
        text = template.replace("{name}", mention(member.id, member.first_name)).replace(
            "{group}", chat.title or "the group"
        )
        await update.message.reply_html(text)


async def on_left_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    left = update.message.left_chat_member
    if not left or left.id == context.bot.id:
        return
    template = db.get_setting(chat.id, "goodbye", DEFAULT_GOODBYE)
    if template == "off":
        return
    text = template.replace("{name}", left.first_name).replace("{group}", chat.title or "the group")
    await update.message.reply_html(text)


# ---------- settings ----------
@admin_only
async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_html(
            "Usage: <code>/setwelcome your text</code>\n"
            "Placeholders: <code>{name}</code>, <code>{group}</code>\n"
            "Use <code>/setwelcome off</code> to disable."
        )
        return
    db.set_setting(update.effective_chat.id, "welcome", " ".join(context.args))
    await update.message.reply_text("✅ Welcome message updated.")


@admin_only
async def set_goodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_html(
            "Usage: <code>/setgoodbye your text</code>\n"
            "Placeholders: <code>{name}</code>, <code>{group}</code>\n"
            "Use <code>/setgoodbye off</code> to disable."
        )
        return
    db.set_setting(update.effective_chat.id, "goodbye", " ".join(context.args))
    await update.message.reply_text("✅ Goodbye message updated.")


# ---------- birthday + greeting listener ----------
async def _birthday_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    # Replying to someone -> wish them
    if msg.reply_to_message and msg.reply_to_message.from_user:
        u = msg.reply_to_message.from_user
        return mention(u.id, u.first_name)
    # text-mention entity
    for ent in (msg.entities or []):
        if ent.type == "text_mention" and ent.user:
            return mention(ent.user.id, ent.user.first_name)
    # @username mention
    for ent in (msg.entities or []):
        if ent.type == "mention":
            uname = msg.text[ent.offset: ent.offset + ent.length]
            try:
                chat = await context.bot.get_chat(uname)
                return mention(chat.id, chat.full_name or uname)
            except Exception:
                return uname
    return None


async def social_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return
    if update.effective_user:
        db.track_user(update.effective_user.id)

    # Birthday magic: "happy birthday @someone"
    if BIRTHDAY_RE.search(msg.text):
        who = await _birthday_target(update, context)
        if who:
            await msg.reply_html(random.choice(BIRTHDAY_WISHES).format(who=who))
            return

    # Friendly greeting auto-reply
    if GREETING_RE.match(msg.text):
        name = update.effective_user.first_name if update.effective_user else "there"
        await msg.reply_text(random.choice(GREET_REPLIES).format(name=name))


def register(app: Application):
    app.add_handler(CommandHandler("setwelcome", set_welcome))
    app.add_handler(CommandHandler("setgoodbye", set_goodbye))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_members))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, on_left_member))
    # Social listener lives in its own group so it never blocks commands.
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, social_listener), group=1
    )
