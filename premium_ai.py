"""Premium AI commands: image generation, writing tools, captions, polls."""
import asyncio
from io import BytesIO
from textwrap import wrap

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from PIL import Image, ImageDraw, ImageFont

import ai
import config
from utils import admin_only


def _args(context: ContextTypes.DEFAULT_TYPE) -> str:
    return " ".join(context.args or []).strip()


def _voice_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    text = _args(context)
    if text:
        return text
    src = update.message.reply_to_message
    if src:
        return (src.text or src.caption or "").strip()
    return ""


async def _ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str, max_tokens: int = 450, temperature: float = 0.8):
    if not ai.is_enabled():
        await update.message.reply_text("🧠 AI is disabled. Set GEMINI_API_KEY first.")
        return
    key = f"premium:{update.effective_chat.id}:{update.effective_user.id}"
    if not ai.allow_request(key, 5, 60):
        await update.message.reply_text("⏳ AI limit reached for a moment. Try again shortly.")
        return
    await context.bot.send_chat_action(update.effective_chat.id, "typing")
    out = await ai.ask(prompt, max_tokens=max_tokens, temperature=temperature)
    await update.message.reply_text(out or "AI did not answer right now. Try again in a moment.")


async def imagine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = _args(context)
    if not prompt:
        await update.message.reply_text("Usage: /imagine a premium logo for a cricket group, gold and black")
        return
    if not ai.is_enabled():
        await update.message.reply_text("Image generation needs GEMINI_API_KEY.")
        return
    if not ai.allow_request(f"image:{update.effective_chat.id}:{update.effective_user.id}", 2, 300):
        await update.message.reply_text("⏳ Image limit reached. Try again later.")
        return
    await context.bot.send_chat_action(update.effective_chat.id, "upload_photo")
    image = await ai.generate_image(
        "Create a polished, high-quality image for Telegram. Avoid text unless the user asks. "
        f"Prompt: {prompt}"
    )
    if not image:
        await update.message.reply_text(f"Couldn't generate image. Last error: {ai.last_error() or 'unknown'}")
        return
    data, mime_type = image
    ext = "jpg" if "jpeg" in mime_type else "png"
    bio = BytesIO(data)
    bio.name = f"generated.{ext}"
    await update.message.reply_photo(photo=bio, caption=f"🎨 {prompt[:900]}")


async def editimage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = _args(context)
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text("Reply to a photo with: /editimage make it cinematic")
        return
    if not prompt:
        await update.message.reply_text("Usage: reply to a photo with /editimage make it cinematic")
        return
    if not ai.is_enabled():
        await update.message.reply_text("Image editing needs GEMINI_API_KEY.")
        return
    if not ai.allow_request(f"image:{update.effective_chat.id}:{update.effective_user.id}", 2, 300):
        await update.message.reply_text("⏳ Image limit reached. Try again later.")
        return
    await context.bot.send_chat_action(update.effective_chat.id, "upload_photo")
    photo = update.message.reply_to_message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    data = await file.download_as_bytearray()
    image = await ai.edit_image(
        "Edit/restyle this image for Telegram. Keep it polished and high quality. "
        f"Instruction: {prompt}",
        bytes(data),
        "image/jpeg",
    )
    if not image:
        await update.message.reply_text(f"Couldn't edit image. Last error: {ai.last_error() or 'unknown'}")
        return
    out, mime_type = image
    ext = "jpg" if "jpeg" in mime_type else "png"
    bio = BytesIO(out)
    bio.name = f"edited.{ext}"
    await update.message.reply_photo(photo=bio, caption=f"🎨 {prompt[:900]}")


def _sticker_webp(image_bytes: bytes) -> BytesIO:
    img = Image.open(BytesIO(image_bytes)).convert("RGBA")
    img.thumbnail((512, 512), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    x = (512 - img.width) // 2
    y = (512 - img.height) // 2
    canvas.alpha_composite(img, (x, y))
    out = BytesIO()
    canvas.save(out, format="WEBP", lossless=True, quality=90, method=6)
    out.seek(0)
    out.name = "sticker.webp"
    return out


def _font(size: int, bold: bool = False):
    names = (
        "arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf",
    ) if bold else (
        "arial.ttf", "Arial.ttf", "DejaVuSans.ttf",
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _fit_lines(text: str, font, max_width: int, max_lines: int = 7) -> list[str]:
    words = text.replace("\n", " ").split()
    lines = []
    current = ""
    probe = Image.new("RGBA", (10, 10))
    draw = ImageDraw.Draw(probe)
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textbbox((0, 0), trial, font=font)[2] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and len(" ".join(words)) > len(" ".join(lines)):
        lines[-1] = lines[-1].rstrip(".") + "..."
    return lines


async def _profile_photo_bytes(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bytes | None:
    try:
        photos = await context.bot.get_user_profile_photos(user_id, limit=1)
        if not photos.total_count or not photos.photos:
            return None
        file = await context.bot.get_file(photos.photos[0][-1].file_id)
        return bytes(await file.download_as_bytearray())
    except Exception:
        return None


def _circle_avatar(photo_bytes: bytes | None, initials: str) -> Image.Image:
    size = 124
    avatar = Image.new("RGBA", (size, size), (67, 97, 238, 255))
    if photo_bytes:
        try:
            img = Image.open(BytesIO(photo_bytes)).convert("RGBA")
            img = img.resize((size, size), Image.Resampling.LANCZOS)
            avatar = img
        except Exception:
            pass
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(avatar, (0, 0), mask)
    if not photo_bytes:
        d = ImageDraw.Draw(out)
        f = _font(48, bold=True)
        label = initials[:2].upper() or "?"
        box = d.textbbox((0, 0), label, font=f)
        d.text(((size - (box[2] - box[0])) // 2, (size - (box[3] - box[1])) // 2 - 4), label, fill="white", font=f)
    return out


async def _quote_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    src = update.message.reply_to_message
    if not src or not (src.text or src.caption):
        return False
    user = src.from_user
    text = (src.text or src.caption or "").strip()
    photo = await _profile_photo_bytes(context, user.id) if user else None
    name = (user.first_name if user else "User")[:32]
    canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    card = Image.new("RGBA", (468, 420), (255, 255, 255, 242))
    mask = Image.new("L", card.size, 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, card.width - 1, card.height - 1), radius=42, fill=255)
    canvas.paste(card, (22, 46), mask)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((22, 46, 490, 466), radius=42, outline=(42, 52, 65, 255), width=4)
    avatar = _circle_avatar(photo, name)
    canvas.alpha_composite(avatar, (54, 76))
    name_font = _font(34, bold=True)
    text_font = _font(31, bold=True)
    small_font = _font(20)
    draw.text((198, 90), name, fill=(20, 27, 38, 255), font=name_font)
    draw.text((198, 132), "said", fill=(101, 116, 139, 255), font=small_font)
    lines = _fit_lines(text, text_font, 398, max_lines=7)
    y = 225
    for line in lines:
        box = draw.textbbox((0, 0), line, font=text_font)
        draw.text(((512 - (box[2] - box[0])) // 2, y), line, fill=(15, 23, 42, 255), font=text_font)
        y += 42
    draw.text((54, 426), f"{config.BRAND}", fill=(100, 116, 139, 255), font=small_font)
    out = BytesIO()
    canvas.save(out, format="WEBP", lossless=True, quality=92, method=6)
    out.seek(0)
    out.name = "quote_sticker.webp"
    try:
        await context.bot.send_sticker(update.effective_chat.id, sticker=out)
    except Exception:
        out.seek(0)
        await update.message.reply_document(document=out, caption="Text sticker generated as WebP.")
    return True


async def sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = _args(context)
    if update.message.reply_to_message and (update.message.reply_to_message.text or update.message.reply_to_message.caption):
        await context.bot.send_chat_action(update.effective_chat.id, "choose_sticker")
        await _quote_sticker(update, context)
        return
    if not prompt:
        await update.message.reply_text("Usage: /sticker cute desi chai cup smiling, or reply to text with /sticker")
        return
    if not ai.is_enabled():
        await update.message.reply_text("Sticker generation needs GEMINI_API_KEY.")
        return
    if not ai.allow_request(f"sticker:{update.effective_chat.id}:{update.effective_user.id}", 2, 300):
        await update.message.reply_text("⏳ Sticker limit reached. Try again later.")
        return
    await context.bot.send_chat_action(update.effective_chat.id, "choose_sticker")
    image = await ai.generate_image(
        "Create a Telegram sticker asset: centered subject, transparent or plain background, "
        "cute expressive style, high contrast, no tiny text. "
        f"Sticker idea: {prompt}"
    )
    if not image:
        await update.message.reply_text(f"Couldn't generate sticker. Last error: {ai.last_error() or 'unknown'}")
        return
    try:
        webp = _sticker_webp(image[0])
        await context.bot.send_sticker(update.effective_chat.id, sticker=webp)
    except Exception:
        webp = _sticker_webp(image[0])
        await update.message.reply_document(document=webp, caption="Sticker generated as WebP.")


async def voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = _voice_text(update, context)
    if not text:
        await update.message.reply_text("Usage: /voice your text, or reply to a text with /voice")
        return
    if len(text) > 900:
        text = text[:900]
    await context.bot.send_chat_action(update.effective_chat.id, "record_voice")
    try:
        from gtts import gTTS
        mp3 = BytesIO()
        await asyncio.to_thread(lambda: gTTS(text=text, lang="hi", tld="co.in").write_to_fp(mp3))
        mp3.seek(0)
        try:
            from pydub import AudioSegment
            ogg = BytesIO()
            audio = await asyncio.to_thread(lambda: AudioSegment.from_file(mp3, format="mp3"))
            await asyncio.to_thread(lambda: audio.export(ogg, format="ogg", codec="libopus"))
            ogg.seek(0)
            ogg.name = "voice.ogg"
            await context.bot.send_voice(update.effective_chat.id, voice=ogg)
            return
        except Exception:
            mp3.seek(0)
            mp3.name = "voice.mp3"
            await update.message.reply_audio(audio=mp3, title="Voice")
    except Exception as exc:
        await update.message.reply_text(f"Couldn't generate voice right now: {type(exc).__name__}")


async def caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = _args(context)
    if not topic and update.message.reply_to_message:
        topic = update.message.reply_to_message.text or update.message.reply_to_message.caption or ""
    if not topic:
        await update.message.reply_text("Usage: /caption your photo/topic")
        return
    await _ai_reply(
        update,
        context,
        "Write 5 premium Hinglish social media captions for this. Keep them short, stylish, and usable. "
        f"Topic: {topic[:1500]}",
        max_tokens=350,
        temperature=0.9,
    )


async def bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = _args(context) or update.effective_user.first_name
    await _ai_reply(
        update,
        context,
        "Write 5 stylish Telegram/Instagram bio options in Hinglish. Include attitude, warmth, and clean wording. "
        f"Person/theme: {topic[:1000]}",
        max_tokens=300,
        temperature=0.9,
    )


async def rewrite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = _args(context)
    if not text and update.message.reply_to_message:
        text = update.message.reply_to_message.text or update.message.reply_to_message.caption or ""
    if not text:
        await update.message.reply_text("Usage: /rewrite make this message premium")
        return
    await _ai_reply(
        update,
        context,
        "Rewrite this message in a clear, premium, friendly Hinglish style. Keep meaning same and avoid extra explanation.\n\n"
        f"{text[:2200]}",
        max_tokens=400,
        temperature=0.6,
    )


async def announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = _args(context)
    if not topic:
        await update.message.reply_text("Usage: /announce group quiz at 8 PM")
        return
    await _ai_reply(
        update,
        context,
        "Create a premium Telegram group announcement in Hinglish. Use a strong title, short body, and clear call to action. "
        f"Topic: {topic[:1200]}",
        max_tokens=350,
        temperature=0.8,
    )


async def pollidea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = _args(context) or "fun group engagement"
    await _ai_reply(
        update,
        context,
        "Create 3 Telegram poll ideas. For each, include question and 4 short options. Hinglish, fun, clean. "
        f"Theme: {topic[:1000]}",
        max_tokens=450,
        temperature=0.9,
    )


async def logoidea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = _args(context) or config.BRAND
    await _ai_reply(
        update,
        context,
        "Give 8 premium brand/logo ideas. Include name, color palette, icon concept, and tagline. "
        f"Brand/theme: {topic[:1000]}",
        max_tokens=500,
        temperature=0.85,
    )


async def stickeridea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = _args(context) or "desi Telegram group"
    await _ai_reply(
        update,
        context,
        "Give 10 funny Telegram sticker pack ideas in Hinglish. Keep each idea short and expressive. "
        f"Theme: {topic[:1000]}",
        max_tokens=350,
        temperature=1.0,
    )


@admin_only
async def smart_announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await announce(update, context)


def register(app: Application):
    app.add_handler(CommandHandler("imagine", imagine))
    app.add_handler(CommandHandler("editimage", editimage))
    app.add_handler(CommandHandler("sticker", sticker))
    app.add_handler(CommandHandler("voice", voice))
    app.add_handler(CommandHandler("caption", caption))
    app.add_handler(CommandHandler("bio", bio))
    app.add_handler(CommandHandler("rewrite", rewrite))
    app.add_handler(CommandHandler("announce", announce))
    app.add_handler(CommandHandler("smartannounce", smart_announce))
    app.add_handler(CommandHandler("pollidea", pollidea))
    app.add_handler(CommandHandler("logoidea", logoidea))
    app.add_handler(CommandHandler("stickeridea", stickeridea))
