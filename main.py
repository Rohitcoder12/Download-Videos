import os
import yt_dlp
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import logging

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION FROM ENVIRONMENT VARIABLES ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
DUMP_CHANNEL_ID = os.environ.get('DUMP_CHANNEL_ID')
APP_NAME = os.environ.get('RENDER_APP_NAME')
PORT = int(os.environ.get('PORT', '8443'))

# --- BOT FUNCTIONS ---

def start(update, context):
    update.message.reply_text("Hi! Send me a YouTube link. I will archive it and forward a copy to you.")

def process_video_link(update, context):
    message = update.message
    link = message.text
    user_chat_id = update.effective_chat.id

    if 'youtube.com' not in link and 'youtu.be' not in link:
        message.reply_text("Sorry, I can only process links from YouTube for educational purposes.")
        return

    processing_msg = None
    video_filename = None
    thumbnail_filename = None

    try:
        processing_msg = message.reply_text("✅ Link received. Processing video...")

        ydl_opts = {
            'format': 'best[ext=mp4][height<=720]/best[ext=mp4]/best',
            'outtmpl': '/tmp/%(id)s.%(ext)s',
            'writethumbnail': True,
            'noplaylist': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(link, download=True)
            video_id = info_dict.get('id', None)
            video_title = info_dict.get('title', "No Title")
            video_duration = info_dict.get('duration', None)
            video_filename = f"/tmp/{video_id}.mp4"
            
            if os.path.exists(f"/tmp/{video_id}.webp"):
                thumbnail_filename = f"/tmp/{video_id}.webp"
            elif os.path.exists(f"/tmp/{video_id}.jpg"):
                thumbnail_filename = f"/tmp/{video_id}.jpg"

        processing_msg.edit_text("📥 Download complete. Uploading...")
        
        caption = f"🎬 **Title:** {video_title}\n\n🔗 **Source:** [Link]({link})"

        with open(video_filename, 'rb') as video_file:
            if thumbnail_filename and os.path.exists(thumbnail_filename):
                with open(thumbnail_filename, 'rb') as thumb_file:
                    sent_message = context.bot.send_video(
                        chat_id=DUMP_CHANNEL_ID, video=video_file, thumb=thumb_file,
                        caption=caption, duration=video_duration, parse_mode=telegram.ParseMode.MARKDOWN
                    )
            else:
                sent_message = context.bot.send_video(
                    chat_id=DUMP_CHANNEL_ID, video=video_file,
                    caption=caption, duration=video_duration, parse_mode=telegram.ParseMode.MARKDOWN
                )

        processing_msg.edit_text("✅ Archive complete. Forwarding...")
        context.bot.forward_message(
            chat_id=user_chat_id,
            from_chat_id=DUMP_CHANNEL_ID,
            message_id=sent_message.message_id
        )
        processing_msg.edit_text("✅ Process complete!")

    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        if processing_msg:
            processing_msg.edit_text(f"❌ An error occurred. Check logs.")

    finally:
        if video_filename and os.path.exists(video_filename):
            os.remove(video_filename)
        if thumbnail_filename and os.path.exists(thumbnail_filename):
            os.remove(thumbnail_filename)

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, process_video_link))

    webhook_url = f"https://{APP_NAME}.onrender.com/{BOT_TOKEN}"
    logger.info(f"Setting webhook to {webhook_url}")
    
    updater.start_webhook(listen="0.0.0.0",
                          port=PORT,
                          url_path=BOT_TOKEN,
                          webhook_url=webhook_url)

    updater.idle()

if __name__ == '__main__':
    main()