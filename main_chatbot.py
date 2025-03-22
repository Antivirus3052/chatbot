import os
import logging
from dotenv import load_dotenv
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Logging einrichten
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Umgebungsvariablen laden
load_dotenv()
TELEGRAM_TOKEN = "8137401335:AAFgJwdbhW9H5sYYvdZZYVFjdttt662TGUY"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Gemini API konfigurieren
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro")

# Bot-Befehle
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bot-Begrüßung beim Start."""
    await update.message.reply_text(
        "Hallo! Ich bin dein Chatbot mit Gemini-Integration. Wie kann ich dir helfen?"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Hilfe-Befehl."""
    await update.message.reply_text(
        "Du kannst mir einfach Fragen stellen, und ich werde versuchen, dir mit Hilfe der Gemini AI zu antworten."
    )

# Nachrichtenbehandlung
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Beantwortet Benutzernachrichten mit Gemini."""
    message_text = update.message.text
    chat_id = update.effective_chat.id
    
    # Schreib-Status senden
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    try:
        # Antwort von Gemini generieren
        response = model.generate_content(message_text)
        reply_text = response.text
        
        # Antwort senden (in mehreren Teilen, falls zu lang)
        if len(reply_text) <= 4096:
            await update.message.reply_text(reply_text)
        else:
            # Nachricht in Teile aufteilen, wenn sie zu lang ist
            for i in range(0, len(reply_text), 4096):
                await update.message.reply_text(reply_text[i:i+4096])
    
    except Exception as e:
        logger.error(f"Fehler bei der Gemini-Anfrage: {e}")
        await update.message.reply_text(
            "Entschuldigung, ich konnte keine Antwort generieren. Bitte versuche es später noch einmal."
        )

# Hauptfunktion
def main() -> None:
    """Startet den Bot."""
    # Bot-Anwendung erstellen
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Befehlshandler hinzufügen
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Nachrichtenhandler hinzufügen
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Bot starten
    application.run_polling()
    logger.info("Bot gestartet")

if __name__ == "__main__":
    main()