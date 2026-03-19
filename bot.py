import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.environ.get("TELEGRAM_TOKEN")
UNIBZ_COOKIE = os.environ.get("UNIBZ_COOKIE")

# Initialize logging to monitor errors and activity in the console
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command, greeting the user."""
    await update.message.reply_text("Hi! Use the /players command to see today's subscribers.")

async def get_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Retrieves volleyball player data from the unibz API and sends it to the user."""
    await update.message.reply_text("I'm looking for the event and retrieving the subscribers...")
    
    # Base API endpoint for unibz events
    base_url = "https://scub.unibz.it/api/events"
    
    headers = {
        'Cookie': UNIBZ_COOKIE,
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
    } 

    try:
        # --- STEP 1: Find the Volleyball event ID ---
        response_list = requests.get(base_url, headers=headers)
        response_list.raise_for_status()
        data_list = response_list.json()
        
        event_id = None
        
        # Iterate through the events list to find the "Volleyball Match & Training" event
        for event in data_list.get('events', []):
            if "Volleyball Match & Training" in event.get('title', ''):
                event_id = event.get('id')
                break # Event found, exit the loop
                
        if not event_id:
            await update.message.reply_text("I couldn't find any Volleyball events scheduled.")
            return

        # --- STEP 2: Fetch detailed event information including booking names ---
        details_url = f"{base_url}/{event_id}"
        response_details = requests.get(details_url, headers=headers)
        response_details.raise_for_status()
        data_details = response_details.json()
        
        iscritti = []

        event_details = data_details.get('event', {})
        
        # NOTE: The structure of the bookings JSON is assumed. Expecting 'bookings' 
        # to contain a 'user' object with a 'name' field.
        for booking in event_details.get('bookings', []):
            # Get the user's name, defaulting to "Unknown Name" if missing
            nome_utente = booking.get('user', {}).get('name', 'Nome Sconosciuto')
            # Only include confirmed bookings
            if booking.get('status') == 'CONFIRMED':
                iscritti.append(nome_utente)
        
        # --- MESSAGE PREPARATION ---
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
        # Handle HTTP errors specifically (e.g., authentication failures)
        await update.message.reply_text(f"⚠️ Connection error to the site. Maybe login is required? Detail: `{err}`", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"⚠️ An error occurred:\n`{e}`", parse_mode='Markdown')

# --- DUMMY WEB SERVER FOR HOSTING SERVICES (e.g., KOYEB) ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Telegram Bot Active!")

    # Respond to HEAD requests (useful for uptime monitoring services)
    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()

    # Disable server logging to keep the console clean
    def log_message(self, format, *args):
        pass

def run_dummy_server():
    # Get port from environment variables, defaulting to 8000 (typical for Koyeb)
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    print(f"Dummy server running on port {port}...")
    server.serve_forever()
# --- END DUMMY SERVER ---

if __name__ == '__main__':
    # 1. Start the dummy web server in the background (Daemon Thread)
    threading.Thread(target=run_dummy_server, daemon=True).start()
    
    # 2. Build the Telegram bot application using the token
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("players", get_players))
    
    print("Bot running! Go to Telegram and write /start")
    
    # 3. Start polling to receive and process messages
    app.run_polling()