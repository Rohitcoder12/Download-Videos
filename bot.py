# bot.py

import os
import logging
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- Step 1: Configuration from Environment Variables ---
# These are provided by the Koyeb dashboard.

# Your bot's secret token.
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Your private channel's ID. We use a try-except block for safety.
try:
    DUMB_CHANNEL_ID = int(os.getenv("DUMB_CHANNEL_ID"))
except (TypeError, ValueError):
    DUMB_CHANNEL_ID = None

# These are automatically provided by Koyeb for a Web Service.
KOYEB_PUBLIC_URL = os.getenv("KOYEB_PUBLIC_URL")
PORT = int(os.getenv("PORT", "8000")) # Default to 8000 for local testing

# We use the bot token as a secret path to prevent unauthorized access to our webhook.
SECRET_PATH = BOT_TOKEN
WEBHOOK_URL = f"{KOYEB_PUBLIC_URL}/{SECRET_PATH}"

# --- Basic Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Command & Message Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! 👋",
        reply_markup=None,
    )
    await update.message.reply_text(
        "I am an educational video downloader running in webhook mode. Send me a link from a supported platform."
    )

async def handle_video_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles video links sent by the user."""
    url = update.message.text
    processing_message = await update.message.reply_text("⏳ Processing your link... Please wait.")
    
    # Use a temporary directory for each download to keep the server clean.
    temp_dir = f"temp_{update.update_id}"
    os.makedirs(temp_dir, exist_ok=True)
    video_path_template = os.path.join(temp_dir, '%(id)s.%(ext)s')

    try:
        # --- yt-dlp Options ---
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': video_path_template,
            'noplaylist': True,
            'quiet': True,
            'merge_output_format': 'mp4'
        }

        # --- 1. Extract Info ---
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            video_title = info_dict.get('title', 'No Title')
            video_id = info_dict.get('id', None)
            video_ext = info_dict.get('ext', 'mp4')
            video_duration = info_dict.get('duration', 0)
            thumbnail_url = info_dict.get('thumbnail', None)
            uploader = info_dict.get('uploader', 'N/A')

        video_filename = os.path.join(temp_dir, f"{video_id}.{video_ext}")

        # --- 2. Download Video ---
        await processing_message.edit_text(f"📥 Downloading: *{video_title}*")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not os.path.exists(video_filename):
            raise FileNotFoundError("Downloaded video file not found.")

        # --- 3. Prepare Caption & Thumbnail ---
        caption = (f"🎬 **Title:** {video_title}\n" f"👤 **Uploader:** {uploader}\n" f"⏱ **Duration:** {video_duration // 60}:{video_duration % 60:02d}\n" f"🔗 **Source:** [Link]({url})")
        
        thumb_path = None
        if thumbnail_url:
            thumb_path = os.path.join(temp_dir, f"{video_id}.jpg")
            with yt_dlp.YoutubeDL({'outtmpl': thumb_path, 'quiet': True, 'noplaylist': True}) as ydl_thumb:
                ydl_thumb.download([thumbnail_url])
            if not os.path.exists(thumb_path):
                thumb_path = None

        # --- 4. Upload to Channel ---
        await processing_message.edit_text("📤 Uploading to channel...")
        with open(video_filename, 'rb') as video_file:
            thumb_to_upload = open(thumb_path, 'rb') if thumb_path else None
            await context.bot.send_video(chat_id=DUMB_CHANNEL_ID, video=video_file, caption=caption, parse_mode='Markdown', duration=int(video_duration), thumbnail=thumb_to_upload)
            if thumb_to_upload: thumb_to_upload.close()

        # --- 5. Final Notification ---
        await processing_message.edit_text("✅ Done! Your video has been saved to the channel.")

    except Exception as e:
        logger.error(f"Error processing {url}: {e}")
        await processing_message.edit_text(f"❌ An error occurred. Please check the logs.")

    finally:
        # --- 6. Cleanup ---
        if os.path.exists(temp_dir):
            for file in os.listdir(temp_dir):
                try:
                    os.remove(os.path.join(temp_dir, file))
                except OSError as e:
                    logger.error(f"Error removing file {file}: {e}")
            os.rmdir(temp_dir)

def main() -> None:
    """Start the bot in webhook mode."""
    # This check is crucial. It ensures the app doesn't start without its configuration.
    if not all([BOT_TOKEN, DUMB_CHANNEL_ID, KOYEB_PUBLIC_URL]):
        logger.error("FATAL: One or more environment variables are not set. Check BOT_TOKEN, DUMB_CHANNEL_ID, and ensure the service type is Web Service for KOYEB_PUBLIC_URL.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Entity("url"), handle_video_link))

    # Set up and run the webhook server
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