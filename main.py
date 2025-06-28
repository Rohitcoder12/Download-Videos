import os
import yt_dlp
import asyncio
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TELEGRAM_TOKEN = "YOUR_BOT_TOKEN"
DUMP_CHANNEL_ID = "@your_channel_username_or_channel_id"  # With @ or as int (like -1001234567890)

YDL_OPTS = {
    'format': 'bestvideo+bestaudio/best',
    'outtmpl': 'downloads/%(title)s.%(ext)s',
    'writethumbnail': True,
    'writeinfojson': True,
    'postprocessors': [
        {
            'key': 'EmbedThumbnail',
        },
        {
            'key': 'FFmpegMetadata'
        }
    ]
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send me a video URL and I'll download and send it to you.")

async def download_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url.startswith("http"):
        await update.message.reply_text("❌ Please send a valid URL.")
        return

    await update.message.reply_text("⏬ Downloading...")

    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            title = info.get("title", "Video")
            thumbnail_path = filename.rsplit(".", 1)[0] + ".jpg"

        # Check size
        file_size = os.path.getsize(filename)
        max_size = 50 * 1024 * 1024

        caption = f"🎬 <b>{title}</b>\n📥 Source: {url}"
        parse_mode = "HTML"

        if file_size <= max_size:
            with open(filename, 'rb') as video, open(thumbnail_path, 'rb') if os.path.exists(thumbnail_path) else None as thumb:
                thumb_file = InputFile(thumbnail_path) if os.path.exists(thumbnail_path) else None

                await update.message.reply_video(video=video, caption=caption, parse_mode=parse_mode, thumbnail=thumb_file)

                # Also send to dump channel
                await context.bot.send_video(
                    chat_id=DUMP_CHANNEL_ID,
                    video=video,
                    caption=caption,
                    parse_mode=parse_mode,
                    thumbnail=thumb_file
                )
        else:
            await update.message.reply_text("⚠️ File too big to send via Telegram (limit 50MB).")
        
        # Cleanup
        os.remove(filename)
        if os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

def main():
    os.makedirs("downloads", exist_ok=True)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_and_send))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
  
