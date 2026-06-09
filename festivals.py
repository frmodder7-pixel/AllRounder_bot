"""Festival auto-wishes for Indian users. 🎊
A daily job (08:00 IST) checks the date and, if it's a festival, sends a
warm Hinglish greeting to every group the bot is in.

⚠️ Dates are for 2026 and verified from Drik Panchang / timeanddate.
Lunar festivals (Holi, Eid, Diwali, etc.) shift each year — update the
FESTIVALS_2026 table annually. Islamic dates depend on moon sighting and
may move by a day.
"""
import logging
from datetime import time
from zoneinfo import ZoneInfo

from telegram.ext import Application, ContextTypes

import config
import db

log = logging.getLogger("allrounder.festivals")
IST = ZoneInfo("Asia/Kolkata")

# (month, day) -> (title, message). Verified 2026 dates.
FESTIVALS_2026 = {
    (1, 1):  ("New Year", "🎆 <b>Happy New Year 2026!</b> 🥳\nNaya saal aapke liye khushiyan, sehat aur dher saari success laaye! ✨"),
    (1, 26): ("Republic Day", "🇮🇳 <b>Happy Republic Day!</b> 🎉\nGantantra Diwas ki hardik shubhkamnaayein! Jai Hind! 🙏"),
    (3, 4):  ("Holi", "🌈 <b>Happy Holi!</b> 🎨\nRangon ka tyohaar mubarak ho! Khoob masti karo, gujiya khao aur rang lagao! 💦😄"),
    (3, 20): ("Eid ul-Fitr", "🌙 <b>Eid Mubarak!</b> ✨\nEid-ul-Fitr ki dher saari mubarakbaad! Khushiyan aapke ghar mein basi rahein. 🤲❤️"),
    (5, 27): ("Bakri Eid", "🌙 <b>Eid-ul-Adha Mubarak!</b> 🐐\nBakri Eid ki hardik shubhkamnaayein! Allah aapki har dua kubool kare. 🤲"),
    (8, 15): ("Independence Day", "🇮🇳 <b>Happy Independence Day!</b> 🎉\nSwatantrata Diwas ki shubhkamnaayein! Jai Hind, Vande Mataram! 🙏🧡🤍💚"),
    (8, 28): ("Raksha Bandhan", "🪢 <b>Happy Raksha Bandhan!</b> ❤️\nBhai-behen ke pyaar ka tyohaar mubarak ho! Rakhi ki dher saari shubhkamnaayein! 🎁"),
    (9, 4):  ("Janmashtami", "🦚 <b>Happy Janmashtami!</b> 🙏\nNand ke aanand bhayo, Jai Kanhaiya Lal ki! Krishna ji aapko khush rakhein. 💙🪈"),
    (9, 14): ("Ganesh Chaturthi", "🐘 <b>Happy Ganesh Chaturthi!</b> 🙏\nGanpati Bappa Morya! Bappa aapke saare vighn door karein. 🌺✨"),
    (10, 2): ("Gandhi Jayanti", "🕊️ <b>Gandhi Jayanti</b> 🙏\nBapu ke aadarshon ko yaad karte hue — satya aur ahimsa ki raah par chalein. 🤍"),
    (10, 20):("Dussehra", "🏹 <b>Happy Dussehra!</b> 🔥\nVijayadashami ki shubhkamnaayein! Buraai par acchai ki jeet ho. Jai Shri Ram! 🙏"),
    (11, 8): ("Diwali", "🪔 <b>Happy Diwali!</b> ✨\nDeepavali ki dher saari shubhkamnaayein! Aapka ghar sukh, samriddhi aur roshni se bhara rahe. 🎆🪔❤️"),
}


async def _festival_job(context: ContextTypes.DEFAULT_TYPE):
    from datetime import datetime
    today = datetime.now(IST)
    key = (today.month, today.day)
    festival = FESTIVALS_2026.get(key)
    if not festival:
        return
    title, message = festival
    text = f"{message}\n\n{config.SIGNATURE}"
    sent = failed = 0
    for row in db.list_chats(limit=10000):
        try:
            await context.bot.send_message(row["chat_id"], text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
    log.info("Festival '%s' wished to %d chats (%d failed).", title, sent, failed)


async def festival_test(update, context: ContextTypes.DEFAULT_TYPE):
    """Owner-only: preview today's (or any) festival message. Usage: /festivaltest [MM-DD]"""
    if not config.OWNER_ID or update.effective_user.id != config.OWNER_ID:
        await update.message.reply_text("⛔ Owner only.")
        return
    from datetime import datetime
    if context.args:
        try:
            m, d = map(int, context.args[0].split("-"))
        except Exception:
            await update.message.reply_text("Usage: /festivaltest MM-DD  (e.g. /festivaltest 11-08)")
            return
    else:
        now = datetime.now(IST)
        m, d = now.month, now.day
    festival = FESTIVALS_2026.get((m, d))
    if not festival:
        await update.message.reply_text(f"No festival on {m:02d}-{d:02d}.")
        return
    await update.message.reply_html(f"{festival[1]}\n\n{config.SIGNATURE}")


def register(app: Application):
    from telegram.ext import CommandHandler
    app.add_handler(CommandHandler("festivaltest", festival_test))
    # Run every day at 08:00 IST and wish if it's a festival.
    app.job_queue.run_daily(_festival_job, time=time(hour=8, minute=0, tzinfo=IST))
