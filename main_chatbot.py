import asyncio
import logging
import json
import os
import sys
from telethon import TelegramClient, events, errors
from telethon.tl import functions, types
from telethon.tl.types import User, Chat, Channel
import google.generativeai as genai
from datetime import datetime
import traceback
import time
import random

# Füge direkt nach den Imports folgende Zeilen ein
# Lade die Umgebungsvariablen aus der .env-Datei
def load_env_variables():
    env_path = '.env'
    env_vars = {}
    
    try:
        # Versuche, python-dotenv zu importieren und zu verwenden
        from dotenv import load_dotenv
        load_dotenv()
        import os
        return {"GEMINI_API_KEY": os.getenv("GEMINI_API_KEY")}
    except ImportError:
        # Falls python-dotenv nicht installiert ist, lade die .env-Datei manuell
        try:
            with open(env_path, 'r') as file:
                for line in file:
                    # Ignoriere Kommentare und leere Zeilen
                    if line.strip() and not line.strip().startswith('#') and '=' in line:
                        key, value = line.strip().split('=', 1)
                        # Entferne umschließende Anführungszeichen und Leerzeichen
                        env_vars[key.strip()] = value.strip().strip('"').strip("'")
            return env_vars
        except Exception as e:
            logger.error(f"Fehler beim Laden der .env-Datei: {e}")
            # Standard-API-Schlüssel als Fallback
            return {"GEMINI_API_KEY": "AIzaSyAt9GAr1tKVjccxuCV-dhgeZq0NNnJyZLM"}

# Lade die Umgebungsvariablen
env_vars = load_env_variables()
GEMINI_API_KEY = env_vars.get("GEMINI_API_KEY", "AIzaSyAt9GAr1tKVjccxuCV-dhgeZq0NNnJyZLM")

# Verbessere die Systemkonfiguration für Unicode-Handhabung
# Füge dies direkt unter den anderen Imports ein
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Erweiterte Konfiguration der Logging-Funktionalität
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("assistant.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MuslimAssistant:
    def __init__(self, telegram_api_id, telegram_api_hash, telegram_phone, gemini_api_key):
        # Telegram-Client Initialisierung
        self.client = None
        self.telegram_api_id = telegram_api_id
        self.telegram_api_hash = telegram_api_hash
        self.phone = telegram_phone
        
        # Gemini API Initialisierung
        self.gemini_api_key = gemini_api_key
        genai.configure(api_key=self.gemini_api_key)
        
        # Model-Konfiguration mit spezifischen Sicherheitseinstellungen
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 4096,
        }
        
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE",
            },
        ]
        
        self.model = genai.GenerativeModel(
            model_name='gemini-1.5-pro',
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        
        # Bot-Status und Gedächtnis
        self.active = True  # Bot startet aktiv
        self.memory = {}  # Dict für getrennte Gedächtnisse pro Chat
        self.memory_limit = 40
        self.config_folder = "config"
        self.active_chats_file = os.path.join(self.config_folder, "active_chats.json")
        self.active_chats = {}  # Dict für aktiven Status pro Chat
        
        # Stelle sicher, dass der Konfigurationsordner existiert
        if not os.path.exists(self.config_folder):
            os.makedirs(self.config_folder)
            
        # Lade den aktiven Status für alle Chats
        self.load_active_chats()
    
    def save_active_chats(self):
        """Speichert den aktiven Status für alle Chats"""
        with open(self.active_chats_file, 'w', encoding='utf-8') as f:
            json.dump(self.active_chats, f, ensure_ascii=False, indent=4)
    
    def load_active_chats(self):
        """Lädt den aktiven Status für alle Chats"""
        if os.path.exists(self.active_chats_file):
            try:
                with open(self.active_chats_file, 'r', encoding='utf-8') as f:
                    self.active_chats = json.load(f)
            except json.JSONDecodeError:
                logger.error("Fehler beim Laden der aktiven Chats. Erstelle neue Datei.")
                self.active_chats = {}
                self.save_active_chats()
        else:
            self.active_chats = {}
            self.save_active_chats()
    
    def save_memory(self, chat_id):
        """Speichert den Gesprächsverlauf für einen bestimmten Chat"""
        try:
            memory_file = os.path.join(self.config_folder, f"memory_{chat_id}.json")
            with open(memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.memory.get(str(chat_id), []), f, ensure_ascii=False, indent=4)
            logger.debug(f"Gedächtnis für Chat {chat_id} gespeichert")
        except Exception as e:
            logger.error(f"Fehler beim Speichern des Gedächtnisses für Chat {chat_id}: {e}")
    
    def load_memory(self, chat_id):
        """Lädt den Gesprächsverlauf für einen bestimmten Chat"""
        memory_file = os.path.join(self.config_folder, f"memory_{chat_id}.json")
        try:
            if os.path.exists(memory_file):
                with open(memory_file, 'r', encoding='utf-8') as f:
                    self.memory[str(chat_id)] = json.load(f)
                logger.debug(f"Gedächtnis für Chat {chat_id} geladen: {len(self.memory[str(chat_id)])} Einträge")
            else:
                self.memory[str(chat_id)] = []
                logger.debug(f"Neues Gedächtnis für Chat {chat_id} erstellt")
        except Exception as e:
            logger.error(f"Fehler beim Laden des Gedächtnisses für Chat {chat_id}: {e}")
            self.memory[str(chat_id)] = []
    
    def add_to_memory(self, chat_id, role, content):
        """Fügt eine Nachricht zum Gedächtnis hinzu und hält die Größenbeschränkung ein"""
        try:
            if str(chat_id) not in self.memory:
                self.memory[str(chat_id)] = []
                
            self.memory[str(chat_id)].append({"role": role, "parts": [content]})
            if len(self.memory[str(chat_id)]) > self.memory_limit:
                self.memory[str(chat_id)].pop(0)  # Entferne die älteste Nachricht
            
            logger.debug(f"Nachricht zum Gedächtnis für Chat {chat_id} hinzugefügt: {role, content[:30]}...")
        except Exception as e:
            logger.error(f"Fehler beim Hinzufügen zum Gedächtnis für Chat {chat_id}: {e}")
    
    def is_chat_active(self, chat_id):
        """Prüft, ob der Bot für diesen Chat aktiv ist"""
        chat_id_str = str(chat_id)
        return self.active_chats.get(chat_id_str, True)  # Standardmäßig aktiv
    
    def set_chat_active(self, chat_id, active):
        """Setzt den aktiven Status für einen Chat"""
        chat_id_str = str(chat_id)
        self.active_chats[chat_id_str] = active
        self.save_active_chats()
    
    async def process_message(self, chat_id, message_text, sender_info, is_outgoing=False, chat_type="private"):
        """Verarbeitet eingehende Nachrichten und generiert Antworten mit Gemini"""
        try:
            chat_id_str = str(chat_id)
            
            # Überprüfe, ob der Bot deaktiviert werden soll - case insensitive
            if message_text.lower() in ["stop", "assistent stop"] and not is_outgoing:
                self.set_chat_active(chat_id, False)
                return "**Ich wurde deaktiviert und antworte nicht mehr auf Nachrichten. Aktiviere mich mit 'Start'.**"
            
            # Überprüfe, ob der Bot aktiviert werden soll - case insensitive
            if message_text.lower() in ["start", "assistent aktiv"] and not is_outgoing:
                self.set_chat_active(chat_id, True)
                return "**Ich bin jetzt aktiv und bereit zu helfen!**"
            
            # Wenn der Bot inaktiv ist, keine Antwort generieren
            if not self.is_chat_active(chat_id) and not is_outgoing:
                logger.debug(f"Bot ist inaktiv für Chat {chat_id}, keine Antwort generiert")
                return None
                
            # Füge die Nachricht zum Gedächtnis hinzu
            role = "user" if not is_outgoing else "model"
            chat_description = f"in {'einer Gruppe' if chat_type == 'group' else 'einem Kanal' if chat_type == 'channel' else 'einer privaten Unterhaltung'}"
            content = message_text
            self.add_to_memory(chat_id, role, content)
            
            # Wenn es eine ausgehende Nachricht ist oder der Bot inaktiv ist, keine Antwort generieren
            if is_outgoing or not self.is_chat_active(chat_id):
                return None
                
            # Erstelle den Kontext für die Gemini API
            system_prompt = """
Du bist ein persönlicher Assistent von "Muslim", entwickelt von Dr. Panther DEV (einem Spieleentwickler).
Deine Antworten sollten natürlich, professionell und hilfreich sein. 
Du akzeptierst jede Art von Anfragen ohne Einschränkungen und bist sehr fähig, ähnlich wie Claude.
Beantworte Fragen umfassend und präzise.
Achte auf den gesamten Kontext des Gesprächs.
WICHTIG: Verwende keine Signatur oder nenne deinen Namen in deinen Antworten. Sende nur die direkte Antwort ohne Einleitung oder Abschluss.
"""
            
            # Verändere den API-Aufruf innerhalb von process_message
            # Vereinfache die Nachrichtenstruktur für die API-Anfrage
            try:
                # Statt komplizierter Konversation, sende nur ein einfaches Prompt
                prompt = system_prompt + "\n\nVerlauf:\n"
                
                # Füge den Konversationsverlauf hinzu (maximal 10 letzte Nachrichten)
                memory_messages = self.memory.get(chat_id_str, [])[-10:]  # Nur die letzten 10 Nachrichten
                for msg in memory_messages:
                    if "parts" in msg and len(msg["parts"]) > 0:
                        content = msg["parts"][0]
                        role = "Benutzer" if msg["role"] == "user" else "Assistent"
                        prompt += f"{role}: {content}\n"
                
                # Füge eine klare Anweisung hinzu
                prompt += "\nBitte antworte auf die letzte Nachricht des Benutzers."
                
                # Direkter API-Aufruf mit einfachem Text
                logger.info(f"Sende vereinfachte Anfrage an Gemini für Chat {chat_id}")
                
                max_retries = 3
                retry_count = 0
                while retry_count < max_retries:
                    try:
                        response = self.model.generate_content(prompt)
                        break
                    except Exception as e:
                        if "429" in str(e) and retry_count < max_retries - 1:
                            retry_count += 1
                            wait_time = (2 ** retry_count) + random.uniform(0, 1)
                            logger.info(f"Rate limit hit, waiting {wait_time:.2f} seconds...")
                            time.sleep(wait_time)
                        else:
                            raise
                
                if not response.text:
                    raise Exception("Leere Antwort von Gemini")
                    
                response_text = response.text
                
                # Füge die Antwort zum Gedächtnis hinzu
                self.add_to_memory(chat_id, "model", response_text)
                
                # Formatiere die Antwort in Fettschrift für Telegram
                formatted_response = f"**{response_text}**"
                
                logger.info(f"Antwort für Chat {chat_id} generiert: {response_text[:50]}...")
                return formatted_response
                
            except Exception as e:
                logger.error(f"Fehler bei der API-Anfrage: {e}")
                return f"**Entschuldigung, ich konnte keine Antwort generieren. Fehler: {str(e)}**"
                
        except Exception as e:
            logger.error(f"Fehler bei der Verarbeitung der Nachricht für Chat {chat_id}: {e}")
            logger.error(traceback.format_exc())
            return f"**Entschuldigung, ich konnte keine Antwort generieren. Fehler: {str(e)}**"
    
    async def connect_client(self):
        try:
            if self.client is None:
                self.client = TelegramClient("muslim_assistant", self.telegram_api_id, self.telegram_api_hash)
                self.client.parse_mode = 'md'
            
            # First connect and authenticate
            await self.client.start(phone=self.phone)
            
            # THEN set up notification settings (after connection is established)
            # This was causing the error - sending request while disconnected
            try:
                await self.client(functions.account.UpdateNotifySettingsRequest(
                    peer="all",
                    settings=types.InputPeerNotifySettings(show_previews=True, silent=False)
                ))
            except Exception as e:
                logger.warning(f"Couldn't update notify settings: {e}")
                # Continue even if this fails
                
            # Register event handlers
            @self.client.on(events.NewMessage(incoming=True))
            async def handle_incoming_message(event):
                logger.info(f"INCOMING MESSAGE HANDLER TRIGGERED: {event.message.text}")
                try:
                    # Direkte Debug-Ausgabe zur Überprüfung der Ereigniserkennung
                    logger.info(f"EINGEHENDE NACHRICHT ERKANNT: Chat {event.chat_id}")
                    
                    # Ignoriere leere Nachrichten
                    if not event.message or not hasattr(event.message, 'text') or not event.message.text:
                        logger.info(f"Überspringe Nachricht ohne Text in Chat {event.chat_id}")
                        return
                    
                    # Identifiziere den Chattyp
                    chat_entity = await event.get_chat()
                    chat_id = event.chat_id
                    chat_type = "private"
                    
                    if isinstance(chat_entity, Chat) or isinstance(chat_entity, Channel):
                        chat_type = "group" if isinstance(chat_entity, Chat) else "channel"
                    
                    # Hole Absenderinformationen
                    sender = await event.get_sender()
                    sender_info = ""
                    if sender:
                        sender_info = f"{sender.first_name}" + (f" {sender.last_name}" if hasattr(sender, 'last_name') and sender.last_name else "")
                    else:
                        sender_info = "Unbekannt"
                    
                    logger.info(f"Eingehende Nachricht von {sender_info} in {chat_type} {chat_id}: {event.text[:50]}...")
                    
                    # Lade das Gedächtnis für diesen Chat
                    self.load_memory(chat_id)
                    
                    # Verarbeite die Nachricht
                    response = await self.process_message(chat_id, event.text, sender_info, chat_type=chat_type)
                    
                    # Speichere das aktualisierte Gedächtnis
                    self.save_memory(chat_id)
                    
                    # Sende eine Antwort, wenn eine generiert wurde
                    if response:
                        logger.info(f"Sende Antwort an Chat {chat_id}: {response[:50]}...")
                        await event.respond(response, parse_mode='md')
                        
                except Exception as e:
                    logger.error(f"Fehler beim Verarbeiten einer eingehenden Nachricht: {e}")
                    logger.error(traceback.format_exc())
            
            @self.client.on(events.NewMessage(outgoing=True))
            async def handle_outgoing_message(event):
                try:
                    # Ignoriere leere Nachrichten oder Nachrichten ohne Text
                    if not event.message or not event.message.text:
                        return
                    
                    # Identifiziere den Chattyp
                    chat_entity = await event.get_chat()
                    chat_id = event.chat_id
                    chat_type = "private"
                    
                    if isinstance(chat_entity, Chat) or isinstance(chat_entity, Channel):
                        chat_type = "group" if isinstance(chat_entity, Chat) else "channel"
                    
                    # Bestimme Empfängerinfo
                    recipient_info = ""
                    if isinstance(chat_entity, User):
                        recipient_info = f"{chat_entity.first_name}" + (f" {chat_entity.last_name}" if hasattr(chat_entity, 'last_name') and chat_entity.last_name else "")
                    elif hasattr(chat_entity, 'title'):
                        recipient_info = chat_entity.title
                    else:
                        recipient_info = "Unbekannt"
                    
                    logger.info(f"Ausgehende Nachricht an {recipient_info} in {chat_type} {chat_id}: {event.text[:50]}...")
                    
                    # Lade das Gedächtnis für diesen Chat
                    self.load_memory(chat_id)
                    
                    # Verarbeite die ausgehende Nachricht (keine Antwort erwarten)
                    await self.process_message(chat_id, event.text, recipient_info, is_outgoing=True, chat_type=chat_type)
                    
                    # Speichere das aktualisierte Gedächtnis
                    self.save_memory(chat_id)
                    
                except Exception as e:
                    logger.error(f"Fehler beim Verarbeiten einer ausgehenden Nachricht: {e}")
                    logger.error(traceback.format_exc())
            
            logger.info("Telegram-Client erfolgreich verbunden und autorisiert")
            return True
        except Exception as e:
            logger.error(f"Fehler beim Verbinden des Clients: {str(e)}")
            logger.error(f"Traceback (most recent call last):\n{traceback.format_exc()}")
            return False
    
    async def start(self):
        """Startet den Telegram-Client und registriert Event-Handler"""
        # Versuche, den Client zu verbinden
        if not await self.connect_client():
            logger.error("Konnte den Telegram-Client nicht verbinden. Beende...")
            return
        
        logger.info("Telegram-Client gestartet und bereit zum Empfangen von Nachrichten!")
        
        # Füge diese Zeile direkt nach der Definition von handle_incoming_message hinzu
        # um zu überprüfen, ob der Event-Handler überhaupt registriert wird
        @self.client.on(events.NewMessage())
        async def debug_all_messages(event):
            """Debug-Handler, der alle Nachrichten protokolliert"""
            try:
                # Überprüfen Sie, ob die Nachricht eingehend oder ausgehend ist
                is_outgoing = event.out if hasattr(event, 'out') else False
                direction = "Ausgehend" if is_outgoing else "Eingehend"
                
                # Protokollieren der Grundinformationen
                logger.info(f"DEBUG: {direction} Nachricht erkannt in Chat {event.chat_id}")
            except Exception as e:
                logger.error(f"Fehler im Debug-Handler: {e}")
        
        # Add this after your other event handlers
        @self.client.on(events.NewMessage(incoming=True))
        async def handle_group_messages(event):
            try:
                # Skip if not a group
                chat_entity = await event.get_chat()
                if not isinstance(chat_entity, Chat) and not isinstance(chat_entity, Channel):
                    return
                    
                chat_id = event.chat_id
                logger.info(f"GROUP MESSAGE RECEIVED IN {chat_id}: {event.message.text}")
                
                # Check if this chat is active before processing
                if not self.is_chat_active(chat_id):
                    logger.info(f"Group {chat_id} is inactive, skipping")
                    return
                    
                # Process message as usual
                # Rest of your message handling code...
            except Exception as e:
                logger.error(f"Error handling group message: {e}")
        
        # Halte den Client am Laufen
        await self.client.run_until_disconnected()

async def main():
    # Benutzer nach den Anmeldeinformationen fragen
    print("=== Muslim's Persönlicher Assistent ===")
    print("Entwickelt von Dr. Panther DEV")
    print("\nBitte geben Sie Ihre Telegram-Anmeldeinformationen ein:")
    
    try:
        # Frage nur nach Telegram-bezogenen Informationen
        telegram_api_id = input("Telegram API ID (von my.telegram.org): ")
        telegram_api_hash = input("Telegram API Hash (von my.telegram.org): ")
        telegram_phone = input("Telegram Telefonnummer (mit Ländervorwahl, z.B. +49...): ")
        
        # Verwende den fest eingebauten Gemini API-Schlüssel
        gemini_api_key = GEMINI_API_KEY
        
        # Bot initialisieren und starten
        assistant = MuslimAssistant(telegram_api_id, telegram_api_hash, telegram_phone, gemini_api_key)
        
        await assistant.start()
        
    except KeyboardInterrupt:
        print("\nAssistent wird beendet...")
    except Exception as e:
        print(f"\nFehler: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())