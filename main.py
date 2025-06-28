import os
import yt_dlp
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DUMP_CHANNEL_ID = os.environ.get("DUMP_CHANNEL_ID")

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
    await update.message.reply_text("Send me a video URL, and I’ll fetch it.")

async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url.startswith("http"):
        await update.message.reply_text("Please send a valid video URL.")
        return

    await update.message.reply_text("Downloading...")

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
            await update.message.reply_text("File too large for Telegram.")

        os.remove(filename)
        if os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)

    except Exception as e:
        await update.message.reply_text(f"Download failed: {e}")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download))
    app.run_polling()

if __name__ == "__main__":
    main()
