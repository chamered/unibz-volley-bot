# Unibz SCUB Sports Bot

A Python-based Telegram Bot designed for students of the Free University of Bozen-Bolzano (unibz). This bot interacts with the SCUB (Sports Club University Bolzano) platform to fetch event details, list subscribed players, and automatically book your spot for upcoming sports events.

## ✨ Features
* **`/players` command:** Fetches the list of confirmed players for today's "Volleyball Match & Training" (easily customizable for other sports).
* **Automated Booking System:** Sends you a Telegram message on specific days (e.g., Wed/Fri at 10:00) asking if you want to play. If you click "Yes", it automatically books your spot when the registrations open at 12:30.
* **Auto-Login:** Uses `requests.Session()` to handle unibz authentication dynamically.
* **Cloud-Ready:** Includes a built-in dummy HTTP server to bypass "sleep" restrictions on free hosting platforms like Koyeb.

## 🛠️ Prerequisites
To run your own instance of this bot, you will need:
1. Python 3.9+
2. A Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
3. Your Telegram Chat ID (from [@userinfobot](https://t.me/userinfobot))
4. Your unibz SCUB credentials
5. Your SCUB User ID (See instructions below)

## 🚀 Local Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/chamered/unibz-volley-bot.git
   cd unibz-volley-bot
   ```

2. **Install the required dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Environment Variables:**
   
   For security reasons, credentials are not hardcoded. Set the following environment variables:
   - `TELEGRAM_TOKEN`: Your Telegram Bot Token.
   - `UNIBZ_USER`: Your unibz email or username.
   - `UNIBZ_PASS`: Your unibz password.
   - `MY_CHAT_ID`: Your personal Telegram ID.
   - `UNIBZ_USER_ID`: Your unique SCUB User ID.

   **How to find your `UNIBZ_USER_ID`:**
   
   1. Log into `scub.unibz.it` on yout browser.
   2. Open Developer Tools (F12) -> Network tab.
   3. Manually book an event.
   4. Look for a `POST` request named `book`.
   5. Open the `Payload` tab of that request: you will find a JSON like `{"userId": "YOUR_USER_ID"}`. Copy that string.

4. **Run the bot:**
   ```bash
   python bot.py
   ```

## ☁️ Deployment (Koyeb / Render)
1. This bot is optimized for free PaaS platforms like Koyeb.
Connect your GitHub repository to Koyeb.
2. Go to the **Settings** of your service and navigate to **Environment Variables**.
3. Add all the 5 variables listed above (`TELEGRAM_TOKEN`, `UNIBZ_USER`, etc.).
4. Set the **Service Type** to `Web Service` (The bot includes a dummy web server on port 8000 to pass health checks).
5. Deploy!

*(Pro Tip: To prevent the bot from going to sleep on free tiers, set up a free monitor on [UptimeRobot](https://uptimerobot.com/) pointing to your Koyeb app URL to ping it every 5 minutes).*

## ⚠️ Disclaimer
This is an unofficial project created for educational purposes It is not affiliated with, endorsed, or sponsored by the Free University of Bozen-Bolzano (unibz) or the SCUB. Use it responsibly and do not spam the university's API.