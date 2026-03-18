import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.environ.get("TELEGRAM_TOKEN")
UNIBZ_COOKIE = os.environ.get("UNIBZ_COOKIE")

# Configura il logging per vedere eventuali errori nel terminale
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Risponde al comando /start"""
    await update.message.reply_text("Hi! Use the /players command to see today's subscribers.")

async def get_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recupera i dati dal JSON in due step e li invia su Telegram"""
    await update.message.reply_text("I'm looking for the event and retrieving the subscribers...")
    
    # Base URL
    base_url = "https://scub.unibz.it/api/events"
    
    # ⚠️ IF AUTHENTICATION IS REQUIRED, UNCOMMENT THESE LINES AND INSERT YOUR COOKIE
    # headers = {'Cookie': 'NOME_COOKIE=valore_del_cookie'} 
    # For now we use an empty variable if you don't have the cookies yet
    headers = {
        'Cookie': UNIBZ_COOKIE,
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
    } 

    try:
        # --- STEP 1: Trovare l'ID dell'evento ---
        response_list = requests.get(base_url, headers=headers)
        response_list.raise_for_status()
        data_list = response_list.json()
        
        event_id = None
        
        # Navighiamo la lista "events" del JSON che mi hai incollato
        for event in data_list.get('events', []):
            if "Volleyball Match & Training" in event.get('title', ''):
                event_id = event.get('id')
                break # Trovato l'evento, fermiamo il ciclo!
                
        if not event_id:
            await update.message.reply_text("I couldn't find any Volleyball events scheduled.")
            return

        # --- STEP 2: Usare l'ID per prendere i dettagli (e i nomi) ---
        details_url = f"{base_url}/{event_id}"
        response_details = requests.get(details_url, headers=headers)
        response_details.raise_for_status()
        data_details = response_details.json()
        
        iscritti = []

        event_details = data_details.get('event', {})
        
        # ATTENZIONE: Qui sto tirando a indovinare la struttura del SECONDO JSON.
        # Immagino che dentro "bookings" ci sia un dizionario "user" con il "name".
        # Se la struttura è diversa, dovrai aggiustare queste 3 righe.
        for booking in event_details.get('bookings', []):
            # Prova a prendere il nome, se non lo trova mette "Nome Sconosciuto"
            nome_utente = booking.get('user', {}).get('name', 'Nome Sconosciuto')
            # Aggiungiamo solo chi è confermato per sicurezza
            if booking.get('status') == 'CONFIRMED':
                iscritti.append(nome_utente)
        
        # --- PREPARAZIONE DEL MESSAGGIO ---
        if len(iscritti) > 0:
            messaggio = f"🏐 **Volleyball Match & Training**\n"
            messaggio += f"Event ID: `{event_id}`\n"
            messaggio += f"Total subscribers: {len(iscritti)}\n\n"
            
            for i, nome in enumerate(iscritti, 1):
                messaggio += f"{i}. {nome}\n"
        else:
            messaggio = "I found the event, but the subscriber list seems empty or inaccessible."
            
        await update.message.reply_text(messaggio, parse_mode='Markdown')
        
    except requests.exceptions.HTTPError as err:
        # Gestione specifica se il sito ci blocca (es. Errore 401 o 403)
        await update.message.reply_text(f"⚠️ Connection error to the site. Maybe login is required? Detail: `{err}`", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"⚠️ An error occurred:\n`{e}`", parse_mode='Markdown')

# --- INIZIO FINTO SERVER WEB PER KOYEB ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot Telegram Attivo!")

    # Nascondiamo i log del server web per non sporcare il terminale
    def log_message(self, format, *args):
        pass

def run_dummy_server():
    # Koyeb di solito usa la porta 8000 di default
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    print(f"Dummy server running on port {port}...")
    server.serve_forever()
# --- END DUMMY SERVER ---

if __name__ == '__main__':
    # 1. Start the dummy web server in the background (Daemon Thread)
    threading.Thread(target=run_dummy_server, daemon=True).start()
    
    # 2. Crea l'applicazione del bot
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("players", get_players))
    
    print("Bot running! Go to Telegram and write /start")
    
    # 3. Mantiene il bot in ascolto
    app.run_polling()