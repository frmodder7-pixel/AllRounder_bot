"""Profiles, coins, shop items, gifting, and extra lightweight games."""
import random

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import Application, CommandHandler, ContextTypes

import db
from utils import mention

SHOP = {
    "vip": {"price": 250, "title": "VIP Member", "badge": "💎"},
    "legend": {"price": 500, "title": "Group Legend", "badge": "👑"},
    "helper": {"price": 180, "title": "Helpful Dost", "badge": "🤝"},
    "gamer": {"price": 160, "title": "Game Champ", "badge": "🎮"},
}

RIDDLES = [
    ("What has keys but no locks?", "keyboard"),
    ("I speak without a mouth and hear without ears. What am I?", "echo"),
    ("What gets wetter as it dries?", "towel"),
    ("Which month has 28 days?", "all"),
    ("What has hands but cannot clap?", "clock"),
]
DARES = [
    "Send a voice note saying your favorite movie dialogue.",
    "Compliment the last person who messaged.",
    "Tell the group one funny childhood memory.",
    "Use only emojis for your next message.",
]
TRUTHS = [
    "What is one habit you want to improve?",
    "Who in this group makes you laugh most?",
    "What was your most embarrassing typo?",
    "What is a food you can eat anytime?",
]
_RIDDLE_STATE = {}
_NUMBER_STATE = {}
_WORDCHAIN_STATE = {}
_RAPID_QUIZ_STATE = {}
RAPID_QUIZ = [
    ("Capital of India?", "delhi"),
    ("2 + 8 * 2 = ?", "18"),
    ("Which sport uses wickets?", "cricket"),
    ("Hindi word for water?", "pani"),
    ("How many days in a leap year?", "366"),
]


def _is_group(update: Update) -> bool:
    return update.effective_chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)


def _level(total: int) -> tuple[int, int]:
    level = 1
    needed = 100
    left = total
    while left >= needed:
        left -= needed
        level += 1
        needed += 50
    return level, needed - left


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_group(update):
        await update.message.reply_text("Profile works inside groups.")
        return
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    total, rank = db.my_rank(update.effective_chat.id, target.id)
    wallet = db.get_wallet(update.effective_chat.id, target.id)
    level, next_left = _level(total)
    title = wallet.get("title") or "Member"
    badge = wallet.get("badge") or "⭐"
    await update.message.reply_html(
        f"{badge} <b>Profile</b>\n"
        f"User: {mention(target.id, target.first_name)}\n"
        f"Title: <b>{title}</b>\n"
        f"Level: <b>{level}</b> ({next_left} pts to next)\n"
        f"Rank: <b>{'#' + str(rank) if rank else 'unranked'}</b>\n"
        f"Points: <b>{total}</b>\n"
        f"Coins: <b>{wallet.get('coins', 0)}</b>"
    )


async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_group(update):
        await update.message.reply_text("Wallet works inside groups.")
        return
    user = update.effective_user
    db.ensure_wallet(update.effective_chat.id, user.id, user.first_name)
    w = db.get_wallet(update.effective_chat.id, user.id)
    await update.message.reply_html(
        f"👛 {mention(user.id, user.first_name)}\n"
        f"Coins: <b>{w.get('coins', 0)}</b>\n"
        f"Badge: <b>{w.get('badge') or '⭐'}</b>\n"
        f"Title: <b>{w.get('title') or 'Member'}</b>"
    )


async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["🛒 <b>Shop</b>\n"]
    for key, item in SHOP.items():
        lines.append(f"• <code>{key}</code> — {item['badge']} {item['title']} — <b>{item['price']}</b> coins")
    lines.append("\nBuy with <code>/buy vip</code>")
    await update.message.reply_html("\n".join(lines))


async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_group(update):
        await update.message.reply_text("Buy shop items inside groups.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /buy vip")
        return
    key = context.args[0].lower()
    item = SHOP.get(key)
    if not item:
        await update.message.reply_text("Unknown item. See /shop.")
        return
    user = update.effective_user
    db.ensure_wallet(update.effective_chat.id, user.id, user.first_name)
    if not db.spend_coins(update.effective_chat.id, user.id, item["price"]):
        await update.message.reply_text("Not enough coins yet. Chat, play games, and claim /daily.")
        return
    db.set_wallet_item(update.effective_chat.id, user.id, title=item["title"], badge=item["badge"])
    await update.message.reply_html(f"✅ Bought {item['badge']} <b>{item['title']}</b>.")


async def give(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_group(update):
        await update.message.reply_text("Use this inside a group.")
        return
    if not update.message.reply_to_message or not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Reply to someone with: /give 25")
        return
    amount = int(context.args[0])
    if amount <= 0 or amount > 1000:
        await update.message.reply_text("Give between 1 and 1000 coins.")
        return
    sender = update.effective_user
    target = update.message.reply_to_message.from_user
    if target.is_bot or target.id == sender.id:
        await update.message.reply_text("Pick another real user.")
        return
    ok = db.transfer_coins(update.effective_chat.id, sender.id, target.id, target.first_name, amount)
    if not ok:
        await update.message.reply_text("Not enough coins.")
        return
    await update.message.reply_html(
        f"🎁 {mention(sender.id, sender.first_name)} gave <b>{amount}</b> coins to {mention(target.id, target.first_name)}."
    )


async def truth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧩 Truth: " + random.choice(TRUTHS))


async def dare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 Dare: " + random.choice(DARES))


async def riddle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_group(update):
        await update.message.reply_text("Play riddles inside groups.")
        return
    q, a = random.choice(RIDDLES)
    _RIDDLE_STATE[update.effective_chat.id] = a
    await update.message.reply_html(f"🧠 <b>Riddle</b>\n\n{q}\n\nReply with <code>/answer your answer</code>.")


async def guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_group(update):
        await update.message.reply_text("Play guess inside groups.")
        return
    _NUMBER_STATE[update.effective_chat.id] = random.randint(1, 20)
    await update.message.reply_text("🎯 I picked a number from 1 to 20. Use /guessnum 7")


async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /answer keyboard")
        return
    chat_id = update.effective_chat.id
    expected = _RIDDLE_STATE.get(chat_id)
    if not expected:
        await update.message.reply_text("No active riddle. Start one with /riddle.")
        return
    given = " ".join(context.args).strip().lower()
    if given == expected:
        _RIDDLE_STATE.pop(chat_id, None)
        total = db.add_points(chat_id, update.effective_user.id, update.effective_user.first_name, 10)
        coins = db.add_coins(chat_id, update.effective_user.id, update.effective_user.first_name, 5)
        await update.message.reply_html(f"✅ Correct! +10 points, +5 coins. Total: <b>{total}</b> pts, <b>{coins}</b> coins.")
    else:
        await update.message.reply_text("Not correct. Try again.")


async def guessnum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /guessnum 7")
        return
    chat_id = update.effective_chat.id
    target = _NUMBER_STATE.get(chat_id)
    if not target:
        await update.message.reply_text("No active number game. Start one with /guess.")
        return
    n = int(context.args[0])
    if n == target:
        _NUMBER_STATE.pop(chat_id, None)
        total = db.add_points(chat_id, update.effective_user.id, update.effective_user.first_name, 12)
        coins = db.add_coins(chat_id, update.effective_user.id, update.effective_user.first_name, 6)
        await update.message.reply_html(f"🎉 Correct number! +12 points, +6 coins. Total: <b>{total}</b> pts, <b>{coins}</b> coins.")
    elif n < target:
        await update.message.reply_text("Higher.")
    else:
        await update.message.reply_text("Lower.")


async def wordchain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_group(update):
        await update.message.reply_text("Play word chain inside groups.")
        return
    seed = random.choice(["mango", "cricket", "train", "namaste", "energy"])
    _WORDCHAIN_STATE[update.effective_chat.id] = seed[-1]
    await update.message.reply_html(
        f"🔗 <b>Word Chain</b>\nStart word: <b>{seed}</b>\n"
        f"Next word must start with <b>{seed[-1].upper()}</b>.\nUse <code>/chain word</code>."
    )


async def chain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /chain elephant")
        return
    chat_id = update.effective_chat.id
    needed = _WORDCHAIN_STATE.get(chat_id)
    if not needed:
        await update.message.reply_text("No word chain active. Start one with /wordchain.")
        return
    word = context.args[0].strip().lower()
    if len(word) < 3 or not word.isalpha():
        await update.message.reply_text("Use a real word with at least 3 letters.")
        return
    if word[0] != needed:
        await update.message.reply_text(f"Word must start with {needed.upper()}.")
        return
    _WORDCHAIN_STATE[chat_id] = word[-1]
    total = db.add_points(chat_id, update.effective_user.id, update.effective_user.first_name, 3)
    if random.random() < 0.35:
        db.add_coins(chat_id, update.effective_user.id, update.effective_user.first_name, 1)
    await update.message.reply_html(
        f"✅ Accepted: <b>{word}</b>. Next starts with <b>{word[-1].upper()}</b>.\n"
        f"+3 points (total: <b>{total}</b>)"
    )


async def rapid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_group(update):
        await update.message.reply_text("Play rapid quiz inside groups.")
        return
    q, a = random.choice(RAPID_QUIZ)
    _RAPID_QUIZ_STATE[update.effective_chat.id] = a
    await update.message.reply_html(f"⚡ <b>Rapid Quiz</b>\n\n{q}\n\nAnswer with <code>/rapidanswer your answer</code>.")


async def rapidanswer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /rapidanswer delhi")
        return
    chat_id = update.effective_chat.id
    expected = _RAPID_QUIZ_STATE.get(chat_id)
    if not expected:
        await update.message.reply_text("No rapid quiz active. Start one with /rapid.")
        return
    given = " ".join(context.args).strip().lower()
    if given == expected:
        _RAPID_QUIZ_STATE.pop(chat_id, None)
        total = db.add_points(chat_id, update.effective_user.id, update.effective_user.first_name, 8)
        coins = db.add_coins(chat_id, update.effective_user.id, update.effective_user.first_name, 4)
        await update.message.reply_html(f"⚡ Correct! +8 points, +4 coins. Total: <b>{total}</b> pts, <b>{coins}</b> coins.")
    else:
        await update.message.reply_text("Wrong answer. Try again.")


async def predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args).strip() or "this"
    chance = random.randint(1, 100)
    vibe = "strong" if chance >= 70 else "possible" if chance >= 40 else "low"
    await update.message.reply_text(f"🔮 Prediction for {topic}: {chance}% chance. Vibe: {vibe}.")


def register(app: Application):
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("level", profile))
    app.add_handler(CommandHandler("wallet", wallet))
    app.add_handler(CommandHandler("coins", wallet))
    app.add_handler(CommandHandler("shop", shop))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("give", give))
    app.add_handler(CommandHandler("truth", truth))
    app.add_handler(CommandHandler("dare", dare))
    app.add_handler(CommandHandler("riddle", riddle))
    app.add_handler(CommandHandler("answer", answer))
    app.add_handler(CommandHandler("guess", guess))
    app.add_handler(CommandHandler("guessnum", guessnum))
    app.add_handler(CommandHandler("wordchain", wordchain))
    app.add_handler(CommandHandler("chain", chain))
    app.add_handler(CommandHandler("rapid", rapid))
    app.add_handler(CommandHandler("rapidanswer", rapidanswer))
    app.add_handler(CommandHandler("predict", predict))
