"""All Rounder Bot — by BLITEX
Entry point: starts a tiny keep-alive web server (so Render's free web
service stays happy) and runs the Telegram bot via long polling.
"""
import logging
import threading

from flask import Flask
from telegram import BotCommand, Update
from telegram.ext import Application

import config
import db
import admin
import admin_panel
import engagement
import extra
import festivals
import fun
import greetings
import tools

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("allrounder")

# ---------- keep-alive web server (for Render + UptimeRobot) ----------
web = Flask(__name__)


@web.route("/")
def home():
    return "✅ All Rounder Bot by BLITEX is alive and running!"


def run_web():
    web.run(host="0.0.0.0", port=config.PORT)


# ---------- command list shown in Telegram's menu ----------
async def _post_init(app: Application):
    await app.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Show all commands"),
        BotCommand("admin", "Owner dashboard"),
        BotCommand("ban", "Ban a user (admin)"),
        BotCommand("kick", "Kick a user (admin)"),
        BotCommand("mute", "Mute a user (admin)"),
        BotCommand("warn", "Warn a user (admin)"),
        BotCommand("joke", "Hinglish joke 😂"),
        BotCommand("shayari", "Desi shayari 🌹"),
        BotCommand("roast", "Playful roast 🔥"),
        BotCommand("compliment", "Sweet compliment 💖"),
        BotCommand("cricket", "Live cricket scores 🏏"),
        BotCommand("score", "Match by team 🔍"),
        BotCommand("leaderboard", "Group Top-10 🏆"),
        BotCommand("rank", "Your rank & points 🎯"),
        BotCommand("daily", "Claim daily bonus 🎁"),
        BotCommand("wordgame", "Word scramble game 🎮"),
        BotCommand("meme", "Random meme"),
        BotCommand("quote", "Inspiring quote"),
        BotCommand("quiz", "Trivia quiz"),
        BotCommand("remind", "Set a reminder"),
        BotCommand("weather", "Weather for a city"),
        BotCommand("calc", "Calculator"),
        BotCommand("define", "Dictionary"),
        BotCommand("tr", "Translate text"),
        BotCommand("id", "Get IDs"),
    ])
    me = await app.bot.get_me()
    log.info("Logged in as @%s (%s)", me.username, me.id)


def main():
    if not config.BOT_TOKEN:
        raise SystemExit(
            "❌ BOT_TOKEN is missing. Set it as an environment variable "
            "(get one from @BotFather)."
        )

    db.init_db()
    log.info("Database backend: %s", "PostgreSQL (PERMANENT ✅)" if db._USE_PG else "SQLite (temporary — resets on redeploy)")

    # Start keep-alive server in the background.
    threading.Thread(target=run_web, daemon=True).start()

    application = Application.builder().token(config.BOT_TOKEN).post_init(_post_init).build()

    # Order matters only for the same handler group; registration order is fine.
    extra.register(application)
    admin_panel.register(application)
    admin.register(application)
    tools.register(application)
    fun.register(application)
    greetings.register(application)
    festivals.register(application)
    engagement.register(application)

    log.info("All Rounder Bot is starting…")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
