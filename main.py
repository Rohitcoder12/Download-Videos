from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes
import os
import asyncio

TOKEN = os.getenv("BOT_TOKEN")  # Set this in Koyeb's environment variables

app = FastAPI()

# Initialize the Telegram bot application
telegram_app: Application = ApplicationBuilder().token(TOKEN).build()

# --- Define Bot Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I'm alive and running on webhook via Koyeb 🚀")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Use /start to test this bot.")

# Add handlers to the Telegram app
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("help", help_command))

# --- FastAPI endpoint for Telegram webhook ---
@app.post("/webhook")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"status": "ok"}

# --- Start webhook setup when app launches ---
@app.on_event("startup")
async def on_startup():
    webhook_url = os.getenv("WEBHOOK_URL")  # Should be your Koyeb HTTPS endpoint
    if not webhook_url:
        raise ValueError("WEBHOOK_URL not set in environment variables.")

    await telegram_app.bot.set_webhook(url=f"{webhook_url}/webhook")
    print(f"Webhook set to: {webhook_url}/webhook ✅")

# --- Optional health check route ---
@app.get("/")
async def root():
    return {"message": "Bot is running!"}
