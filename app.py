"""
Voluum FTD Telegram Notification Bot
=====================================
Modtager postback webhooks fra Voluum og sender notifikationer til Telegram.

Sådan virker det:
1. Voluum sender en postback til denne server når der sker en FTD konvertering
2. Serveren parser dataen og sender en besked til din Telegram chat/gruppe
"""

import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Flask app
app = Flask(__name__)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def send_telegram_message(message: str) -> tuple[bool, str]:
    """Send a message to Telegram. Returns (success, error_message)."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "din_bot_token_her":
        return False, "Bot token mangler - opdater TELEGRAM_BOT_TOKEN i .env"
    if not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID == "your_chat_id_here":
        return False, "Chat ID mangler - opdater TELEGRAM_CHAT_ID i .env"
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        
        if not response.ok:
            err = data.get("description", str(response.status_code))
            if "unauthorized" in err.lower() or response.status_code == 401:
                return False, "Ugyldigt bot token - tjek at du har kopieret det korrekt fra BotFather"
            if "chat not found" in err.lower() or response.status_code == 400:
                return False, "Chat ikke fundet - send en besked til botten først (Start), så prøv igen"
            return False, f"Telegram fejl: {err}"
        
        logger.info("Telegram message sent successfully")
        return True, ""
    except requests.RequestException as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False, str(e)


def format_ftd_message(data: dict) -> str:
    """Format FTD data into a nice Telegram message."""
    # Extract common Voluum parameters
    click_id = data.get("cid", data.get("clickid", "N/A"))
    payout = data.get("payout", data.get("revenue", "N/A"))
    campaign = data.get("campaign", data.get("camp", "N/A"))
    country = data.get("country", data.get("geo", "N/A"))
    offer = data.get("offer", data.get("lander", "N/A"))
    source = data.get("source", data.get("traffic_source", "N/A"))
    
    # Custom variables (sub1-sub10)
    custom_vars = []
    for i in range(1, 11):
        for key in [f"sub{i}", f"var{i}", f"c{i}"]:
            if data.get(key):
                custom_vars.append(f"  • {key}: {data.get(key)}")
                break
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    message = f"""
🎉 <b>NY FTD!</b> 🎉

💰 <b>Payout:</b> {payout}
📍 <b>Country:</b> {country}
📢 <b>Campaign:</b> {campaign}
🎯 <b>Offer:</b> {offer}
🔗 <b>Source:</b> {source}
🔑 <b>Click ID:</b> <code>{click_id}</code>

⏰ <b>Tid:</b> {timestamp}
"""
    
    if custom_vars:
        message += "\n📊 <b>Custom Variables:</b>\n" + "\n".join(custom_vars)
    
    return message.strip()


@app.route("/", methods=["GET"])
def index():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "service": "Voluum FTD Telegram Bot",
        "telegram_configured": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
    })


@app.route("/postback", methods=["GET", "POST"])
def postback():
    """
    Receive Voluum postback and send Telegram notification.
    
    Voluum Postback URL format:
    https://your-server.com/postback?cid={clickid}&payout={payout}&campaign={campaign}&country={country}&offer={offer}&source={trafficsource}
    
    Du kan tilføje flere parametre efter behov.
    """
    # Get data from either GET or POST
    if request.method == "POST":
        data = request.form.to_dict() or request.json or {}
    else:
        data = request.args.to_dict()
    
    logger.info(f"Received postback: {data}")
    
    if not data:
        return jsonify({"error": "No data received"}), 400
    
    # Format and send message
    message = format_ftd_message(data)
    success, error = send_telegram_message(message)
    
    if success:
        return jsonify({"status": "ok", "message": "Notification sent"}), 200
    else:
        return jsonify({"status": "error", "message": error or "Failed to send notification"}), 500


@app.route("/test", methods=["GET"])
def test():
    """Send a test notification to verify setup."""
    test_data = {
        "cid": "test-click-123",
        "payout": "$150",
        "campaign": "Test Campaign",
        "country": "DK",
        "offer": "Test Offer",
        "source": "Facebook"
    }
    
    message = "🧪 <b>TEST NOTIFIKATION</b>\n\n" + format_ftd_message(test_data)
    success, error = send_telegram_message(message)
    
    if success:
        return jsonify({"status": "ok", "message": "Test notification sent!"}), 200
    else:
        return jsonify({"status": "error", "message": error or "Failed to send test notification"}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    
    logger.info(f"Starting Voluum FTD Bot on port {port}")
    logger.info(f"Telegram configured: {bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)}")
    
    app.run(host="0.0.0.0", port=port, debug=debug)
