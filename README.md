# 🤖 All Rounder Bot — *by BLITEX*

A premium, all-in-one Telegram group bot: greetings, moderation, fun, tools and an optional AI brain. Free to run on **Render**, code lives on **GitHub**.

> ✅ **Safe for your account.** This is a normal bot created through **@BotFather** — it has its *own* identity and can **never** freeze or affect your personal Telegram account. (We never use risky "userbot" logins.)

---

## ✨ Features

**🎉 Greetings & Social**
- Auto welcome / goodbye (`/setwelcome`, `/setgoodbye`, supports `{name}` `{group}`)
- 🎂 Tag someone + say "happy birthday" → bot wishes the tagged person
- Friendly auto-replies to hi / hello / good morning

**🛡️ Admin & Moderation** (every action shows a **reason**)
- `/ban` `/unban` `/kick` `/mute [10m]` `/unmute`
- `/warn` `/warns` `/resetwarns` (auto-ban at the limit)
- `/pin` `/unpin` `/del` `/purge`
- `/antilink on|off`, `/antiflood on|off`, bad-word filter

**🎮 Fun**
- `/joke` `/quote` `/fact` `/meme` `/dice` `/dart` `/coin` `/8ball` `/quiz`

**🛠️ Tools**
- `/remind 10m text`, `/save` `/get` `/notes` `/clear`
- `/calc`, `/define`, `/tr en text`, `/weather city`, `/time`, `/id`, `/info`

**🧠 AI Brain** (optional) — mention the bot or reply to it for smart answers.

**👑 Owner tools** — `/stats`, `/broadcast` (reply to a message).

---

## 🚀 Deploy in ~10 minutes (100% free)

### 1. Create the bot
1. In Telegram, open **@BotFather** → send `/newbot`
2. Choose a name (e.g. *All Rounder Bot*) and a username ending in `bot`
3. Copy the **token** it gives you.

### 2. Put this code on GitHub
1. Create a new repo on https://github.com (e.g. `allrounder-bot`)
2. Upload all these files (drag-and-drop works), **except** never upload a real `.env`.

### 3. Deploy on Render
1. Go to https://render.com → **New → Web Service** → connect your GitHub repo
2. Settings:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `python bot.py`
   - **Instance type:** Free
3. Add **Environment Variables**:
   | Key | Value |
   |-----|-------|
   | `BOT_TOKEN` | *(from BotFather)* |
   | `OWNER_ID` | *(your numeric id — send `/id` to the bot)* |
   | `GEMINI_API_KEY` | *(optional, from https://aistudio.google.com/app/apikey)* |
4. Click **Deploy**. 🎉

### 4. Keep it awake (so it stays fast)
Render's free service sleeps after 15 min idle. Fix it free:
1. Copy your Render URL (e.g. `https://allrounder-bot.onrender.com`)
2. Go to https://uptimerobot.com → add an **HTTP(s) monitor** to that URL, every 5 min.

Done — your bot is online 24/7. ✅

### 5. Add to your group
Open the bot → tap **"➕ Add me to your group"**, then make it **admin** so it can welcome members and moderate.

---

## 🧪 Run locally (optional, for testing)
```bash
pip install -r requirements.txt
# Windows PowerShell:
$env:BOT_TOKEN="your-token"; $env:OWNER_ID="your-id"; python bot.py
```

## 🛠️ Customize
- Branding: edit `config.py` (`BRAND`, `TAG`).
- Bad-word list: edit `_BADWORDS` in `admin.py`.
- Warn limit: env var `WARN_LIMIT`.

*Crafted with ✨ — by BLITEX.*
