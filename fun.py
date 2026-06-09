"""Fun: jokes, quotes, facts, memes, dice, coin flip, magic 8-ball, quiz.
All network calls are wrapped so a failing API never breaks the bot."""
import random

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import ai
import config
from utils import mention

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
    "Patni: Aaj bahar khaana khaate hain.\nPati: Theek hai, balcony mein chataai bichha deta hoon. 🏠😂",
    "Santa ne ATM mein likha dekha: 'Cash nahi hai.'\nSanta: Koi na, card se nikaal leta hoon. 💳😂",
    "Teacher: Earth round hai ya flat?\nPappu: Sir, mummy kehti hai duniya gol hai, papa kehte hain duniya bekaar hai. 🌍😂",
    "Ladki: Mujhe chand la do.\nLadka: Pehle network toh aane de, Google Maps khol raha hoon. 🌙📵😂",
    "Interviewer: Apni weakness batao.\nMain: Sach bolta hoon.\nInterviewer: Ye toh weakness nahi.\nMain: Mujhe aapki feelings ki parwah nahi. 😎😂",
    "Doctor: Aapko complete rest chahiye.\nMain: Doctor sahab, salary bhi complete chahiye phir. 💰😴😂",
    "Friend: Tera diet plan kaisa chal raha hai?\nMain: Bahut accha, kal samose ne mujhe cheat kiya. 🥟😂",
    "Maa: Sabzi laane gaya tha, itni der?\nBeta: Bhaav kam karwa raha tha.\nMaa: Kitne ka laya?\nBeta: ...double ka. 🛒😂",
    "GF: Tum mujhe kitna pyaar karte ho?\nBF: Itna ki phone ka 1% battery bhi tumse baat karne mein laga dunga. 🔋❤️😂",
    "Santa: Waiter, ye soup thanda hai.\nWaiter: Sir, ye lassi hai. 🥛😂",
    "Boss: Kal Sunday hai, aaram karo.\nMain: Sir aap mahaan ho!\nBoss: ...office mein aakar. 😭😂",
    "Pappu: Papa, school nahi jaana.\nPapa: Kyun?\nPappu: Bachche pareshaan karte hain.\nPapa: Tu principal hai, jaana padega! 🏫😂",
    "Ek aadmi gym gaya, trainer bola '3 mahine mein body ban jaayegi.'\nAadmi: '3 mahine? Tab tak toh shaadi ho jaayegi!' 💪😂",
    "Bachpan mein socha tha bada hokar settle ho jaunga.\nAb laptop ki battery settle ho jaye wahi badi baat hai. 💻😂",
    "Patni: Tumhe meri koi value hi nahi.\nPati: Hai na, tum meri 'high value' EMI ho. 😬💸😂",
    "Teacher: Homework kahan hai?\nStudent: Sir cloud pe save tha, baarish mein dho gaya. ☁️🌧️😂",
    "Main: Bhaiya 10 ka samosa dena.\nBhaiya: 15 ka hai.\nMain: Inflation toh chutney mein bhi aa gaya! 🥟😂",
    "Dost: Naya phone liya?\nMain: Haan, EMI pe.\nDost: Toh phone tera hua kahan?\nMain: Sahi pakde hain! 📱😂",
    "Ladka: Shaadi karoge mujhse?\nLadki: Salary kitni hai?\nLadka: Pyaar puchho na.\nLadki: Pyaar ka CTC bata. 💍😂",
    "Mummy: Beta sabzi mein namak theek hai?\nBeta: Haan, par sabzi kahan hai isme? 🍲😂",
]

# Bonus: desi shayari 🌹
SHAYARIS = [
    "Zindagi mein do cheezein kabhi mat todna —\nek bharosa, aur doosra Maggi banate waqt ka time. 🍜❤️",
    "Chai ki pyaali aur tumhari yaad,\ndono ke bina subah adhuri lagti hai. ☕✨",
    "Log kehte hain mehnat karo,\nhum kehte hain pehle thodi neend poori karo. 😴💪",
    "Dil toh bachcha hai ji,\nisliye har baar biryani dekhke macha leta hai. 🍛😄",
    "Dosti tumse hai, isliye life set hai,\nwarna duniya toh bas WiFi ke peeche bhaag rahi hai. 📶❤️",
    "Mohabbat aur Monday,\ndono hi bina permission ke aa jaate hain. 💔📅😅",
    "Tumhari ek smile ke liye,\nhum poori salary ka recharge bhi kar dein. 😄📱❤️",
    "Sapne wo nahi jo neend mein aaye,\nsapne wo hain jo EMI bhar ke bhi sukoon dein. 💸😴",
    "Pyaar ek chai jaisa hai —\nthoda meetha, thoda garam, aur biscuit ke bina adhura. ☕🍪",
    "Zindagi se shikayat nahi,\nbas weekend thoda lamba hona chahiye tha. 🛌😌",
    "Tum paas ho toh traffic bhi accha lagta hai,\naur tum door ho toh WiFi bhi slow lagta hai. 🚗📶❤️",
    "Khush raho itna,\nki tumhari hansi dekh ke duniya ka mood ban jaaye. 😊✨",
    "Raat ki chai aur dil ki baatein,\ndono late night mein hi acchi lagti hain. 🌙☕",
    "Manzil milegi zaroor,\nbas Google Maps thoda saath de de. 🗺️😄",
    "Pyaar wahi sachcha hai,\njo aapka last samosa bina maange de de. 🥟❤️",
]

# Meme subreddits for variety — every /meme can pull a different flavour.
MEME_SUBS = ["memes", "dankmemes", "wholesomememes", "funny", "meme", "ProgrammerHumor", "me_irl"]

# Joke "flavours" so the AI generates a different *type* each time.
JOKE_TYPES = [
    "a Santa-Banta joke", "a husband-wife (pati-patni) joke",
    "a teacher-student (Pappu) joke", "a boss-employee office joke",
    "a desi exam/student-life joke", "a food/Maggi/samosa joke",
    "a boyfriend-girlfriend joke", "a mummy-beta joke",
    "a relatable Indian middle-class joke", "a WiFi/mobile/EMI joke",
]

# Curated, VERIFIED desi facts (we don't AI-generate facts — those can be false).
DESI_FACTS = [
    "Chess (Chaturanga) ki shuruaat India mein hui thi! ♟️🇮🇳",
    "Zero aur decimal system India ne duniya ko diya — Aryabhata aur Brahmagupta. 0️⃣🧮",
    "India ke paas duniya ka sabse bada postal network hai. 📮",
    "Mawsynram, Meghalaya duniya ki sabse zyada baarish wali inhabited jagah hai. 🌧️",
    "'Shampoo' shabd Hindi 'champo' se aaya hai. 🧴",
    "Chandrayaan-1 (2008) ne Moon par paani ke proof dhoondhe the. 🌙🚀",
    "Yoga ki shuruaat India mein 5,000+ saal pehle hui thi. 🧘",
    "Varanasi duniya ke sabse purane lagataar basey shehron mein se ek hai. 🛕",
    "India mein 1,600+ se zyada bhashayein boli jaati hain. 🗣️",
    "Rupee ka symbol ₹ 2010 mein adopt hua tha. 💵",
    "Kumbh Mela itna bada hota hai ki ये space se bhi dikhta hai. 🛰️",
    "Chail, Himachal mein duniya ka sabse ooncha cricket ground hai. 🏏⛰️",
]

# Light, fun roasts (fallback when AI is off). {name} = target.
ROASTS = [
    "{name}, tum itne unique ho ki Google bhi 'did you mean someone else?' poochta hai. 😏",
    "{name}, tumhari speed dekh ke toh buffering bhi sharma jaaye. 🐢😂",
    "{name}, dimaag toh tumhare paas hai, bas abhi tak unbox nahi kiya. 📦😆",
    "{name}, tum WiFi ke jaise ho — kabhi connect, kabhi disappear. 📶😜",
    "{name}, aapki selfie aur expectations, dono thoda over-edited hain. 🤳😂",
]
COMPLIMENTS = [
    "{name}, tumhari smile kisi ke poore din ka mood bana sakti hai! 😊✨",
    "{name}, tum un logon mein se ho jinki energy room mein aate hi mehsoos hoti hai. 🌟",
    "{name}, dil bhi accha aur dimaag bhi tez — rare combo ho tum! 💖🧠",
    "{name}, tum jo bhi karte ho, usme ek alag hi spark hota hai. ⚡",
    "{name}, duniya ko tum jaise ache log hi behtar banate hain. 🙌❤️",
]


async def _get_json(url):
    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
        r = await client.get(url, headers={"Accept": "application/json"})
        r.raise_for_status()
        return r.json()


async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # If AI is available, generate a FRESH, unique Hinglish joke (~60% of the time)
    # — unlimited variety, never repeats. Otherwise use the big built-in list.
    if ai.is_enabled() and random.random() < 0.6:
        await context.bot.send_chat_action(update.effective_chat.id, "typing")
        prompt = (
            f"Write {random.choice(JOKE_TYPES)} in Hinglish (Hindi written in English letters, "
            "mixed with English). Keep it short (2-4 lines), original, clean and family-friendly. "
            "Add 1-2 emojis. Return ONLY the joke, no preamble."
        )
        out = await ai.ask(prompt, max_tokens=150, temperature=1.0)
        if out:
            await update.message.reply_text(f"😂 {out}")
            return
    await update.message.reply_text(f"😂 {random.choice(HINGLISH_JOKES)}")


async def shayari(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ai.is_enabled() and random.random() < 0.6:
        await context.bot.send_chat_action(update.effective_chat.id, "typing")
        prompt = (
            "Write a short, original 2-line desi shayari in Hinglish (Hindi in English letters). "
            "Make it witty/relatable (chai, dosti, pyaar, life, Monday vibes). Add 1-2 emojis. "
            "Return ONLY the shayari."
        )
        out = await ai.ask(prompt, max_tokens=120, temperature=1.0)
        if out:
            await update.message.reply_text(f"🌹 {out}")
            return
    await update.message.reply_text(f"🌹 {random.choice(SHAYARIS)}")


async def cricket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Live cricket scores. Uses CricketData.org if a free key is configured,
    otherwise points the user to live scores. Accurate, no fake data."""
    if not config.CRICKET_API_KEY:
        await update.message.reply_html(
            "🏏 <b>Live cricket scores</b> are ready to go!\n"
            "This feature just needs a <b>free</b> API key (https://cricketdata.org).\n"
            "Ask BLITEX to add it as <code>CRICKET_API_KEY</code> and scores appear here! 🔥\n\n"
            "For now: <a href=\"https://www.cricbuzz.com/cricket-match/live-scores\">Cricbuzz live scores</a> 📺"
        )
        return
    try:
        d = await _get_json(
            f"https://api.cricapi.com/v1/currentMatches?apikey={config.CRICKET_API_KEY}&offset=0"
        )
        # Handle API-level errors clearly (bad key, daily limit reached, etc.)
        if d.get("status") != "success":
            await update.message.reply_html(
                f"🏏 Cricket API error: <i>{d.get('status') or 'unknown'}</i>\n"
                "(Today's free request limit may be used up — try again tomorrow.)"
            )
            return
        matches = [m for m in d.get("data", []) if m.get("matchStarted") and not m.get("matchEnded")]
        if not matches:
            matches = d.get("data", [])[:3]
        if not matches:
            await update.message.reply_text("🏏 No live matches right now.")
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
            "🏏 Couldn't fetch scores right now. Try again shortly, or see "
            "<a href=\"https://www.cricbuzz.com/cricket-match/live-scores\">Cricbuzz</a>. 📺"
        )


async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search current matches by team name. Usage: /score India"""
    if not config.CRICKET_API_KEY:
        await update.message.reply_html(
            "🏏 This needs a free <code>CRICKET_API_KEY</code> (https://cricketdata.org)."
        )
        return
    if not context.args:
        await update.message.reply_text("Usage: /score <team>   e.g. /score India")
        return
    query = " ".join(context.args).lower()
    try:
        d = await _get_json(f"https://api.cricapi.com/v1/cricScore?apikey={config.CRICKET_API_KEY}")
        if d.get("status") != "success":
            await update.message.reply_html(
                f"🏏 Cricket API error: <i>{d.get('status') or 'unknown'}</i> "
                "(daily free limit may be reached)."
            )
            return
        data = d.get("data", [])
        hits = [m for m in data if query in f"{m.get('t1','')} {m.get('t2','')}".lower()]
        if not hits:
            await update.message.reply_text(
                f"🏏 No current matches found for “{query}”. Try a team like India, Mumbai, England…"
            )
            return
        lines = [f"🏏 <b>Matches: {query.title()}</b>\n"]
        for m in hits[:5]:
            lines.append(f"• <b>{m.get('t1','?')}</b> vs <b>{m.get('t2','?')}</b>")
            if m.get("t1s") or m.get("t2s"):
                lines.append(f"   {m.get('t1s','')}  |  {m.get('t2s','')}")
            if m.get("status"):
                lines.append(f"   <i>{m['status']}</i>")
        await update.message.reply_html("\n".join(lines))
    except Exception:
        await update.message.reply_text("🏏 Couldn't fetch scores right now. Try again shortly.")


async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        d = await _get_json("https://api.quotable.io/random")
        await update.message.reply_html(f"💬 <i>{d['content']}</i>\n\n— <b>{d['author']}</b>")
    except Exception:
        await update.message.reply_text("😅 Couldn't fetch a quote right now. Try again!")


async def fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 60% verified desi fact, else a random fact from the API. (No AI-made facts.)
    if random.random() < 0.6:
        await update.message.reply_text(f"🤓 Kya aapko pata tha?\n\n{random.choice(DESI_FACTS)}")
        return
    try:
        d = await _get_json("https://uselessfacts.jsph.pl/api/v2/facts/random?language=en")
        await update.message.reply_text(f"🤓 Did you know?\n\n{d['text']}")
    except Exception:
        await update.message.reply_text(f"🤓 Kya aapko pata tha?\n\n{random.choice(DESI_FACTS)}")


def _roast_target(update: Update):
    """Return (first_name, html_mention) — replied user, or the sender."""
    msg = update.effective_message
    if msg.reply_to_message and msg.reply_to_message.from_user:
        u = msg.reply_to_message.from_user
    else:
        u = update.effective_user
    return u.first_name, mention(u.id, u.first_name)


async def roast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name, mnt = _roast_target(update)
    if ai.is_enabled():
        await context.bot.send_chat_action(update.effective_chat.id, "typing")
        out = await ai.ask(
            f"Write a short, funny, light-hearted and CLEAN playful roast for a friend named "
            f"{name}, in Hinglish (Hindi in English letters). 1-2 lines, witty not offensive, "
            "no abuses. Add an emoji. Return ONLY the roast.",
            max_tokens=120, temperature=1.0,
        )
        if out:
            await update.message.reply_html(f"🔥 {mnt}, {out}")
            return
    await update.message.reply_html("🔥 " + random.choice(ROASTS).format(name=mnt))


async def compliment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name, mnt = _roast_target(update)
    if ai.is_enabled():
        await context.bot.send_chat_action(update.effective_chat.id, "typing")
        out = await ai.ask(
            f"Write a short, warm, genuine compliment for someone named {name}, in Hinglish "
            "(Hindi in English letters). 1-2 lines, sweet and uplifting. Add an emoji. "
            "Return ONLY the compliment.",
            max_tokens=120, temperature=1.0,
        )
        if out:
            await update.message.reply_html(f"💖 {mnt}, {out}")
            return
    await update.message.reply_html("💖 " + random.choice(COMPLIMENTS).format(name=mnt))


async def meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Pull from a random subreddit each time -> different *type* of meme.
    sub = random.choice(MEME_SUBS)
    for url in (f"https://meme-api.com/gimme/{sub}", "https://meme-api.com/gimme"):
        try:
            d = await _get_json(url)
            if d.get("url"):
                await update.message.reply_photo(d["url"], caption=f"😆 {d.get('title', '')}")
                return
        except Exception:
            continue
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
    app.add_handler(CommandHandler("roast", roast))
    app.add_handler(CommandHandler("compliment", compliment))
    app.add_handler(CommandHandler("cricket", cricket))
    app.add_handler(CommandHandler("score", score))
    app.add_handler(CommandHandler("quote", quote))
    app.add_handler(CommandHandler("fact", fact))
    app.add_handler(CommandHandler("meme", meme))
    app.add_handler(CommandHandler("dice", dice))
    app.add_handler(CommandHandler("dart", dart))
    app.add_handler(CommandHandler("coin", coin))
    app.add_handler(CommandHandler("8ball", eightball))
    app.add_handler(CommandHandler("quiz", quiz))
