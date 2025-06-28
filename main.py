import os
import asyncio
import logging
import yt_dlp
import aiohttp

from fastapi import FastAPI, Request
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputFile
)
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram.error import RetryAfter

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ENV variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
DUMP_CHANNEL = os.getenv("DUMP_CHANNEL")  # e.g., '@yourchannel' or channel ID

# FastAPI app
app = FastAPI()

# Telegram bot application
telegram_app = Application.builder().token(BOT_TOKEN).build()

# Root endpoint for health check
@app.get("/")
def root():
    return {"status": "ok"}

# Webhook endpoint
@app.post("/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}


# --- Bot Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send me a video URL, and I’ll try to download it.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    url = query.data
    await handle_video_download(update, context, url, from_button=True)

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith("http"):
        await update.message.reply_text("Please send a valid URL.")
        return

    # Inline button
    buttons = [
        [InlineKeyboardButton("Download This Video", callback_data=url)]
    ]
    await update.message.reply_text(
        "Click below to confirm download:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def handle_video_download(update, context, url, from_button=False):
    chat = update.effective_chat
    message = update.callback_query.message if from_button else update.message

    try:
        await context.bot.send_chat_action(chat.id, ChatAction.UPLOAD_VIDEO)

        ydl_opts = {
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4',
            'merge_output_format': 'mp4',
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            title = info.get("title", "Downloaded Video")
            thumbnail_url = info.get("thumbnail")

        caption = f"🎬 <b>{title}</b>\n🔗 <code>{url}</code>"
        thumb_bytes = None

        # Fetch thumbnail
        if thumbnail_url:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(thumbnail_url) as resp:
                        if resp.status == 200:
                            thumb_bytes = await resp.read()
            except Exception as e:
                logger.warning(f"Thumbnail download failed: {e}")

        video_input = InputFile(file_path)

        await context.bot.send_video(
            chat_id=chat.id,
            video=video_input,
            caption=caption,
            parse_mode="HTML",
            thumbnail=InputFile.from_bytes(thumb_bytes, filename="thumb.jpg") if thumb_bytes else None
        )

        # Also upload to dump channel
        await context.bot.send_video(
            chat_id=DUMP_CHANNEL,
            video=InputFile(file_path),
            caption=caption,
            parse_mode="HTML",
            thumbnail=InputFile.from_bytes(thumb_bytes, filename="thumb.jpg") if thumb_bytes else None
        )

        os.remove(file_path)

    except Exception as e:
        logger.error(f"Download error: {e}")
        await message.reply_text("❌ Failed to download video. Make sure it's supported.")


# --- Register Handlers ---

telegram_app.add_handler(CommandHandler("start", start_command))
telegram_app.add_handler(CallbackQueryHandler(button_handler))
telegram_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_video))


# --- Startup Webhook Setup ---

@app.on_event("startup")
async def on_startup():
    webhook_url = os.getenv("WEBHOOK_URL")
    if webhook_url:
        for attempt in range(5):
            try:
                await telegram_app.bot.set_webhook(url=f"{webhook_url}/webhook")
                print(f"✅ Webhook set to: {webhook_url}/webhook")
                break
            except RetryAfter as e:
                wait_time = e.retry_after
                print(f"⏳ Rate limited. Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
            except Exception as ex:
                print(f"❌ Error setting webhook: {ex}")
                break

# Start bot in background
telegram_app.initialize()
asyncio.create_task(telegram_app.start())
