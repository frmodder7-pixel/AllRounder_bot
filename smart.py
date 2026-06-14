"""Smart group features: /ask, summaries, rules, FAQ, and optional AI moderation."""
import html
import re
import time
from difflib import SequenceMatcher

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import Application, ApplicationHandlerStop, CommandHandler, MessageHandler, ContextTypes, filters

import ai
import config
import db
from utils import admin_only, is_admin

_TEXT_LIMIT = 3500
_FAQ_COOLDOWN = {}
_AIMOD_COOLDOWN = {}
_TOXIC_WORDS = {
    "kill yourself", "kys", "scam link", "free crypto", "send otp", "otp code",
    "password de", "password bhej", "card number", "cvv",
}


def _group_chat(chat) -> bool:
    return chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _setting(chat_id: int, key: str, default: str = "off") -> str:
    return (db.get_setting(chat_id, key, default) or default).lower()


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}


def _faq_score(question: str, text: str) -> float:
    q = _tokens(question)
    t = _tokens(text)
    if not q or not t:
        return 0.0
    overlap = len(q & t) / max(len(q), 1)
    ratio = SequenceMatcher(None, question.lower(), text.lower()).ratio()
    return max(overlap, ratio * 0.75)


def _level(total: int) -> tuple[int, int]:
    level = 1
    needed = 100
    remaining = total
    while remaining >= needed:
        remaining -= needed
        level += 1
        needed += 50
    return level, needed - remaining


async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ai.is_enabled():
        await update.message.reply_text("🧠 AI is disabled. Ask the owner to set GEMINI_API_KEY.")
        return
    question = _clean(" ".join(context.args))
    if not question and update.message.reply_to_message:
        question = _clean(update.message.reply_to_message.text or update.message.reply_to_message.caption or "")
    if not question:
        await update.message.reply_text("Usage: /ask your question")
        return
    chat_key = f"ask:{update.effective_chat.id}"
    user_key = f"ask:{update.effective_chat.id}:{update.effective_user.id}"
    if not ai.allow_request(chat_key, 12, 60) or not ai.allow_request(user_key, 4, 60):
        await update.message.reply_text("⏳ AI limit reached for a moment. Try again shortly.")
        return
    await context.bot.send_chat_action(update.effective_chat.id, "typing")
    prompt = (
        "You are All Rounder Bot by BLITEX. Answer clearly in friendly Hinglish unless the "
        "user asks for another language. Keep it useful, brief, and safe.\n\n"
        f"Question: {question[:2500]}"
    )
    answer = await ai.ask(prompt, max_tokens=500, temperature=0.7)
    await update.message.reply_text(answer or "🤖 AI did not answer right now. Try again in a moment.")


async def ai_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _group_chat(update.effective_chat):
        await update.message.reply_text("Use this inside a group.")
        return
    if not context.args:
        state = _setting(update.effective_chat.id, "ai_mode", "mentions")
        mod = _setting(update.effective_chat.id, "ai_moderation", "off")
        faq = _setting(update.effective_chat.id, "faq_auto", "on")
        await update.message.reply_html(
            f"🧠 <b>AI settings</b>\n"
            f"Replies: <code>{state}</code>\n"
            f"AI moderation: <code>{mod}</code>\n"
            f"FAQ auto-answer: <code>{faq}</code>\n\n"
            "Admins: <code>/ai on</code>, <code>/ai mentions</code>, <code>/ai privateonly</code>, <code>/ai off</code>"
        )
        return
    if not await is_admin(context, update.effective_chat.id, update.effective_user.id):
        await update.message.reply_text("⛔ Only group admins can change AI settings.")
        return
    mode = context.args[0].lower()
    if mode not in ("on", "mentions", "privateonly", "off"):
        await update.message.reply_text("Use: /ai on | mentions | privateonly | off")
        return
    db.set_setting(update.effective_chat.id, "ai_mode", mode)
    await update.message.reply_html(f"🧠 AI replies set to <code>{mode}</code>.")


@admin_only
async def ai_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or context.args[0].lower() not in ("on", "off"):
        cur = _setting(update.effective_chat.id, "ai_moderation", "off")
        await update.message.reply_html(f"AI moderation is <code>{cur}</code>. Use <code>/aimod on</code> or <code>/aimod off</code>.")
        return
    mode = context.args[0].lower()
    db.set_setting(update.effective_chat.id, "ai_moderation", mode)
    await update.message.reply_html(
        f"🛡️ AI moderation turned <code>{mode}</code>.\n"
        "It is conservative and only acts on likely abuse/scams."
    )


@admin_only
async def set_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = _clean(" ".join(context.args))
    if not text:
        await update.message.reply_html("Usage: <code>/setrules no spam | respect everyone | no links</code>")
        return
    db.set_setting(update.effective_chat.id, "rules", text)
    await update.message.reply_text("✅ Group rules saved.")


async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = db.get_setting(update.effective_chat.id, "rules")
    if not text:
        await update.message.reply_text("📜 No rules saved yet. Admins can use /setrules.")
        return
    parts = [p.strip() for p in re.split(r"\s*\|\s*|\n+", text) if p.strip()]
    if len(parts) > 1:
        body = "\n".join(f"{i}. {html.escape(part)}" for i, part in enumerate(parts, 1))
    else:
        body = html.escape(text)
    await update.message.reply_html(f"📜 <b>Group Rules</b>\n\n{body}\n\n{config.SIGNATURE}")


@admin_only
async def faq_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = _clean(" ".join(context.args))
    if not raw or "|" not in raw:
        await update.message.reply_html(
            "Usage: <code>/faqadd fees What are fees? | Fees are 500 per month.</code>"
        )
        return
    first, answer = [p.strip() for p in raw.split("|", 1)]
    bits = first.split(maxsplit=1)
    if len(bits) < 2:
        await update.message.reply_text("Give a short FAQ name and a question.")
        return
    name, question = bits
    db.save_faq(update.effective_chat.id, name, question, answer)
    await update.message.reply_html(f"✅ FAQ <code>{html.escape(name.lower())}</code> saved.")


async def faq_get(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        rows = db.list_faqs(update.effective_chat.id)
        if not rows:
            await update.message.reply_text("📭 No FAQs saved. Admins can use /faqadd.")
            return
        await update.message.reply_html(
            "📚 <b>FAQs</b>\n" + "\n".join(f"• <code>{html.escape(r['name'])}</code> — {html.escape(r['question'])}" for r in rows[:30])
        )
        return
    row = db.get_faq(update.effective_chat.id, context.args[0])
    if not row:
        await update.message.reply_text("No FAQ with that name.")
        return
    await update.message.reply_html(f"📚 <b>{html.escape(row['question'])}</b>\n\n{html.escape(row['answer'])}")


@admin_only
async def faq_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /faqdel fees")
        return
    db.del_faq(update.effective_chat.id, context.args[0])
    await update.message.reply_text("🗑️ FAQ deleted if it existed.")


@admin_only
async def faq_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or context.args[0].lower() not in ("on", "off"):
        cur = _setting(update.effective_chat.id, "faq_auto", "on")
        await update.message.reply_html(f"FAQ auto-answer is <code>{cur}</code>. Use <code>/faqauto on</code> or <code>/faqauto off</code>.")
        return
    db.set_setting(update.effective_chat.id, "faq_auto", context.args[0].lower())
    await update.message.reply_html(f"📚 FAQ auto-answer set to <code>{context.args[0].lower()}</code>.")


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _group_chat(update.effective_chat):
        await update.message.reply_text("Use /summary inside a group.")
        return
    if not ai.is_enabled():
        await update.message.reply_text("🧠 AI is disabled. Summary needs GEMINI_API_KEY.")
        return
    if not ai.allow_request(f"summary:{update.effective_chat.id}", 3, 300):
        await update.message.reply_text("⏳ Summary limit reached. Try again later.")
        return
    rows = list(reversed(db.recent_messages(update.effective_chat.id, 60)))
    if len(rows) < 3:
        await update.message.reply_text("Not enough recent messages to summarize yet.")
        return
    transcript = "\n".join(f"{r['name']}: {r['text']}" for r in rows)[-_TEXT_LIMIT:]
    await context.bot.send_chat_action(update.effective_chat.id, "typing")
    prompt = (
        "Summarize this Telegram group chat in friendly Hinglish. Give 3-6 bullets, mention "
        "decisions/questions if any, and do not invent facts.\n\n"
        f"{transcript}"
    )
    answer = await ai.ask(prompt, max_tokens=350, temperature=0.4)
    await update.message.reply_text(answer or "Couldn't summarize right now.")


async def smart_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not user or user.is_bot or not _group_chat(chat):
        return
    if context.chat_data.get(f"smart_deleted:{msg.message_id}"):
        return
    text = _clean(msg.text or msg.caption or "")
    if not text:
        return
    db.add_recent_message(chat.id, msg.message_id, user.id, user.first_name, text, int(time.time()))

    if _setting(chat.id, "faq_auto", "on") == "on":
        await _maybe_answer_faq(update)


async def smart_moderation_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not user or user.is_bot or not _group_chat(chat):
        return
    text = _clean(msg.text or msg.caption or "")
    if not text:
        return
    if _setting(chat.id, "ai_moderation", "off") == "on":
        deleted = await _maybe_ai_moderate(update, context, text)
        if deleted:
            context.chat_data[f"smart_deleted:{msg.message_id}"] = True
            raise ApplicationHandlerStop


async def _maybe_answer_faq(update: Update):
    text = update.effective_message.text or ""
    if len(text) < 8 or not ("?" in text or any(w in text.lower() for w in ("what", "how", "when", "where", "fees", "price", "rule", "kaise", "kab", "kya"))):
        return
    chat_id = update.effective_chat.id
    now = time.monotonic()
    if now - _FAQ_COOLDOWN.get(chat_id, 0) < 45:
        return
    rows = db.list_faqs(chat_id)
    best = None
    best_score = 0.0
    for row in rows:
        score = _faq_score(row["question"], text)
        if score > best_score:
            best = row
            best_score = score
    if best and best_score >= 0.62:
        _FAQ_COOLDOWN[chat_id] = now
        await update.effective_message.reply_html(
            f"📚 <b>{html.escape(best['question'])}</b>\n\n{html.escape(best['answer'])}"
        )


async def _maybe_ai_moderate(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    chat = update.effective_chat
    user = update.effective_user
    if await is_admin(context, chat.id, user.id):
        return False
    lowered = text.lower()
    obvious = any(word in lowered for word in _TOXIC_WORDS)
    if not obvious:
        if not ai.is_enabled() or not ai.allow_request(f"aimod:{chat.id}", 8, 60):
            return False
        prompt = (
            "Classify this Telegram group message. Reply only SAFE or UNSAFE. "
            "UNSAFE means clear abuse, self-harm encouragement, scam, OTP/password theft, or explicit spam. "
            f"Message: {text[:800]}"
        )
        verdict = await ai.ask(prompt, max_tokens=8, temperature=0.0)
        obvious = bool(verdict and "UNSAFE" in verdict.upper())
    if not obvious:
        return False
    key = (chat.id, user.id)
    now = time.monotonic()
    if now - _AIMOD_COOLDOWN.get(key, 0) < 30:
        return False
    _AIMOD_COOLDOWN[key] = now
    try:
        await update.effective_message.delete()
        await context.bot.send_message(
            chat.id,
            f"🛡️ Removed a likely unsafe message from {html.escape(user.first_name)}.\n"
            "Reason: AI moderation is on.",
            parse_mode="HTML",
        )
        return True
    except Exception:
        return False


def register(app: Application):
    app.add_handler(CommandHandler("ask", ask_cmd))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("ai", ai_settings))
    app.add_handler(CommandHandler("aimod", ai_moderation))
    app.add_handler(CommandHandler("setrules", set_rules))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("faqadd", faq_add))
    app.add_handler(CommandHandler("faq", faq_get))
    app.add_handler(CommandHandler("faqs", faq_get))
    app.add_handler(CommandHandler("faqdel", faq_del))
    app.add_handler(CommandHandler("faqauto", faq_auto))
    app.add_handler(MessageHandler((filters.TEXT | filters.CAPTION) & ~filters.COMMAND, smart_moderation_listener), group=0)
    app.add_handler(MessageHandler((filters.TEXT | filters.CAPTION) & ~filters.COMMAND, smart_listener), group=4)
