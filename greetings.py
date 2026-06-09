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

DEFAULT_WELCOME = (
    "👋 <b>Welcome</b> {name}! 🎉\n"
    "Aapka <b>{group}</b> mein dil se swagat hai! 🙏\n"
    "Rules padh lena aur masti karo — enjoy your stay! ✨"
)
DEFAULT_GOODBYE = "👋 {name} ne {group} chhod diya. Take care, phir milenge! 🙏"

GREETING_RE = re.compile(
    r"^\s*(hi+|hey+|hello+|yo|hola|namaste|namaskar|ram\s*ram)\b[\s!.]*$",
    re.IGNORECASE,
)
GREET_REPLIES = [
    "Arre {name} ji! 👋 Kaise ho?",
    "Hello {name}! 😄 Kya haal chaal?",
    "Namaste {name}! 🙏✨",
    "Oye {name}! 🙌 Swagat hai!",
    "Hey {name}! 🌟 Kaisa chal raha hai sab?",
    "Ram Ram {name} ji! 😄",
]

# Context-aware Hinglish auto-replies for specific phrases.
GOOD_MORNING_RE = re.compile(r"^\s*(good\s*morning|gud\s*morning|gm|subah\s*bakhair)\b[\s!.]*$", re.IGNORECASE)
GOOD_NIGHT_RE = re.compile(r"^\s*(good\s*night|gud\s*night|gn|shubh\s*ratri)\b[\s!.]*$", re.IGNORECASE)
THANKS_RE = re.compile(r"^\s*(thanks?|thank\s*you|thx|shukriya|dhanyawad|ty)\b[\s!.]*$", re.IGNORECASE)

GM_REPLIES = [
    "🌅 Good Morning {name} ji! Aaj ka din shaandaar ho! ☕",
    "☀️ Subah bakhair {name}! Chai ho gayi kya? 😄",
    "🌞 Good Morning {name}! Aaj kuch badhiya kaam karte hain! 💪",
]
GN_REPLIES = [
    "🌙 Good Night {name} ji! Meethe sapne aayein! 😴",
    "✨ Shubh Ratri {name}! Aaram se so jao. 🛌",
    "🌌 Good Night {name}! Kal phir milte hain! 💫",
]
THANKS_REPLIES = [
    "Arre koi baat nahi {name}! 😊",
    "Welcome {name} ji! Khush raho! 🙌",
    "No mention {name}! Hum hain na! 💪",
]

BIRTHDAY_RE = re.compile(
    r"happy\s*(birthday|bday|b'day)|janamdin\s*mubarak|janmdin\s*mubarak", re.IGNORECASE
)
BIRTHDAY_WISHES = [
    "🎂 <b>Happy Birthday</b> {who}! 🎉🥳 Aapko janamdin ki dher saari shubhkamnaayein! Khush raho, masti karo! 🎈",
    "🥳 Arre wah {who}, <b>Happy Birthday</b>! 🎈 Aaj toh poora din aapka hai — cake kaato, party karo! 🎁🍰",
    "🎉 {who} ko <b>Janamdin Mubarak ho</b>! 🎂 God bless you, khoob taraqqi karo aur hamesha muskuraate raho! ✨",
    "🎊 Happy Birthday {who}! 🎂 Naya saal aapki life mein khushiyan, success aur dher saara pyaar laaye! ❤️🥳",
]


# ---------- profile photo helper ----------
async def _get_profile_photo(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Return the file_id of the user's current profile photo, or None.
    Works only if the user hasn't hidden photos in their privacy settings."""
    try:
        photos = await context.bot.get_user_profile_photos(user_id, limit=1)
        if photos.total_count and photos.photos:
            return photos.photos[0][-1].file_id  # highest resolution
    except Exception:
        pass
    return None


# ---------- new / left members ----------
async def on_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    db.track_chat(chat.id, chat.title)
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
        # Try to greet with their profile photo for a premium feel 📸
        photo = await _get_profile_photo(context, member.id)
        if photo:
            try:
                await context.bot.send_photo(chat.id, photo, caption=text, parse_mode="HTML")
                continue
            except Exception:
                pass  # fall back to text if the photo send fails
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
    """Return (mention_html, user_id) of the person being wished, or (None, None)."""
    msg = update.effective_message
    # Replying to someone -> wish them
    if msg.reply_to_message and msg.reply_to_message.from_user:
        u = msg.reply_to_message.from_user
        return mention(u.id, u.first_name), u.id
    # text-mention entity
    for ent in (msg.entities or []):
        if ent.type == "text_mention" and ent.user:
            return mention(ent.user.id, ent.user.first_name), ent.user.id
    # @username mention
    for ent in (msg.entities or []):
        if ent.type == "mention":
            uname = msg.text[ent.offset: ent.offset + ent.length]
            try:
                chat = await context.bot.get_chat(uname)
                return mention(chat.id, chat.full_name or uname), chat.id
            except Exception:
                return uname, None
    return None, None


async def social_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return
    if update.effective_user:
        u = update.effective_user
        db.track_user(u.id, u.full_name, u.username)
        if update.effective_chat.type in ("group", "supergroup"):
            db.track_chat(update.effective_chat.id, update.effective_chat.title)

    # Birthday magic: "happy birthday @someone" — wish them with their photo 🎂📸
    if BIRTHDAY_RE.search(msg.text):
        who, who_id = await _birthday_target(update, context)
        if who:
            wish = random.choice(BIRTHDAY_WISHES).format(who=who)
            photo = await _get_profile_photo(context, who_id) if who_id else None
            if photo:
                try:
                    await context.bot.send_photo(
                        update.effective_chat.id, photo, caption=wish, parse_mode="HTML"
                    )
                    return
                except Exception:
                    pass
            await msg.reply_html(wish)
            return

    # Friendly Hinglish auto-replies (most specific first)
    name = update.effective_user.first_name if update.effective_user else "dost"
    if GOOD_MORNING_RE.match(msg.text):
        await msg.reply_text(random.choice(GM_REPLIES).format(name=name))
    elif GOOD_NIGHT_RE.match(msg.text):
        await msg.reply_text(random.choice(GN_REPLIES).format(name=name))
    elif THANKS_RE.match(msg.text):
        await msg.reply_text(random.choice(THANKS_REPLIES).format(name=name))
    elif GREETING_RE.match(msg.text):
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
