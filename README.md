# 🤖 All Rounder Bot — *by BLITEX*

A premium, all-in-one Telegram group bot: greetings, moderation, fun, tools and an optional AI brain. Deploy from **GitHub** to **Railway** or Render.

> ✅ **Safe for your account.** This is a normal bot created through **@BotFather** — it has its *own* identity and does not log in as your personal Telegram account. Keep tokens private and avoid spammy broadcasts so Telegram does not restrict the bot.

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
- `/ask`, `/summary`, `/ai on|mentions|privateonly|off|chatty`, `/aimod on|off`
- `/imagine`, `/editimage`, `/sticker`, `/caption`, `/bio`, `/rewrite`, `/announce`, `/pollidea`, `/logoidea`, `/stickeridea`
- `/setrules`, `/rules`, `/faqadd`, `/faq`, `/faqauto`

**🪙 Profiles & Economy**
- `/profile`, `/wallet`, `/shop`, `/buy`, `/give`
- Extra games: `/truth`, `/dare`, `/riddle`, `/answer`, `/guess`, `/guessnum`, `/wordchain`, `/chain`, `/rapid`, `/predict`

**👑 Owner tools** — `/stats`, `/broadcast` (reply to a message).

---

## 🚀 Deploy With GitHub + Railway

### 1. Create the bot
1. In Telegram, open **@BotFather** → send `/newbot`
2. Choose a name (e.g. *All Rounder Bot*) and a username ending in `bot`
3. Copy the **token** it gives you.

### 2. Put this code on GitHub
1. Create a new repo on https://github.com (e.g. `allrounder-bot`)
2. Upload all these files (drag-and-drop works), **except** never upload a real `.env`.

### 3. Deploy on Railway
1. Go to https://railway.com → **New Project → Deploy from GitHub repo**
2. Pick your `allrounder-bot` repo.
3. Railway should detect Python. If it asks for a start command, use:
   ```bash
   python bot.py
   ```
4. Open the Railway service → **Variables** and add:
   | Key | Value |
   |-----|-------|
   | `BOT_TOKEN` | *(from BotFather)* |
   | `OWNER_ID` | *(your numeric id — send `/id` to the bot)* |
   | `GEMINI_API_KEY` | *(optional, from https://aistudio.google.com/app/apikey)* |
   | `GEMINI_MODEL` | `gemini-2.5-flash` *(optional)* |
   | `GEMINI_IMAGE_MODEL` | `gemini-2.5-flash-image-preview` *(optional)* |
   | `GEMINI_FALLBACK_MODELS` | `gemini-1.5-flash` *(optional)* |
   | `WARN_LIMIT` | `3` |
5. Review and deploy the staged variable changes, then restart or redeploy the service.

### 4. Test Gemini
After deployment, send `/aistatus` to the bot from your owner account.

- `Gemini: OK` means the AI brain is working.
- `disabled` means `GEMINI_API_KEY` is missing in Railway Variables.
- `failing` means the command will show a safe error like bad key, quota, or model access. It will not print your API key.

In groups, `/ai on` is safe: it behaves like `/ai mentions`, so the bot replies only when mentioned, replied to, or asked with `/ask`. Use `/ai chatty` only if you deliberately want replies to every group message.

### 5. Recommended Railway Database
For permanent points, warns, FAQs, rules, wallets and message summaries:
1. In Railway, add a **Postgres** database to the same project.
2. In your bot service variables, set `DATABASE_URL` to the Postgres connection URL.
3. Redeploy the bot service.

Without `DATABASE_URL`, the bot still works using SQLite on the Railway container. The only downside is that saved data can reset after redeploys/restarts.

### Optional: Deploy on Render
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
   | `GEMINI_MODEL` | `gemini-2.5-flash` *(optional)* |
   | `GEMINI_IMAGE_MODEL` | `gemini-2.5-flash-image-preview` *(optional)* |
   | `GEMINI_FALLBACK_MODELS` | `gemini-1.5-flash` *(optional)* |
4. Click **Deploy**. 🎉

### Keep it awake
Free hosts may sleep after idle time. To keep the bot warm:
1. Copy your Railway public URL.
2. Go to https://uptimerobot.com → add an **HTTP(s) monitor** to that URL, every 5 min.

Done — your bot is online 24/7. ✅

### 6. Add To Your Group
Open the bot → tap **"➕ Add me to your group"**, then make it **admin** so it can welcome members and moderate.

### 7. First Setup Commands
Run these in your group after deployment:

```text
/setrules no spam | respect everyone | no scam links
/faqadd fees What are the fees? | Fees are 500 per month.
/faqauto off
/ai mentions
/aimod off
```

Useful checks:

```text
/aistatus
/ask hello
/imagine premium logo for my Telegram group
/sticker cute desi chai cup smiling
/summary
/profile
/wallet
/admin
```

---

## 🧪 Run locally (optional, for testing)
```bash
pip install -r requirements.txt
# Windows PowerShell:
$env:BOT_TOKEN="your-token"; $env:OWNER_ID="your-id"; python bot.py
```

You can also copy `.env.example` to `.env` for local testing. Run `/aistatus`
as the owner to verify that Gemini can answer without exposing your API key.

## 🛠️ Customize
- Branding: edit `config.py` (`BRAND`, `TAG`).
- Bad-word list: edit `_BADWORDS` in `admin.py`.
- Warn limit: env var `WARN_LIMIT`.

*Crafted with ✨ — by BLITEX.*
