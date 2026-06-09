"""Fun: jokes, quotes, facts, memes, dice, coin flip, magic 8-ball, quiz.
All network calls are wrapped so a failing API never breaks the bot."""
import random

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import config

_TIMEOUT = httpx.Timeout(10.0)

EIGHTBALL = [
    "Haan, pakka! ✅", "Bilkul sahi! 💯", "Haan ji, definitely. 👍",
    "Lagta toh hai. 🙂", "Baad mein poocho. ⏳", "Abhi nahi bata sakta. 🤐",
    "Na baba na. 🚫", "Mera jawab hai NO. ❌", "Bahut shaq hai. 😬",
]

# Desi Hinglish jokes — Hindi written in English letters 😂
HINGLISH_JOKES = [
    "Pappu: Doctor sahab, mujhe bhoolne ki bimari hai.\nDoctor: Kab se?\nPappu: Kab se kya? 🤔😂",
    "Teacher: Bada hokar kya banoge?\nStudent: Sir, aapke jaisa nahi banunga, itna toh pakka hai! 😎😂",
    "Wife: Suno ji, aaj khaana main banaungi.\nHusband: Theek hai, main Swiggy se mangwa leta hoon backup ke liye. 🍔😆",
    "Santa: Yaar meri ghadi kho gayi.\nBanta: Dhoond le.\nSanta: Time nahi hai! ⏰😂",
    "Ladka: I love you.\nLadki: Pehle apni Maggi toh time pe bana le, pyaar baad mein dekhenge. 🍜😂",
    "Boss: Tum late kyun aaye?\nEmployee: Sir, TV pe likha tha — 'Ghar baithe kamao', toh bas... 📺😂",
    "Exam mein 3 ghante: pen chala nahi.\nGhar aate hi WhatsApp pe 200 message: ek second mein. 📱😂",
    "Mummy: Beta padhai kar.\nMain: Kar raha hoon.\nMummy: Phone mein kya hai?\nMain: ...padhai ka mood. 😬😂",
    "Dost: Tu itna intelligent kaise hai?\nMain: Bachpan mein Cerelac nahi, Boost piya tha. 💪😂",
    "Bijli wale: Aaj light nahi aayegi.\nMain: Koi na, vibe candle-light dinner wali kar lenge. 🕯️😂",
]

# Bonus: desi shayari 🌹
SHAYARIS = [
    "Zindagi mein do cheezein kabhi mat todna —\nek bharosa, aur doosra Maggi banate waqt ka time. 🍜❤️",
    "Chai ki pyaali aur tumhari yaad,\ndono ke bina subah adhuri lagti hai. ☕✨",
    "Log kehte hain mehnat karo,\nhum kehte hain pehle thodi neend poori karo. 😴💪",
    "Dil toh bachcha hai ji,\nisliye har baar biryani dekhke macha leta hai. 🍛😄",
    "Dosti tumse hai, isliye life set hai,\nwarna duniya toh bas WiFi ke peeche bhaag rahi hai. 📶❤️",
]


async def _get_json(url):
    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
        r = await client.get(url, headers={"Accept": "application/json"})
        r.raise_for_status()
        return r.json()


async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 70% desi Hinglish joke, 30% English from API — full desi vibe 😂
    if random.random() < 0.7:
        await update.message.reply_text(f"😂 {random.choice(HINGLISH_JOKES)}")
        return
    try:
        d = await _get_json("https://official-joke-api.appspot.com/random_joke")
        await update.message.reply_text(f"😂 {d['setup']}\n\n👉 {d['punchline']}")
    except Exception:
        # If the API fails, never leave the user hanging — desi joke saves the day
        await update.message.reply_text(f"😂 {random.choice(HINGLISH_JOKES)}")


async def shayari(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🌹 {random.choice(SHAYARIS)}")


async def cricket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Live cricket scores. Uses CricketData.org if a free key is configured,
    otherwise points the user to live scores. Accurate, no fake data."""
    if not config.CRICKET_API_KEY:
        await update.message.reply_html(
            "🏏 <b>Live cricket scores</b> ka feature ready hai!\n"
            "Bas ek <b>free</b> API key chahiye (https://cricketdata.org).\n"
            "BLITEX usse <code>CRICKET_API_KEY</code> mein daal de — phir live scores yahin milenge! 🔥\n\n"
            "Abhi ke liye: <a href=\"https://www.cricbuzz.com/cricket-match/live-scores\">Cricbuzz live scores</a> 📺"
        )
        return
    try:
        d = await _get_json(
            f"https://api.cricapi.com/v1/currentMatches?apikey={config.CRICKET_API_KEY}&offset=0"
        )
        matches = [m for m in d.get("data", []) if m.get("matchStarted") and not m.get("matchEnded")]
        if not matches:
            matches = d.get("data", [])[:3]
        if not matches:
            await update.message.reply_text("🏏 Abhi koi live match nahi hai.")
            return
        lines = ["🏏 <b>Cricket Scores</b>\n"]
        for m in matches[:5]:
            lines.append(f"• <b>{m.get('name', 'Match')}</b>")
            for s in m.get("score", []):
                lines.append(f"   {s.get('inning', '')}: {s.get('r', 0)}/{s.get('w', 0)} ({s.get('o', 0)} ov)")
            if m.get("status"):
                lines.append(f"   <i>{m['status']}</i>")
        await update.message.reply_html("\n".join(lines))
    except Exception:
        await update.message.reply_html(
            "🏏 Score laane mein dikkat aa rahi hai. Thodi der baad try karo, "
            "ya <a href=\"https://www.cricbuzz.com/cricket-match/live-scores\">Cricbuzz</a> dekho. 📺"
        )


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
    app.add_handler(CommandHandler("shayari", shayari))
    app.add_handler(CommandHandler("cricket", cricket))
    app.add_handler(CommandHandler("quote", quote))
    app.add_handler(CommandHandler("fact", fact))
    app.add_handler(CommandHandler("meme", meme))
    app.add_handler(CommandHandler("dice", dice))
    app.add_handler(CommandHandler("dart", dart))
    app.add_handler(CommandHandler("coin", coin))
    app.add_handler(CommandHandler("8ball", eightball))
    app.add_handler(CommandHandler("quiz", quiz))
