# bot.py

import os
import logging
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- Get configuration from Environment Variables ---
# This is the standard way to handle secrets in cloud deployments.
# We add a fallback value for local testing, but Koyeb will provide the real values.
BOT_TOKEN = os.getenv("BOT_TOKEN")
try:
    DUMB_CHANNEL_ID = int(os.getenv("DUMB_CHANNEL_ID"))
except (TypeError, ValueError):
    # Handle case where the environment variable is not set or is not a valid integer
    DUMB_CHANNEL_ID = None

# --- Basic Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! 👋",
        reply_markup=None,
    )
    await update.message.reply_text(
        "I am an educational video downloader. Send me a link from a supported platform."
    )

# --- Main Message Handler ---

async def handle_video_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles video links sent by the user."""
    url = update.message.text
    
    # Send a "processing" message
    processing_message = await update.message.reply_text("⏳ Processing your link... Please wait.")
    
    # Use a temporary directory for downloads that is cleaned up automatically
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

        # --- 1. Extract Info without Downloading ---
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            video_title = info_dict.get('title', 'No Title')
            video_id = info_dict.get('id', None)
            video_ext = info_dict.get('ext', 'mp4')
            video_duration = info_dict.get('duration', 0)
            thumbnail_url = info_dict.get('thumbnail', None)
            uploader = info_dict.get('uploader', 'N/A')

        video_filename = os.path.join(temp_dir, f"{video_id}.{video_ext}")

        # --- 2. Download the Video ---
        await processing_message.edit_text(f"📥 Downloading: *{video_title}*")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not os.path.exists(video_filename):
            raise FileNotFoundError("Downloaded video file not found.")

        # --- 3. Prepare Caption and Thumbnail ---
        caption = (
            f"🎬 **Title:** {video_title}\n"
            f"👤 **Uploader:** {uploader}\n"
            f"⏱ **Duration:** {video_duration // 60}:{video_duration % 60:02d}\n"
            f"🔗 **Source:** [Link]({url})"
        )
        
        thumb_path = None
        if thumbnail_url:
            thumb_path = os.path.join(temp_dir, f"{video_id}.jpg")
            with yt_dlp.YoutubeDL({'outtmpl': thumb_path, 'quiet': True, 'noplaylist': True}) as ydl_thumb:
                ydl_thumb.download([thumbnail_url])
            if not os.path.exists(thumb_path):
                thumb_path = None

        # --- 4. Upload to Dumb Channel ---
        await processing_message.edit_text("📤 Uploading to channel...")
        
        with open(video_filename, 'rb') as video_file:
            thumb_to_upload = open(thumb_path, 'rb') if thumb_path else None
            
            await context.bot.send_video(
                chat_id=DUMB_CHANNEL_ID,
                video=video_file,
                caption=caption,
                parse_mode='Markdown',
                duration=int(video_duration),
                thumbnail=thumb_to_upload
            )
            
            if thumb_to_upload:
                thumb_to_upload.close()

        # --- 5. Final Notification ---
        await processing_message.edit_text("✅ Done! Your video has been saved to the channel.")
        
    except Exception as e:
        logger.error(f"Error processing {url}: {e}")
        await processing_message.edit_text(f"❌ An error occurred. Please check the logs.")
    finally:
        # --- 6. Cleanup ---
        # Clean up local files and directories to keep the container clean
        if os.path.exists(temp_dir):
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)


def main() -> None:
    """Start the bot."""
    if not all([BOT_TOKEN, DUMB_CHANNEL_ID]):
        logger.error("FATAL: BOT_TOKEN or DUMB_CHANNEL_ID environment variables are not set.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Entity("url"), handle_video_link))

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot is starting...")
    application.run_polling()


if __name__ == '__main__':
    main()