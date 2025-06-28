import os
import logging
import asyncio
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.error import RetryAfter
from downloader import download_video  # Assume you have a separate module for downloading

BOT_TOKEN = os.getenv("BOT_TOKEN")
DUMP_CHANNEL = os.getenv("DUMP_CHANNEL")  # Channel ID to dump videos
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g., https://your-koyeb-app.koyeb.app

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Create bot application
telegram_app = Application.builder().token(BOT_TOKEN).build()
app = FastAPI()

# /start command
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send me a link and I’ll fetch the video with thumbnail, caption, and buttons.")

# Handle video request
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    chat_id = update.message.chat_id
    
    # Send placeholder message
    msg = await update.message.reply_text("⏳ Downloading... please wait")
    
    try:
        video_path, thumbnail_path, title = download_video(url)

        # Inline buttons
        buttons = [[InlineKeyboardButton("Source", url=url)]]
        reply_markup = InlineKeyboardMarkup(buttons)

        # Send to dump channel first
        dump_msg = await context.bot.send_video(
            chat_id=DUMP_CHANNEL,
            video=open(video_path, 'rb'),
            supports_streaming=True,
            caption=title or "Downloaded video",
            thumbnail=open(thumbnail_path, 'rb') if thumbnail_path else None
        )

        # Forward to user with buttons
        await context.bot.send_video(
            chat_id=chat_id,
            video=open(video_path, 'rb'),
            caption=title or "Here is your video",
            supports_streaming=True,
            thumbnail=open(thumbnail_path, 'rb') if thumbnail_path else None,
            reply_markup=reply_markup
        )

        await msg.delete()

    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        await msg.edit_text("❌ Failed to download the video.")

# Add handlers
telegram_app.add_handler(CommandHandler("start", start_command))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# FastAPI webhook route
@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.update_queue.put(update)
    return {"ok": True}

@app.on_event("startup")
async def on_startup():
    webhook_url = WEBHOOK_URL

    # Initialize and start application
    await telegram_app.initialize()
    await telegram_app.start()

    # Set webhook with retry logic
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
