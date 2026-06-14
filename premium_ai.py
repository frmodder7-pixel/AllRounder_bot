"""Premium AI commands: image generation, writing tools, captions, polls."""
from io import BytesIO

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from PIL import Image

import ai
import config
from utils import admin_only


def _args(context: ContextTypes.DEFAULT_TYPE) -> str:
    return " ".join(context.args or []).strip()


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


async def sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = _args(context)
    if not prompt:
        await update.message.reply_text("Usage: /sticker cute desi chai cup smiling")
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
    app.add_handler(CommandHandler("caption", caption))
    app.add_handler(CommandHandler("bio", bio))
    app.add_handler(CommandHandler("rewrite", rewrite))
    app.add_handler(CommandHandler("announce", announce))
    app.add_handler(CommandHandler("smartannounce", smart_announce))
    app.add_handler(CommandHandler("pollidea", pollidea))
    app.add_handler(CommandHandler("logoidea", logoidea))
    app.add_handler(CommandHandler("stickeridea", stickeridea))
