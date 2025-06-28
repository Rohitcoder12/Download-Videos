import os
import yt_dlp
import uuid
import shutil
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, CallbackQueryHandler, filters
)
from fastapi import FastAPI, Request

BOT_TOKEN = os.getenv("BOT_TOKEN")
DUMP_CHANNEL = os.getenv("DUMP_CHANNEL")  # e.g., "@your_channel"

# --- FastAPI App for webhook ---
app = FastAPI()
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()


# Helper: Get metadata (thumbnail, title) without downloading full video
def get_video_info(url):
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'forcejson': True,
        'noplaylist': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            "title": info.get("title", "Untitled"),
            "thumbnail": info.get("thumbnail"),
            "url": url,
        }


# Command: /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send me a video link from Instagram, Pinterest, etc.")


# Handle user messages (URLs)
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    try:
        info = get_video_info(url)
        title = info['title']
        thumbnail_url = info['thumbnail']

        # Save URL in callback data (UUID as key)
        callback_id = str(uuid.uuid4())
        context.chat_data[callback_id] = url

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 Download Now", callback_data=callback_id)]
        ])

        await update.message.reply_photo(
            photo=thumbnail_url,
            caption=f"🎬 *{title}*\n\nPress the button below to download.",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Could not fetch video info.\n{str(e)}")


# Handle button click (download + send to user + dump)
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    callback_id = query.data
    url = context.chat_data.get(callback_id)

    if not url:
        await query.edit_message_caption("❌ Error: URL not found.")
        return

    await query.edit_message_caption("⏬ Downloading...")

    temp_dir = f"downloads/{uuid.uuid4()}"
    os.makedirs(temp_dir, exist_ok=True)
    out_template = os.path.join(temp_dir, "%(title).30s.%(ext)s")

    try:
        ydl_opts = {
            "outtmpl": out_template,
            "format": "bestvideo+bestaudio/best",
            "quiet": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url)
            filename = ydl.prepare_filename(info)

        # Send to user
        with open(filename, "rb") as f:
            await query.message.reply_video(f, caption=f"✅ Downloaded: {info['title']}")

        # Send to dump channel
        with open(filename, "rb") as f:
            await context.bot.send_video(chat_id=DUMP_CHANNEL, video=f, caption=f"📥 {info['title']}")

        await query.edit_message_caption("✅ Sent to you and dump channel.")

    except Exception as e:
        await query.edit_message_caption(f"❌ Download failed: {str(e)}")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# Register handlers
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
telegram_app.add_handler(CallbackQueryHandler(button_handler))


# FastAPI route for webhook
@app.post("/webhook")
async def telegram_webhook(update: dict):
    telegram_update = Update.de_json(update, telegram_app.bot)
    await telegram_app.process_update(telegram_update)
    return {"ok": True}


@app.on_event("startup")
async def on_startup():
    webhook_url = os.getenv("WEBHOOK_URL")
    if webhook_url:
        await telegram_app.bot.set_webhook(url=f"{webhook_url}/webhook")
