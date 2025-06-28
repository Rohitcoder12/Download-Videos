# bot.py

import os
import logging
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import BOT_TOKEN, DUMB_CHANNEL_ID

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
        "Send me a link to a video from a supported platform, and I'll download it for you."
    )

# --- Main Message Handler ---

async def handle_video_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles video links sent by the user."""
    url = update.message.text
    user_id = update.effective_user.id
    
    # Send a "processing" message
    processing_message = await update.message.reply_text("⏳ Processing your link... Please wait.")

    try:
        # --- yt-dlp Options ---
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': '%(id)s.%(ext)s', # Output filename template
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

        video_filename = f"{video_id}.{video_ext}"

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
        
        # Download thumbnail to a file if it exists
        thumb_path = None
        if thumbnail_url:
            thumb_path = f"{video_id}.jpg"
            # Using yt-dlp to download the thumbnail to avoid another dependency like requests
            with yt_dlp.YoutubeDL({'outtmpl': thumb_path, 'quiet': True}) as ydl_thumb:
                ydl_thumb.download([thumbnail_url])
            if not os.path.exists(thumb_path):
                thumb_path = None # Failed to download

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

        # --- 5. Final Notification and Cleanup ---
        await processing_message.edit_text("✅ Done! Your video has been saved to the channel.")
        
        # Clean up local files
        if os.path.exists(video_filename):
            os.remove(video_filename)
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)

    except Exception as e:
        logger.error(f"Error processing {url}: {e}")
        await processing_message.edit_text(f"❌ An error occurred: {e}")
        # Clean up if a file was partially downloaded
        if 'video_filename' in locals() and os.path.exists(video_filename):
            os.remove(video_filename)


def main() -> None:
    """Start the bot."""
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_video_link))

    # Run the bot until the user presses Ctrl-C
    print("Bot is running...")
    application.run_polling()


if __name__ == '__main__':
    main()
