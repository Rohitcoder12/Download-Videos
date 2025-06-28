import os
import logging
import asyncio

from fastapi import FastAPI, Request
from downloader import download_video
from telegram import InputFile, InlineKeyboardButton, InlineKeyboardMarkup, Update, ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.error import RetryAfter

# Load env
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
DUMP_CHANNEL = os.getenv("DUMP_CHANNEL")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI()

# Telegram bot app
telegram_app = Application.builder().token(BOT_TOKEN).build()

# Health check route
@app.get("/")
async def health():
    return {"status": "ok"}

# Webhook receiver
@app.post("/webhook")
async def receive_update(req: Request):
    data = await req.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}

# /start command
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 Send an adult site video URL to download it.")

# Button press handler
async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    url = query.data
    await query.answer()
    await ctx.bot.send_message(query.message.chat_id, f"Processing 👉 {url}")
    await process_download(query.message.chat_id, url, ctx)

# Message handler
async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.lower().startswith("http"):
        await update.message.reply_text("❌ Please send a valid URL.")
        return
    # Confirm with inline button
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Download", callback_data=url)]
    ])
    await update.message.reply_text("Click to download:", reply_markup=kb)

# Core download logic
async def process_download(chat_id, url, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await ctx.bot.send_message(chat_id, "⏳ Downloading...")
    await ctx.bot.send_chat_action(chat_id, ChatAction.UPLOAD_VIDEO)

    result = download_video(url)
    if not result:
        await msg.edit_text("❌ Failed to download video.")
        return
    file_path, title = result

    caption = f"🎥 <b>{title}</b>\n🔗 <code>{url}</code>"
    try:
        await ctx.bot.send_video(
            chat_id=chat_id,
            video=InputFile(file_path),
            caption=caption,
            parse_mode="HTML"
        )
        # Upload to dump channel
        await ctx.bot.send_video(
            chat_id=DUMP_CHANNEL,
            video=InputFile(file_path),
            caption=caption,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error("Upload failed: %s", e)
        await msg.edit_text("❌ Failed to send video.")
    finally:
        try:
            os.remove(file_path)
        except:
            pass

    await msg.delete()

# Register handlers
telegram_app.add_handler(CommandHandler("start", cmd_start))
telegram_app.add_handler(CallbackQueryHandler(on_callback))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

# Webhook setup on startup
@app.on_event("startup")
async def startup_bot():
    await telegram_app.initialize()
    await telegram_app.start()
    if WEBHOOK_URL:
        for _ in range(5):
            try:
                await telegram_app.bot.set_webhook(url=WEBHOOK_URL + "/webhook")
                logger.info("✅ Webhook set successfully.")
                break
            except RetryAfter as e:
                logger.warning(f"Rate limited. Retry in {e.retry_after}s")
                await asyncio.sleep(e.retry_after)
            except Exception as ex:
                logger.error("Webhook setup failed: %s", ex)
                break

    # Start polling fallback
    asyncio.create_task(telegram_app.updater.start_polling())

# Uvicorn runner
# Koyeb uses 'web: uvicorn main:app --host 0.0.0.0 --port 8080' in Procfile
