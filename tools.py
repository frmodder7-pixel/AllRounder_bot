"""Tools (v2): reminders, notes, calculator, dictionary, translate,
weather, time, id/info. Network calls degrade gracefully on failure."""
import ast
import asyncio
import operator
from datetime import datetime, timezone

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import config
import db
from utils import mention, parse_duration

_TIMEOUT = httpx.Timeout(10.0)

# ---------- safe calculator ----------
_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv, ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def _safe_eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp):
        return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        return _OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("unsupported expression")


async def calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /calc 2 + 2 * 5")
        return
    expr = " ".join(context.args)
    try:
        result = _safe_eval(ast.parse(expr, mode="eval").body)
        await update.message.reply_html(f"🧮 <code>{expr}</code> = <b>{result}</b>")
    except Exception:
        await update.message.reply_text("❌ That doesn't look like a valid math expression.")


# ---------- dictionary ----------
async def define(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /define serendipity")
        return
    word = context.args[0]
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}")
            r.raise_for_status()
            data = r.json()[0]
        out = [f"📖 <b>{data['word']}</b>"]
        for m in data["meanings"][:3]:
            defs = m["definitions"][0]["definition"]
            out.append(f"\n<i>{m['partOfSpeech']}</i>: {defs}")
        await update.message.reply_html("\n".join(out))
    except Exception:
        await update.message.reply_text(f"😅 No definition found for “{word}”.")


# ---------- translate ----------
async def translate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_html("Usage: <code>/tr en नमस्ते दुनिया</code>  (target-lang then text)")
        return
    lang = context.args[0]
    text = " ".join(context.args[1:])
    try:
        from deep_translator import GoogleTranslator
        out = await asyncio.to_thread(
            lambda: GoogleTranslator(source="auto", target=lang).translate(text)
        )
        await update.message.reply_html(f"🌐 <b>{lang}</b>: {out}")
    except Exception:
        await update.message.reply_text("😅 Couldn't translate that. Check the language code (e.g. en, hi, es).")


# ---------- weather (no API key, via wttr.in) ----------
async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /weather Mumbai")
        return
    city = " ".join(context.args)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.get(f"https://wttr.in/{city}?format=j1")
            r.raise_for_status()
            d = r.json()
        cur = d["current_condition"][0]
        area = d["nearest_area"][0]["areaName"][0]["value"]
        await update.message.reply_html(
            f"🌤️ <b>{area}</b>\n"
            f"🌡️ {cur['temp_C']}°C (feels {cur['FeelsLikeC']}°C)\n"
            f"☁️ {cur['weatherDesc'][0]['value']}\n"
            f"💧 Humidity {cur['humidity']}%   💨 Wind {cur['windspeedKmph']} km/h"
        )
    except Exception:
        await update.message.reply_text(f"😅 Couldn't get weather for “{city}”.")


# ---------- time ----------
async def time_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(timezone.utc)
    await update.message.reply_html(f"🕒 <b>UTC time:</b> {now:%Y-%m-%d %H:%M:%S}")


# ---------- reminders ----------
async def _fire_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    await context.bot.send_message(job.chat_id, f"⏰ <b>Reminder:</b> {job.data}", parse_mode="HTML")


async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_html("Usage: <code>/remind 10m drink water</code>  (s/m/h/d)")
        return
    seconds = parse_duration(context.args[0])
    if not seconds:
        await update.message.reply_text("⏱️ First give a duration like 30s, 10m, 2h, 1d.")
        return
    text = " ".join(context.args[1:])
    context.job_queue.run_once(_fire_reminder, seconds, chat_id=update.effective_chat.id, data=text)
    await update.message.reply_html(f"✅ Okay! I'll remind you in <b>{context.args[0]}</b>.")


# ---------- notes (save & recall) ----------
async def save_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_html("Usage: <code>/save rules No spam, be kind.</code> (or reply to a message)")
        return
    name = context.args[0]
    if update.message.reply_to_message and update.message.reply_to_message.text:
        content = update.message.reply_to_message.text
    elif len(context.args) > 1:
        content = " ".join(context.args[1:])
    else:
        await update.message.reply_text("Add some text, or reply to a message to save it.")
        return
    db.save_note(update.effective_chat.id, name, content)
    await update.message.reply_html(f"✅ Saved note <code>{name}</code>. Get it with <code>/get {name}</code>.")


async def get_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /get rules")
        return
    content = db.get_note(update.effective_chat.id, context.args[0])
    await update.message.reply_text(content if content else "🤷 No note with that name.")


async def list_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    names = db.list_notes(update.effective_chat.id)
    if not names:
        await update.message.reply_text("📭 No notes saved yet. Use /save <name> <text>.")
        return
    await update.message.reply_html("📒 <b>Saved notes:</b>\n" + "\n".join(f"• <code>{n}</code>" for n in names))


async def clear_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /clear rules")
        return
    db.del_note(update.effective_chat.id, context.args[0])
    await update.message.reply_text("🗑️ Deleted (if it existed).")


# ---------- id / info ----------
async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    c = update.effective_chat
    text = f"🆔 <b>Your ID:</b> <code>{u.id}</code>\n💬 <b>Chat ID:</b> <code>{c.id}</code>"
    if update.message.reply_to_message:
        ru = update.message.reply_to_message.from_user
        text += f"\n↩️ <b>Their ID:</b> <code>{ru.id}</code>"
    await update.message.reply_html(text)


async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = (update.message.reply_to_message.from_user
         if update.message.reply_to_message else update.effective_user)
    text = (
        f"👤 <b>User info</b>\n"
        f"Name: {mention(u.id, u.full_name)}\n"
        f"ID: <code>{u.id}</code>\n"
        f"Username: {('@' + u.username) if u.username else '—'}\n"
        f"Is bot: {'yes' if u.is_bot else 'no'}"
    )
    await update.message.reply_html(text)


def register(app: Application):
    app.add_handler(CommandHandler("calc", calc))
    app.add_handler(CommandHandler("define", define))
    app.add_handler(CommandHandler("tr", translate))
    app.add_handler(CommandHandler("translate", translate))
    app.add_handler(CommandHandler("weather", weather))
    app.add_handler(CommandHandler("time", time_cmd))
    app.add_handler(CommandHandler("remind", remind))
    app.add_handler(CommandHandler("save", save_note))
    app.add_handler(CommandHandler("get", get_note))
    app.add_handler(CommandHandler("notes", list_notes))
    app.add_handler(CommandHandler("clear", clear_note))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(CommandHandler("info", info))
