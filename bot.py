import os
import threading
import datetime
import pytz
from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

TOKEN = os.environ.get("TELEGRAM_TOKEN")
UNIBZ_USER = os.environ.get("UNIBZ_USER")
UNIBZ_PASS = os.environ.get("UNIBZ_PASS")
MY_CHAT_ID = os.environ.get("MY_CHAT_ID")

# Boolean flag to indicate if I'm willing to play
WILLING_TO_PLAY = False

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
    
    # Create a session to persist cookies
    session = requests.Session()

    # Data for login
    login_url = "https://scub.unibz.it/api/auth/login"
    login_payload = {
        'emailOrUsername': UNIBZ_USER,
        'password': UNIBZ_PASS
    }

    try:
        # STEP 0: Login to the website
        # Use login_payload because the API expects a JSON object
        response_login = session.post(login_url, json=login_payload)
        response_login.raise_for_status() # Check if the password is correct
        
        # If we are here, the login was successful
        
        # --- STEP 1: Find the Volleyball event ID ---
        base_url = "https://scub.unibz.it/api/events"

        response_list = session.get(base_url)
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
        response_details = session.get(details_url)
        response_details.raise_for_status()
        data_details = response_details.json()
        
        subscribers = []
        event_details = data_details.get('event', {})
        
        for booking in event_details.get('bookings', []):
            # Get the user's name, defaulting to "Unknown Name" if missing
            nome_utente = booking.get('user', {}).get('name', 'Nome Sconosciuto')
            # Only include confirmed bookings
            if booking.get('status') == 'CONFIRMED':
                subscribers.append(nome_utente)
        
        # --- MESSAGE PREPARATION ---
        if len(subscribers) > 0:
            messaggio = f"🏐 **Volleyball Match & Training**\n"
            messaggio += f"Total subscribers: {len(subscribers)}\n\n"
            
            for i, nome in enumerate(subscribers, 1):
                messaggio += f"{i}. {nome}\n"
        else:
            messaggio = "I found the event, but the subscriber list seems empty or inaccessible."
            
        await update.message.reply_text(messaggio, parse_mode='Markdown')
        
    except requests.exceptions.HTTPError as err:
        if err.response.status_code == 401:
            await update.message.reply_text("⚠️ Login error. Please check your credentials.")
        else:
            await update.message.reply_text(f"⚠️ Connection error:\n`{err}`", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"⚠️ An error occurred:\n`{e}`", parse_mode='Markdown')

# --- AUTO BOOKING SYSTEM ---
async def ask_to_play(context: ContextTypes.DEFAULT_TYPE):
    """Job scheduled at 10:00. Send the question with inline buttons."""
    global WILLING_TO_PLAY
    WILLING_TO_PLAY = False # Reset the flag
    
    # Create an inline keyboard with two buttons
    keyboard = [
        [
            InlineKeyboardButton("Yes 🏐", callback_data="play_yes"),
            InlineKeyboardButton("No 🛋️", callback_data="play_no")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=MY_CHAT_ID,
        text="Hey! Are you gonna play volleyball today?",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the button press from the user."""
    global WILLING_TO_PLAY
    query = update.callback_query
    await query.answer() # Mandatory to tell Telegram that the button was pressed

    if query.data == "play_yes":
        WILLING_TO_PLAY = True
        await query.edit_message_text(text="Awesome! 🏐 I'll automatically book it for you at 12:30.")
    elif query.data == "play_no":
        WILLING_TO_PLAY = False
        await query.edit_message_text(text="No worries! 🛋️ Maybe next time.")

async def execute_booking(context: ContextTypes.DEFAULT_TYPE):
    """Job scheduled at 12:30. Executes the booking if the user is willing to play."""
    global WILLING_TO_PLAY

    # If you didn't press the button, I won't book it for you
    if not WILLING_TO_PLAY:
        return

    # Send a message to the user that we are about to book
    await context.bot.send_message(chat_id=MY_CHAT_ID, text="It's 12:30! Booking your spot...")

    session = requests.Session()
    login_url = "https://scub.unibz.it/api/auth/login"
    login_payload = {
        'emailOrUsername': UNIBZ_USER,
        'password': UNIBZ_PASS
    }
    
    try:
        # Login
        session.post(login_url, json=login_payload).raise_for_status()

        # Find event ID
        base_url = "https://scub.unibz.it/api/events"
        data_list = session.get(base_url).json()

        event_id = None
        for event in data_list.get('events', []):
            if "Volleyball Match & Training" in event.get('title', ''):
                event_id = event.get('id')
                break
        
        if not event_id:
            await context.bot.send_message(chat_id=MY_CHAT_ID, text="❌ Error: Couldn't find today's event to book.")
            return
        
        booking_url = "https://scub.unibz.it/api/bookings"
        booking_payload = {
            "eventId": event_id,
        }

        # Make the POST request to book the event
        response_book = session.post(booking_url, json=booking_payload)
        response_book.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

        # Success!
        await context.bot.send_message(chat_id=MY_CHAT_ID, text="✅ **Successfully booked!** Get ready to spike!", parse_mode='Markdown')
    
    except Exception as e:
        await context.bot.send_message(chat_id=MY_CHAT_ID, text=f"⚠️ Failed to book automatically:\n`{e}`", parse_mode='Markdown')
    finally:
        # At the end, reset the flag
        WILLING_TO_PLAY = False

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
    # Start the dummy web server in the background (Daemon Thread)
    threading.Thread(target=run_dummy_server, daemon=True).start()
    
    # Build the Telegram bot application using the token
    app = ApplicationBuilder().token(TOKEN).build()

    # Define the timezone for scheduling
    rome_tz = pytz.timezone('Europe/Rome')
    # Define the days of the week when the bot should run (Monday=0, Sunday=6)
    days_to_run = (2, 4)
    
    # Ask the user if they want to play at 10:00 AM
    t_ask = datetime.time(hour=10, minute=0, second=0, tzinfo=rome_tz)
    app.job_queue.run_daily(ask_to_play, time=t_ask, days=days_to_run)

    # Ask the user if they want to play at 10:00 AM (test)
    t_ask_test = datetime.time(hour=10, minute=25, second=0, tzinfo=rome_tz)
    app.job_queue.run_daily(ask_to_play, time=t_ask_test)
    
    # Execute the booking at 12:30:05 PM
    t_book = datetime.time(hour=12, minute=30, second=5, tzinfo=rome_tz)
    app.job_queue.run_daily(execute_booking, time=t_book, days=days_to_run)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("players", get_players))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("Bot running! Go to Telegram and write /start")
    
    # Start polling to receive and process messages
    app.run_polling()