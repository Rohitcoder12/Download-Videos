import os
import yt_dlp
from fastapi import FastAPI, Request
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.ext import AIORateLimiter
from telegram.ext import Defaults
from telegram.ext import WebhookHandler

# ENV VARS
BOT_TOKEN = os.environ["BOT_TOKEN"]
DUMP_CHANNEL_ID = os.environ["DUMP_CHANNEL_ID"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]  # full URL like https://<koyeb-app>.koyeb.app/webhook

app = FastAPI()
application = None

YDL_OPTS = {
    'format': 'bestvideo+bestaudio/best',
    'outtmpl': 'downloads/%(title).100s.%(ext)s',
    'writethumbnail': True,
    'writeinfojson': False,
    'postprocessors': [
        {'key': 'EmbedThumbnail'},
        {'key': 'FFmpegMetadata'}
    ],
    'quiet': True
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send me a video URL.")

async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url.startswith("http"):
        await update.message.reply_text("Please send a valid URL.")
        return

    await update.message.reply_text("⏬ Downloading...")

    try:
        os.makedirs('downloads', exist_ok=True)

        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            thumbnail_path = filename.rsplit(".", 1)[0] + ".jpg"
            title = info.get("title", "Video")

        caption = f"🎬 <b>{title}</b>\n🔗 {url}"

        if os.path.getsize(filename) < 50 * 1024 * 1024:
            with open(filename, 'rb') as video, \
                 open(thumbnail_path, 'rb') if os.path.exists(thumbnail_path) else None as thumb:
                await update.message.reply_video(video=video, caption=caption, parse_mode="HTML", thumbnail=thumb)
                await context.bot.send_video(DUMP_CHANNEL_ID, video=video, caption=caption, parse_mode="HTML", thumbnail=thumb)
        else:
            await update.message.reply_text("⚠️ File too large for Telegram.")

        os.remove(filename)
        if os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

@app.on_event("startup")
async def on_startup():
    global application
    application = Application.builder()\
        .token(BOT_TOKEN)\
        .defaults(Defaults(parse_mode="HTML"))\
        .rate_limiter(AIORateLimiter())\
        .build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download))

    webhook_url = f"{WEBHOOK_URL}/webhook"
    await application.bot.set_webhook(webhook_url)
    print("🔗 Webhook set:", webhook_url)

@app.post("/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, application.bot)
