"""Daily engagement: 🌅 good-morning image + Aaj ka Vichaar, and a
🏆 daily activity leaderboard so the whole group competes every day.

Jobs (Asia/Kolkata):
  • 07:00 — Good Morning image + thought to every group
  • 22:00 — "Aaj ke Champions" daily Top-5 to every active group, then reset

Commands:
  • /leaderboard (/top)  — all-time Top-10 of this group
  • /today               — today's Top-5 so far
  • /rank                — your points & rank
"""
import logging
import random
from datetime import datetime, time
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import config
import db
from utils import mention

log = logging.getLogger("allrounder.engagement")
IST = ZoneInfo("Asia/Kolkata")

MEDALS = ["🥇", "🥈", "🥉", "🏅", "🎖️"]

# Word-scramble game state: chat_id -> answer (lowercase). In-memory.
_active_games = {}
GAME_WORDS = [
    "elephant", "computer", "rainbow", "cricket", "bollywood", "samosa",
    "mountain", "diamond", "festival", "chocolate", "butterfly", "monsoon",
    "treasure", "galaxy", "pyramid", "internet", "champion", "freedom",
    "biryani", "harmony", "victory", "journey", "sunshine", "thunder",
]


def _today_str() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d")


def _yesterday_str() -> str:
    from datetime import timedelta
    return (datetime.now(IST) - timedelta(days=1)).strftime("%Y-%m-%d")


def _week_str() -> str:
    # ISO year-week, e.g. "2026-W23" — same for all days in a week.
    y, w, _ = datetime.now(IST).isocalendar()
    return f"{y}-W{w:02d}"


# ---------------- Good Morning content ----------------
# Royalty-free morning images (Unsplash direct links).
GM_IMAGES = [
    "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05",  # misty hills
    "https://images.unsplash.com/photo-1506744038136-46273834b3fb",  # lake sunrise
    "https://images.unsplash.com/photo-1500382017468-9049fed747ef",  # field morning
    "https://images.unsplash.com/photo-1444703686981-a3abbc4d4fe3",  # sunrise sky
    "https://images.unsplash.com/photo-1418065460487-3e41a6c84dc5",  # green valley
]

VICHAAR = [
    "Subah ki shuruaat ek nayi umeed ke saath karo. Aaj ka din aapka hai! 🌅",
    "Mehnat itni khamoshi se karo ki safalta shor macha de. 💪",
    "Khush rehna ek choice hai — aaj wahi choose karo. 😊",
    "Chhoti shuruaat bhi badi manzil tak le jaati hai. Bas chalte raho. 🚶‍♂️✨",
    "Jo beet gaya use bhool jao, jo aane wala hai use behtar banao. 🌱",
    "Apne aap par bharosa rakho — aap soch se zyada kar sakte ho. 🔥",
    "Muskuraahat free hai, par iski keemat anmol hai. Aaj khoob muskurao! 😄",
    "Har subah ek naya panna hai — aaj kuch accha likho. 📖",
]

# Royalty-free night images (Unsplash).
GN_IMAGES = [
    "https://images.unsplash.com/photo-1532978379173-523e16f371f9",  # starry night
    "https://images.unsplash.com/photo-1419242902214-272b3f66ee7a",  # moon
    "https://images.unsplash.com/photo-1507400492013-162706c8c05e",  # night sky
    "https://images.unsplash.com/photo-1444080748397-f442aa95c3e5",  # milky way
]
GN_LINES = [
    "Din bhar ki thakaan ab chhod do, aaram se so jao. 😴",
    "Sapne wahi sach hote hain jinke liye aap mehnat karte ho. Good night! 🌙",
    "Aaj jo accha hua uske liye shukar, jo bura hua use bhula do. 🌌",
    "Neend poori karo — kal phir ek naya mauka milega. ✨",
]


async def _good_morning_job(context: ContextTypes.DEFAULT_TYPE):
    caption = (
        f"🌅 <b>Good Morning, Doston!</b> ☀️\n\n"
        f"💭 <b>Aaj ka Vichaar:</b>\n<i>{random.choice(VICHAAR)}</i>\n\n"
        f"Aaj ka din shaandaar ho! 💛 {config.SIGNATURE}"
    )
    image = random.choice(GM_IMAGES)
    sent = 0
    for row in db.list_chats(limit=10000):
        try:
            await context.bot.send_photo(row["chat_id"], image, caption=caption, parse_mode="HTML")
            sent += 1
        except Exception:
            try:
                await context.bot.send_message(row["chat_id"], caption, parse_mode="HTML")
                sent += 1
            except Exception:
                pass
    log.info("Good morning sent to %d chats.", sent)


# ---------------- Good Night (nightly) ----------------
async def _good_night_job(context: ContextTypes.DEFAULT_TYPE):
    caption = (
        f"🌙 <b>Good Night, Doston!</b> ✨\n\n"
        f"<i>{random.choice(GN_LINES)}</i>\n\n"
        f"Meethe sapne! 💤 {config.SIGNATURE}"
    )
    image = random.choice(GN_IMAGES)
    for row in db.list_chats(limit=10000):
        try:
            await context.bot.send_photo(row["chat_id"], image, caption=caption, parse_mode="HTML")
        except Exception:
            try:
                await context.bot.send_message(row["chat_id"], caption, parse_mode="HTML")
            except Exception:
                pass


# ---------------- Member of the Week (Sunday) ----------------
async def _member_of_week_job(context: ContextTypes.DEFAULT_TYPE):
    # Runs daily but only acts on Sunday (weekday() == 6: Mon=0 … Sun=6).
    if datetime.now(IST).weekday() != 6:
        return
    week = _week_str()
    for chat_id in db.weeks_active_chats(week):
        rows = db.top_weekly(chat_id, week, limit=1)
        if not rows:
            continue
        w = rows[0]
        # Bonus 50 points for the champion 👑
        db.add_points(chat_id, w["user_id"], w["name"], 50)
        text = (
            f"👑 <b>Member of the Week!</b> 🎉\n\n"
            f"Is hafte ke superstar: {mention(w['user_id'], w['name'])} 🌟\n"
            f"📨 <b>{w['count']}</b> messages is week!\n"
            f"🎁 Bonus: <b>+50 points</b>!\n\n"
            f"Agle hafte ye taaj kiska? Compete karo! 🔥 {config.SIGNATURE}"
        )
        try:
            await context.bot.send_message(chat_id, text, parse_mode="HTML")
        except Exception:
            pass
    log.info("Member of the week posted for %s.", week)


# ---------------- Daily winners (nightly) ----------------
async def _daily_winners_job(context: ContextTypes.DEFAULT_TYPE):
    day = _today_str()
    for chat_id in db.all_active_chats(day):
        rows = db.top_today(chat_id, day, limit=5)
        if not rows:
            continue
        lines = ["🏆 <b>Aaj ke Champions!</b> 🎉\n", "Aaj sabse zyada active members:\n"]
        for i, r in enumerate(rows):
            medal = MEDALS[i] if i < len(MEDALS) else "•"
            lines.append(f"{medal} {mention(r['user_id'], r['name'])} — <b>{r['count']}</b> msgs")
        lines.append(f"\nKal phir compete karo! 🔥 {config.SIGNATURE}")
        try:
            await context.bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML")
        except Exception:
            pass
    log.info("Daily winners posted for %s.", day)


# ---------------- Word-scramble game ----------------
def _scramble(word: str) -> str:
    letters = list(word)
    for _ in range(5):
        random.shuffle(letters)
        if "".join(letters) != word:
            break
    return " ".join(l.upper() for l in letters)


async def _expire_game(context: ContextTypes.DEFAULT_TYPE):
    chat_id, answer = context.job.data
    if _active_games.get(chat_id) == answer:
        _active_games.pop(chat_id, None)
        try:
            await context.bot.send_message(
                chat_id, f"⏰ Time up! Sahi shabd tha: <b>{answer.upper()}</b>", parse_mode="HTML"
            )
        except Exception:
            pass


async def wordgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.message.reply_text("🎯 Word game sirf groups mein khelo!")
        return
    if chat.id in _active_games:
        await update.message.reply_text("🎮 Ek game already chal raha hai — pehle wo solve karo!")
        return
    word = random.choice(GAME_WORDS)
    _active_games[chat.id] = word
    await update.message.reply_html(
        f"🎯 <b>Word Scramble!</b>\n\n"
        f"Is shabd ko suljhaao 👇\n\n<b>{_scramble(word)}</b>\n\n"
        f"Sabse pehle sahi answer type karo aur jeeto <b>15 points</b>! ⏱️ 60 sec"
    )
    context.job_queue.run_once(_expire_game, 60, data=(chat.id, word))


# ---------------- Activity counter (passive) + game checker ----------------
async def activity_counter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not user or user.is_bot:
        return
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    db.bump_activity(chat.id, user.id, _today_str(), user.first_name)
    db.bump_weekly(chat.id, user.id, _week_str(), user.first_name)

    # Word-game winner check
    answer = _active_games.get(chat.id)
    if answer and msg.text and msg.text.strip().lower() == answer:
        _active_games.pop(chat.id, None)
        total = db.add_points(chat.id, user.id, user.first_name, 15)
        await msg.reply_html(
            f"🎉 Sahi jawaab! {mention(user.id, user.first_name)} ne <b>{answer.upper()}</b> "
            f"sabse pehle solve kiya!\n➕ <b>15 points</b> (total: <b>{total}</b>) 🏆"
        )


# ---------------- /daily bonus + streak ----------------
def _streak_emoji(streak: int) -> str:
    if streak >= 30:
        return "💎"
    if streak >= 14:
        return "🔥🔥"
    if streak >= 7:
        return "🔥"
    return "⭐"


async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.message.reply_text("🎁 Daily bonus sirf groups mein milta hai!")
        return
    already, streak = db.claim_daily(chat.id, user.id, _today_str(), _yesterday_str())
    if already:
        await update.message.reply_html(
            f"⏳ {mention(user.id, user.first_name)}, aaj ka bonus le liya hai!\n"
            f"Kal phir aana. Streak: <b>{streak}</b> {_streak_emoji(streak)}"
        )
        return
    # Reward grows with streak: 10 base + 5 per streak day, capped.
    reward = min(10 + streak * 5, 100)
    total = db.add_points(chat.id, user.id, user.first_name, reward)
    await update.message.reply_html(
        f"🎁 {mention(user.id, user.first_name)} ne daily bonus claim kiya!\n"
        f"➕ <b>{reward} points</b> (total: <b>{total}</b>)\n"
        f"🔥 Streak: <b>{streak} din</b> {_streak_emoji(streak)}\n"
        f"<i>Roz aao, streak badhao, zyada points kamao!</i>"
    )


# ---------------- Commands ----------------
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.message.reply_text("🏆 Leaderboard sirf groups mein chalta hai!")
        return
    rows = db.top_alltime(chat.id, limit=10)
    if not rows:
        await update.message.reply_text("📊 Abhi koi data nahi. Chatting shuru karo points kamao! 🔥")
        return
    lines = [f"🏆 <b>{chat.title} — Top Members</b> (all-time)\n"]
    for i, r in enumerate(rows):
        medal = MEDALS[i] if i < len(MEDALS) else f"{i+1}."
        lines.append(f"{medal} {mention(r['user_id'], r['name'])} — <b>{r['total']}</b> pts")
    lines.append("\nHar message = 1 point. Top par pahuncho! 💪")
    await update.message.reply_html("\n".join(lines))


async def today_board(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.message.reply_text("📊 Ye sirf groups mein chalta hai!")
        return
    rows = db.top_today(chat.id, _today_str(), limit=5)
    if not rows:
        await update.message.reply_text("📊 Aaj abhi tak koi active nahi. Pehle bano! 🥇")
        return
    lines = ["📊 <b>Aaj ke Top 5 (ab tak)</b>\n"]
    for i, r in enumerate(rows):
        medal = MEDALS[i] if i < len(MEDALS) else "•"
        lines.append(f"{medal} {mention(r['user_id'], r['name'])} — <b>{r['count']}</b> msgs")
    await update.message.reply_html("\n".join(lines))


async def my_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.message.reply_text("🎯 Rank sirf groups mein milti hai!")
        return
    total, rank = db.my_rank(chat.id, user.id)
    if not rank:
        await update.message.reply_text("🤷 Abhi aapke points nahi. Chatting karo aur rank banao! 🔥")
        return
    await update.message.reply_html(
        f"🎯 {mention(user.id, user.first_name)}\n"
        f"🏆 Points: <b>{total}</b>\n📊 Rank: <b>#{rank}</b> is group mein!"
    )


def register(app: Application):
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("top", leaderboard))
    app.add_handler(CommandHandler("today", today_board))
    app.add_handler(CommandHandler("rank", my_rank))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("wordgame", wordgame))
    app.add_handler(CommandHandler("game", wordgame))
    # Passive counter in a late group so it never blocks anything.
    app.add_handler(
        MessageHandler((filters.TEXT | filters.CAPTION) & ~filters.COMMAND, activity_counter),
        group=3,
    )
    # Scheduled jobs (Asia/Kolkata)
    app.job_queue.run_daily(_good_morning_job, time=time(hour=7, minute=0, tzinfo=IST))
    app.job_queue.run_daily(_good_night_job, time=time(hour=23, minute=0, tzinfo=IST))
    app.job_queue.run_daily(_daily_winners_job, time=time(hour=22, minute=0, tzinfo=IST))
    # Member of the Week — fires daily at 20:00 IST, but only acts on Sundays.
    app.job_queue.run_daily(_member_of_week_job, time=time(hour=20, minute=0, tzinfo=IST))
