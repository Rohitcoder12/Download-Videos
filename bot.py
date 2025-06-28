# bot.py (Diagnostic Version)

import os
import logging
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- Configuration Section (No changes here) ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
try:
    DUMB_CHANNEL_ID = int(os.getenv("DUMB_CHANNEL_ID"))
except (TypeError, ValueError):
    DUMB_CHANNEL_ID = None

KOYEB_PUBLIC_URL = os.getenv("KOYEB_PUBLIC_URL")
PORT = int(os.getenv("PORT", "8000"))
SECRET_PATH = BOT_TOKEN
WEBHOOK_URL = f"{KOYEB_PUBLIC_URL}/{SECRET_PATH}" if KOYEB_PUBLIC_URL and SECRET_PATH else None

# --- Logging (No changes here) ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# --- Handlers (start, handle_video_link) - No changes here ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(rf"Hi {user.mention_html()}! 👋")
    await update.message.reply_text("I am an educational video downloader. Send me a link.")

async def handle_video_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # This function is not the problem, it remains the same.
    url = update.message.text
    processing_message = await update.message.reply_text("⏳ Processing your link...")
    temp_dir = f"temp_{update.update_id}"
    os.makedirs(temp_dir, exist_ok=True)
    video_path_template = os.path.join(temp_dir, '%(id)s.%(ext)s')
    try:
        ydl_opts = {'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', 'outtmpl': video_path_template, 'noplaylist': True, 'quiet': True, 'merge_output_format': 'mp4'}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl: info_dict = ydl.extract_info(url, download=False)
        video_title, video_id, video_ext, video_duration, thumbnail_url, uploader = info_dict.get('title', 'No Title'), info_dict.get('id'), info_dict.get('ext', 'mp4'), info_dict.get('duration', 0), info_dict.get('thumbnail'), info_dict.get('uploader', 'N/A')
        video_filename = os.path.join(temp_dir, f"{video_id}.{video_ext}")
        await processing_message.edit_text(f"📥 Downloading: *{video_title}*")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])
        if not os.path.exists(video_filename): raise FileNotFoundError("Downloaded video file not found.")
        caption = (f"🎬 **Title:** {video_title}\n" f"👤 **Uploader:** {uploader}\n" f"⏱ **Duration:** {video_duration // 60}:{video_duration % 60:02d}\n" f"🔗 **Source:** [Link]({url})")
        thumb_path = None
        if thumbnail_url:
            thumb_path = os.path.join(temp_dir, f"{video_id}.jpg")
            with yt_dlp.YoutubeDL({'outtmpl': thumb_path, 'quiet': True, 'noplaylist': True}) as ydl_thumb: ydl_thumb.download([thumbnail_url])
            if not os.path.exists(thumb_path): thumb_path = None
        await processing_message.edit_text("📤 Uploading to channel...")
        with open(video_filename, 'rb') as video_file:
            thumb_to_upload = open(thumb_path, 'rb') if thumb_path else None
            await context.bot.send_video(chat_id=DUMB_CHANNEL_ID, video=video_file, caption=caption, parse_mode='Markdown', duration=int(video_duration), thumbnail=thumb_to_upload)
            if thumb_to_upload: thumb_to_upload.close()
        await processing_message.edit_text("✅ Done! Your video has been saved to the channel.")
    except Exception as e:
        logger.error(f"Error processing {url}: {e}")
        await processing_message.edit_text(f"❌ An error occurred.")
    finally:
        if os.path.exists(temp_dir):
            for file in os.listdir(temp_dir):
                try: os.remove(os.path.join(temp_dir, file))
                except OSError as e: logger.error(f"Error removing file {file}: {e}")
            os.rmdir(temp_dir)


def main() -> None:
    """Start the bot and run DIAGNOSTICS."""

    # =================================================================
    # --- NEW DIAGNOSTIC CODE ---
    # This block will print the exact values the script sees.
    logger.info("--- STARTING DIAGNOSTIC CHECK ---")
    
    # We check each variable and log what we find.
    token_from_env = os.getenv("BOT_TOKEN")
    channel_id_from_env = os.getenv("DUMB_CHANNEL_ID")
    public_url_from_env = os.getenv("KOYEB_PUBLIC_URL")

    # We use "Exists" vs "MISSING" for the token to avoid printing the secret in logs.
    logger.info(f"Value of BOT_TOKEN: {'Exists' if token_from_env else '!!! IS MISSING !!!'}")
    logger.info(f"Value of DUMB_CHANNEL_ID: {channel_id_from_env}")
    logger.info(f"Value of KOYEB_PUBLIC_URL: {public_url_from_env}")
    
    logger.info("--- FINISHED DIAGNOSTIC CHECK ---")
    # =================================================================


    # Original check that causes the error
    if not all([BOT_TOKEN, DUMB_CHANNEL_ID, WEBHOOK_URL]):
        logger.error("FATAL: One or more environment variables are not set. Check BOT_TOKEN, DUMB_CHANNEL_ID, and ensure the service type is Web Service for KOYEB_PUBLIC_URL.")
        return

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Entity("url"), handle_video_link))

    logger.info(f"Attempting to set webhook for {WEBHOOK_URL}")
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        secret_token=SECRET_PATH,
        webhook_url=WEBHOOK_URL
    )

if __name__ == '__main__':
    main()