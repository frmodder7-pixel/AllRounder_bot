"""Fun: jokes, quotes, facts, memes, dice, coin flip, magic 8-ball, quiz.
All network calls are wrapped so a failing API never breaks the bot."""
import random

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import config

_TIMEOUT = httpx.Timeout(10.0)

EIGHTBALL = [
    "It is certain. ✅", "Without a doubt. 💯", "Yes, definitely. 👍",
    "Most likely. 🙂", "Ask again later. ⏳", "Better not tell you now. 🤐",
    "Don't count on it. 🚫", "My reply is no. ❌", "Very doubtful. 😬",
]


async def _get_json(url):
    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
        r = await client.get(url, headers={"Accept": "application/json"})
        r.raise_for_status()
        return r.json()


async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        d = await _get_json("https://official-joke-api.appspot.com/random_joke")
        await update.message.reply_text(f"😂 {d['setup']}\n\n👉 {d['punchline']}")
    except Exception:
        await update.message.reply_text("😅 Couldn't fetch a joke right now. Try again!")


async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        d = await _get_json("https://api.quotable.io/random")
        await update.message.reply_html(f"💬 <i>{d['content']}</i>\n\n— <b>{d['author']}</b>")
    except Exception:
        await update.message.reply_text("😅 Couldn't fetch a quote right now. Try again!")


async def fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        d = await _get_json("https://uselessfacts.jsph.pl/api/v2/facts/random?language=en")
        await update.message.reply_text(f"🤓 Did you know?\n\n{d['text']}")
    except Exception:
        await update.message.reply_text("😅 Couldn't fetch a fact right now. Try again!")


async def meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        d = await _get_json("https://meme-api.com/gimme")
        await update.message.reply_photo(d["url"], caption=f"😆 {d.get('title', '')}")
    except Exception:
        await update.message.reply_text("😅 Couldn't fetch a meme right now. Try again!")


async def dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_dice(update.effective_chat.id, emoji="🎲")


async def dart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_dice(update.effective_chat.id, emoji="🎯")


async def coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🪙 {random.choice(['Heads!', 'Tails!'])}")


async def eightball(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("🎱 Ask me a yes/no question: /8ball will it rain today?")
        return
    await update.message.reply_text(f"🎱 {random.choice(EIGHTBALL)}")


async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Posts a real Telegram quiz poll."""
    try:
        d = await _get_json("https://opentdb.com/api.php?amount=1&type=multiple")
        q = d["results"][0]
        import html
        question = html.unescape(q["question"])
        correct = html.unescape(q["correct_answer"])
        options = [html.unescape(a) for a in q["incorrect_answers"]] + [correct]
        random.shuffle(options)
        # Telegram poll options must be <= 100 chars
        options = [o[:100] for o in options][:10]
        await context.bot.send_poll(
            update.effective_chat.id,
            question=question[:300],
            options=options,
            type="quiz",
            correct_option_id=options.index(correct[:100]),
            is_anonymous=False,
        )
    except Exception:
        await update.message.reply_text("😅 Couldn't load a quiz right now. Try again!")


def register(app: Application):
    app.add_handler(CommandHandler("joke", joke))
    app.add_handler(CommandHandler("quote", quote))
    app.add_handler(CommandHandler("fact", fact))
    app.add_handler(CommandHandler("meme", meme))
    app.add_handler(CommandHandler("dice", dice))
    app.add_handler(CommandHandler("dart", dart))
    app.add_handler(CommandHandler("coin", coin))
    app.add_handler(CommandHandler("8ball", eightball))
    app.add_handler(CommandHandler("quiz", quiz))
