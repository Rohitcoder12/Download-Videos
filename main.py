import os
import logging
from downloader import download_video
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ChatAction

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DUMP_CHANNEL = os.environ.get("DUMP_CHANNEL")  # Channel ID like -1001234567890

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 Send me any video URL to download it.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    await update.message.chat.send_action(action=ChatAction.TYPING)
    msg = await update.message.reply_text("⏬ Downloading...")

    result = download_video(url)
    if not result:
        await msg.edit_text("❌ Failed to download video.")
        return

    video_path, thumbnail_path, title = result

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Downloaded", url=url)]
    ])

    caption = f"🎞️ *{title}*\n📤 Uploaded via bot."

    try:
        await context.bot.send_video(
            chat_id=update.effective_chat.id,
            video=open(video_path, 'rb'),
            thumb=open(thumbnail_path, 'rb') if thumbnail_path else None,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        # Upload to dump channel
        await context.bot.send_video(
            chat_id=DUMP_CHANNEL,
            video=open(video_path, 'rb'),
            caption=f"👤 From: {update.effective_user.mention_html()}",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error uploading: {e}")
        logger.error(e)
    finally:
        os.remove(video_path)
        if thumbnail_path:
            os.remove(thumbnail_path)

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == "__main__":
    main()
