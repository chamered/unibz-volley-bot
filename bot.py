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

# --- MULTI-USER DATABASE (HARDCODED) ---
# Create a dictionary by reading system variables
USERS = {}

# User 1 (Me)
MY_CHAT_ID = os.environ.get("MY_CHAT_ID")
if (MY_CHAT_ID):
    USERS[str(MY_CHAT_ID)] = {
        "user": UNIBZ_USER,
        "pass": UNIBZ_PASS,
        "user_id": UNIBZ_USER_ID,
        "willing": False
    }

# User 2 (Friend)
FRIEND_CHAT_ID = os.environ.get("FRIEND_CHAT_ID")
if (FRIEND_CHAT_ID):
    USERS[str(FRIEND_CHAT_ID)] = {
        "user": FRIEND_UNIBZ_USER,
        "pass": FRIEND_UNIBZ_PASS,
        "user_id": FRIEND_UNIBZ_USER_ID,
        "willing": False
    }


# --- HELPER FUNCTIONS ---
def login_to_unibz(session: requests.Session, username, password) -> bool:
    """Authenticates the specific user session."""
    login_payload = {
        "emailOrUsername": username,
        "password": password
    }
    try:
        response = session.post(LOGIN_URL, json=login_payload)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Login failed for {username}: {e}")
        return False


def find_volleyball_event(session: requests.Session) -> str:
    """
    Searches for today's "Volleyball Match & Training" event.
    Returns the event ID if found, None otherwise.
    """
    try:
        response = session.get(EVENTS_URL)
        response.raise_for_status()
        for event in response.json().get("events", []):
            if "Volleyball Match & Training" in event.get("title", ""):
                return event.get("id")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch events: {e}")
    return None


# --- BOT COMMAND HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets the user and provides basic instructions."""
    if str(update.effective_chat.id) not in USERS:
        await update.message.reply_text("⛔ Access denied. Private bot.")
        return
    await update.message.reply_text("Hi! Use the /players command to see today's subscribers.")


async def get_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and displays the list of players currently subscribed to the volleyball event."""
    chat_id = str(update.effective_chat.id)
    if chat_id not in USERS:
        return

    await update.message.reply_text("Retrieving the subscribers list...")
    session = requests.Session()
    try:
        # Step 1: Login using the credentials of the user who called the command
        my_creeds = USERS[chat_id]
        if not login_to_unibz(session, my_creeds["user"], my_creeds["pass"]):
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

        subscribers = []
        event_data = response.json().get("event", {})
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
    """Daily job (10:00) to ask to all users if they want to play today."""
    keyboard = [
        [
            InlineKeyboardButton("Yes 🏐", callback_data="play_yes"),
            InlineKeyboardButton("No 🛋️", callback_data="play_no"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    for chat_id in USERS:
        USERS[chat_id]["willing"] = False
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="Hey! Are you planning to play volleyball today?",
                reply_markup=reply_markup,
            )
        except Exception as e:
            logger.error(f"Error sending message to {chat_id}: {e}")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes the user's response to the play inquiry."""
    chat_id = str(update.effective_chat.id)
    query = update.callback_query

    if chat_id not in USERS:
        await query.answer("⛔ Access denied.", show_alert=True)
        return

    await query.answer()

    if query.data == "play_yes":
        USERS[chat_id]["willing"] = True # Change the state only for the single user
        await query.edit_message_text("Awesome! 🏐 I'll attempt to book your spot at 12:30.")
    elif query.data == "play_no":
        USERS[chat_id]["willing"] = False
        await query.edit_message_text("No problem! 🛋️ Maybe next time.")


async def execute_booking(context: ContextTypes.DEFAULT_TYPE):
    """Daily job (12:30) to perform the automatic booking for EACH user who said yes."""
    for chat_id, user_data in USERS.items():
        if not user_data["willing"]:
            continue # Skip the user if he said no

        await context.bot.send_message(chat_id=chat_id, text="Booking window open! Processing...")

        session = requests.Session()
        try:
            # Step 1: Login
            if not login_to_unibz(session, user_data["user"], user_data["pass"]):
                await context.bot.send_message(chat_id=chat_id, text="❌ Auto-booking failed: Login error.")
                continue

            # Step 2: Find Event
            event_id = find_volleyball_event(session)
            if not event_id:
                await context.bot.send_message(chat_id=chat_id, text="❌ Auto-booking failed: Event not found.")
                continue

            # Step 3: Perform Booking with the specific user ID
            booking_url = f"{EVENTS_URL}/{event_id}/book"
            payload = {"userId": user_data["id"]}
            response = session.post(booking_url, json=payload)
            response.raise_for_status()

            await context.bot.send_message(
                chat_id=chat_id,
                text="✅ **Successfully booked!** Get ready to spike!",
                parse_mode="Markdown",
            )

        except Exception as e:
            logger.error(f"Auto-booking error for {chat_id}: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ Auto-booking failed:\n`{e}`",
                parse_mode="Markdown",
            )
        finally:
            USERS[chat_id]["willing"] = False  # Reset the state for the next day


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
    days_to_run = (3, 5) # Wednesday (3) and Friday (5) in python-telegram-bot (0=Sunday)

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