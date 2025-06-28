# bot.py (Webhook Version)

import os
import logging
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- Get configuration from Environment Variables ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
try:
    DUMB_CHANNEL_ID = int(os.getenv("DUMB_CHANNEL_ID"))
except (TypeError, ValueError):
    DUMB_CHANNEL_ID = None

# Koyeb provides the public URL and port for your web service
KOYEB_PUBLIC_URL = os.getenv("KOYEB_PUBLIC_URL")
# Koyeb provides the port to listen on. Default to 8000 for local testing.
PORT = int(os.getenv("PORT", "8000"))

# A secret path segment to ensure that only Telegram is calling our webhook
SECRET_PATH = BOT_TOKEN 
WEBHOOK_URL = f"{KOYEB_PUBLIC_URL}/{SECRET_PATH}"

# --- Basic Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Handlers (start, handle_video_link) remain exactly the same as before ---
# (Copy and paste your start and handle_video_link functions here. They don't need to change.)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(rf"Hi {user.mention_html()}! 👋")
    await update.message.reply_text("Webhook mode active. Send me a link to an educational video.")

async def handle_video_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # This entire function is identical to the one from the previous 'worker' example.
    # No changes are needed inside this function.
    url = update.message.text
    processing_message = await update.message.reply_text("⏳ Processing your link... Please wait.")
    temp_dir = f"temp_{update.update_id}"
    os.makedirs(temp_dir, exist_ok=True)
    video_path_template = os.path.join(temp_dir, '%(id)s.%(ext)s')
    try:
        ydl_opts = {'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', 'outtmpl': video_path_template, 'noplaylist': True, 'quiet': True, 'merge_output_format': 'mp4'}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            video_title = info_dict.get('title', 'No Title')
            video_id = info_dict.get('id', None)
            video_ext = info_dict.get('ext', 'mp4')
            video_duration = info_dict.get('duration', 0)
            thumbnail_url = info_dict.get('thumbnail', None)
            uploader = info_dict.get('uploader', 'N/A')
        video_filename = os.path.join(temp_dir, f"{video_id}.{video_ext}")
        await processing_message.edit_text(f"📥 Downloading: *{video_title}*")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        if not os.path.exists(video_filename):
            raise FileNotFoundError("Downloaded video file not found.")
        caption = (f"🎬 **Title:** {video_title}\n" f"👤 **Uploader:** {uploader}\n" f"⏱ **Duration:** {video_duration // 60}:{video_duration % 60:02d}\n" f"🔗 **Source:** [Link]({url})")
        thumb_path = None
        if thumbnail_url:
            thumb_path = os.path.join(temp_dir, f"{video_id}.jpg")
            with yt_dlp.YoutubeDL({'outtmpl': thumb_path, 'quiet': True, 'noplaylist': True}) as ydl_thumb:
                ydl_thumb.download([thumbnail_url])
            if not os.path.exists(thumb_path): thumb_path = None
        await processing_message.edit_text("📤 Uploading to channel...")
        with open(video_filename, 'rb') as video_file:
            thumb_to_upload = open(thumb_path, 'rb') if thumb_path else None
            await context.bot.send_video(chat_id=DUMB_CHANNEL_ID, video=video_file, caption=caption, parse_mode='Markdown', duration=int(video_duration), thumbnail=thumb_to_upload)
            if thumb_to_upload: thumb_to_upload.close()
        await processing_message.edit_text("✅ Done! Your video has been saved to the channel.")
    except Exception as e:
        logger.error(f"Error processing {url}: {e}")
        await processing_message.edit_text(f"❌ An error occurred. Please check the logs.")
    finally:
        if os.path.exists(temp_dir):
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)

# --- Main function to set up and run the bot ---
def main() -> None:
    """Start the bot in webhook mode."""
    if not all([BOT_TOKEN, DUMB_CHANNEL_ID, KOYEB_PUBLIC_URL]):
        logger.error("FATAL: Environment variables BOT_TOKEN, DUMB_CHANNEL_ID, or KOYEB_PUBLIC_URL are not set.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Entity("url"), handle_video_link))

    # Set up and run the webhook
    logger.info(f"Setting webhook for {WEBHOOK_URL}")
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        secret_token=SECRET_PATH,
        webhook_url=WEBHOOK_URL
    )
    logger.info(f"Bot is listening for webhooks on port {PORT}")


if __name__ == '__main__':
    main()