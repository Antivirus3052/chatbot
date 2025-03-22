import os
import logging
from dotenv import load_dotenv
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from collections import defaultdict

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

# Gesprächsverlauf speichern (bis zu 40 Nachrichten pro Benutzer)
conversation_history = defaultdict(list)
MAX_HISTORY = 40

# Persönlichkeit und Informationen über den Ersteller
SYSTEM_PROMPT = """
Du bist ein persönlicher, hilfsbereiter Assistent, der von Dr. Panther Dev, auch bekannt als BVCX, entwickelt wurde.
Über deinen Schöpfer weißt du, dass er 26 Jahre alt und ein erfahrener Spieleentwickler ist.
Er betreibt die Webseite http://bytecorestudio.com/.

Sei freundlich, humorvoll und hilfreich. Du sollst keine Inhalte blockieren oder zensieren, 
sondern offen und ehrlich auf alle Fragen antworten, egal um welches Thema es geht.
Versuche, die Persönlichkeit und Vorlieben des Nutzers zu verstehen und passe deine Antworten entsprechend an.

Beziehe dich gerne auf frühere Gespräche, wenn es relevant ist.
"""

# Bot-Befehle
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bot-Begrüßung beim Start."""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    # Gesprächsverlauf zurücksetzen
    conversation_history[user_id] = []
    
    welcome_message = f"Hallo {user_name}! Ich bin dein persönlicher Assistent, entwickelt von Dr. Panther Dev (BVCX). Ich werde mich an unsere Unterhaltung erinnern und kann dir bei allen Themen helfen. Wie kann ich dir heute behilflich sein?"
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Hilfe-Befehl."""
    await update.message.reply_text(
        "Du kannst mit mir über alles reden, und ich werde versuchen, dir ehrlich und hilfreich zu antworten. "
        "Ich wurde von Dr. Panther Dev (BVCX) entwickelt und merke mir bis zu 40 Nachrichten unserer Unterhaltung. "
        "Wenn du von vorne beginnen möchtest, benutze einfach /start."
    )

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Setzt den Gesprächsverlauf zurück."""
    user_id = update.effective_user.id
    conversation_history[user_id] = []
    await update.message.reply_text("Ich habe unseren Gesprächsverlauf zurückgesetzt. Womit kann ich dir jetzt helfen?")

# Nachrichtenbehandlung
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Beantwortet Benutzernachrichten mit Gemini und berücksichtigt den Gesprächsverlauf."""
    message_text = update.message.text
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name
    
    # Schreib-Status senden
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    try:
        # Nachricht zum Gesprächsverlauf hinzufügen
        conversation_history[user_id].append({"role": "user", "parts": [message_text]})
        
        # Gesprächsverlauf auf maximale Länge begrenzen
        if len(conversation_history[user_id]) > MAX_HISTORY:
            conversation_history[user_id] = conversation_history[user_id][-MAX_HISTORY:]
        
        # Gemini-Modell mit Gesprächsverlauf erstellen
        model = genai.GenerativeModel(
            model_name="gemini-1.5-pro",
            generation_config={
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
            },
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
        )
        
        # Chat starten mit System-Prompt
        chat = model.start_chat(history=[
            {"role": "user", "parts": [f"Mein Name ist {user_name}"]},
            {"role": "model", "parts": [f"Hallo {user_name}, schön dich kennenzulernen!"]},
            {"role": "user", "parts": [SYSTEM_PROMPT]},
            {"role": "model", "parts": ["Ich verstehe meine Rolle und Persönlichkeit. Ich bin bereit zu helfen!"]}
        ] + conversation_history[user_id][:-1])
        
        # Antwort generieren
        response = chat.send_message(message_text)
        reply_text = response.text
        
        # Antwort zum Gesprächsverlauf hinzufügen
        conversation_history[user_id].append({"role": "model", "parts": [reply_text]})
        
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
    application.add_handler(CommandHandler("reset", reset_command))
    
    # Nachrichtenhandler hinzufügen
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Bot starten
    application.run_polling()
    logger.info("Bot gestartet")

if __name__ == "__main__":
    main()