import datetime
import logging
import os
import threading

import pytz
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

# --- CONFIGURATION & CONSTANTS ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")
UNIBZ_USER = os.environ.get("UNIBZ_USER")
UNIBZ_PASS = os.environ.get("UNIBZ_PASS")
MY_CHAT_ID = os.environ.get("MY_CHAT_ID")
UNIBZ_USER_ID = os.environ.get("UNIBZ_USER_ID")

# Global flag to track if the user wants to play today
WILLING_TO_PLAY = False

# REST API Endpoints
BASE_URL = "https://scub.unibz.it/api"
LOGIN_URL = f"{BASE_URL}/auth/login"
EVENTS_URL = f"{BASE_URL}/events"
BOOKINGS_URL = f"{BASE_URL}/bookings"

# Configure logging to monitor activity and debug issues
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# --- HELPER FUNCTIONS ---

def login_to_unibz(session: requests.Session) -> bool:
    """
    Authenticates the session with unibz credentials.
    Returns True if successful, False otherwise.
    """
    login_payload = {
        "emailOrUsername": UNIBZ_USER,
        "password": UNIBZ_PASS
    }
    try:
        response = session.post(LOGIN_URL, json=login_payload)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Login failed: {e}")
        return False


def find_volleyball_event(session: requests.Session) -> str:
    """
    Searches for today's "Volleyball Match & Training" event.
    Returns the event ID if found, None otherwise.
    """
    try:
        response = session.get(EVENTS_URL)
        response.raise_for_status()
        data = response.json()

        for event in data.get("events", []):
            if "Volleyball Match & Training" in event.get("title", ""):
                return event.get("id")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch events: {e}")

    return None


# --- BOT COMMAND HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets the user and provides basic instructions."""
    await update.message.reply_text(
        "Hi! Use the /players command to see today's subscribers."
    )


async def get_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and displays the list of players currently subscribed to the event."""
    await update.message.reply_text("Retrieving the subscribers list...")

    session = requests.Session()
    try:
        # Step 1: Login
        if not login_to_unibz(session):
            await update.message.reply_text("⚠️ Login error. Check credentials.")
            return

        # Step 2: Find the event ID
        event_id = find_volleyball_event(session)
        if not event_id:
            await update.message.reply_text("No Volleyball events found for today.")
            return

        # Step 3: Fetch event details (subscribers)
        details_url = f"{EVENTS_URL}/{event_id}"
        response = session.get(details_url)
        response.raise_for_status()
        details = response.json()

        subscribers = []
        event_data = details.get("event", {})
        for booking in event_data.get("bookings", []):
            if booking.get("status") == "CONFIRMED":
                name = booking.get("user", {}).get("name", "Unknown Name")
                subscribers.append(name)

        # Step 4: Format and send the response
        if subscribers:
            message = "🏐 **Volleyball Match & Training**\n"
            message += f"Total subscribers: {len(subscribers)}\n\n"
            for i, name in enumerate(subscribers, 1):
                message += f"{i}. {name}\n"
        else:
            message = "No subscribers found for this event."

        await update.message.reply_text(message, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error in get_players: {e}")
        await update.message.reply_text(f"⚠️ An error occurred:\n`{e}`", parse_mode="Markdown")


# --- AUTO-BOOKING WORKFLOW ---

async def ask_to_play(context: ContextTypes.DEFAULT_TYPE):
    """Daily job (10:00) to ask the user if they want to play today."""
    global WILLING_TO_PLAY
    WILLING_TO_PLAY = False  # Reset state

    keyboard = [
        [
            InlineKeyboardButton("Yes 🏐", callback_data="play_yes"),
            InlineKeyboardButton("No 🛋️", callback_data="play_no"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=MY_CHAT_ID,
        text="Hey! Are you planning to play volleyball today?",
        reply_markup=reply_markup,
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes the user's response to the play inquiry."""
    global WILLING_TO_PLAY
    query = update.callback_query
    await query.answer()

    if query.data == "play_yes":
        WILLING_TO_PLAY = True
        await query.edit_message_text(
            "Awesome! 🏐 I'll attempt to book your spot at 12:30."
        )
    elif query.data == "play_no":
        WILLING_TO_PLAY = False
        await query.edit_message_text("No problem! 🛋️ Maybe next time.")


async def execute_booking(context: ContextTypes.DEFAULT_TYPE):
    """Daily job (12:30) to perform the automatic booking if requested."""
    global WILLING_TO_PLAY

    if not WILLING_TO_PLAY:
        return

    await context.bot.send_message(chat_id=MY_CHAT_ID, text="Booking window open! Processing...")

    session = requests.Session()
    try:
        # Step 1: Login
        if not login_to_unibz(session):
            await context.bot.send_message(chat_id=MY_CHAT_ID, text="❌ Auto-booking failed: Login error.")
            return

        # Step 2: Find Event
        event_id = find_volleyball_event(session)
        if not event_id:
            await context.bot.send_message(chat_id=MY_CHAT_ID, text="❌ Auto-booking failed: Event not found.")
            return

        # Step 3: Perform Booking
        booking_url = f"{EVENTS_URL}/{event_id}/book"
        payload = {"userId": UNIBZ_USER_ID}
        response = session.post(booking_url, json=payload)
        response.raise_for_status()

        await context.bot.send_message(
            chat_id=MY_CHAT_ID,
            text="✅ **Successfully booked!** Get ready to spike!",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Auto-booking error: {e}")
        await context.bot.send_message(
            chat_id=MY_CHAT_ID,
            text=f"⚠️ Auto-booking failed:\n`{e}`",
            parse_mode="Markdown",
        )
    finally:
        WILLING_TO_PLAY = False  # Always reset after attempt


# --- INFRASTRUCTURE: DUMMY SERVER ---

class DummyHandler(BaseHTTPRequestHandler):
    """Minimal HTTP server to satisfy hosting health checks (e.g., Koyeb)."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Telegram Bot Active!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

    def log_message(self, format, *args):
        # Suppress logging to keep output clean
        pass


def run_dummy_server():
    """Starts the dummy server on the port defined by environment variables."""
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    logger.info(f"Health check server running on port {port}")
    server.serve_forever()


# --- MAIN EXECUTION ---

if __name__ == "__main__":
    # Start health check server in a background thread
    threading.Thread(target=run_dummy_server, daemon=True).start()

    # Initialize Telegram Application
    app = ApplicationBuilder().token(TOKEN).build()

    # Timezone and scheduling configuration
    rome_tz = pytz.timezone("Europe/Rome")
    days_to_run = (2, 4)  # Wednesday and Friday (0=Mon, 6=Sun)

    # Schedule: Ask user at 10:00
    t_ask = datetime.time(hour=10, minute=0, second=0, tzinfo=rome_tz)
    app.job_queue.run_daily(ask_to_play, time=t_ask, days=days_to_run)

    # Schedule: Execute booking at 12:30:05
    t_book = datetime.time(hour=12, minute=30, second=5, tzinfo=rome_tz)
    app.job_queue.run_daily(execute_booking, time=t_book, days=days_to_run)

    # Register Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("players", get_players))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Bot is starting... Check Telegram for interaction.")
    app.run_polling()