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
VOLUUM_FORWARD_URL = os.getenv("VOLUUM_FORWARD_URL", "").rstrip("/")  # fx https://lowasteisranime.com

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


def country_to_flag(code: str) -> str:
    """Konverter landekode eller landenavn til flag-emoji (fx DK/Denmark -> 🇩🇰, Germany -> 🇩🇪)."""
    if not code:
        return "🌍"
    s = str(code).strip()
    # Fulde landenavne -> ISO-kode (fx Germany -> DE, ikke Ge -> Georgia)
    mapping = {
        "germany": "DE", "denmark": "DK", "sweden": "SE", "norway": "NO", "finland": "FI",
        "czech republic": "CZ", "italy": "IT", "spain": "ES", "france": "FR", "poland": "PL",
        "uk": "GB", "united kingdom": "GB", "georgia": "GE", "austria": "AT", "switzerland": "CH",
        "netherlands": "NL", "belgium": "BE", "portugal": "PT", "greece": "GR", "romania": "RO",
    }
    iso = mapping.get(s.lower(), s[:2] if len(s) == 2 else "")
    if not iso or len(iso) != 2:
        return "🌍"
    try:
        return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso.upper() if "A" <= c <= "Z")
    except (TypeError, ValueError):
        return "🌍"


def format_ftd_message(data: dict) -> str:
    """Format FTD – flag, offer, payout på én linje."""
    offer = data.get("offer", data.get("offerName", data.get("offer_id", data.get("lander", "?"))))
    country = data.get("country", data.get("countryCode", data.get("geo", data.get("cc", ""))))
    payout = data.get("payout", data.get("revenue", data.get("amount", data.get("allConversionsRevenue", 0))))
    try:
        p = f"${float(payout):.2f}"
    except (TypeError, ValueError):
        p = str(payout) if payout else "0"
    if not str(p).startswith("$"):
        p = f"${p}"
    flag = country_to_flag(str(country).strip() if country else "")
    return f"{p} - {offer} - {flag}"


@app.route("/", methods=["GET"])
def index():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "service": "Voluum FTD Telegram Bot",
        "telegram_configured": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
    })


def _forward_to_voluum():
    """Videresend request til Voluum så de stadig modtager konverteringen."""
    if not VOLUUM_FORWARD_URL:
        return
    url = f"{VOLUUM_FORWARD_URL}/postback"
    try:
        if request.method == "GET":
            r = requests.get(url, params=request.args, timeout=10)
        else:
            r = requests.post(url, data=request.form or None, json=request.json if request.is_json else None, params=request.args, timeout=10)
        logger.info(f"Forwarded to Voluum: {r.status_code}")
    except Exception as e:
        logger.error(f"Voluum forward fejl: {e}")


@app.route("/postback", methods=["GET", "POST"])
def postback():
    """
    Modtag postback - send til Telegram (instant) og videresend til Voluum.
    Brug denne URL i affiliate network: https://din-railway.app/postback?cid=...
    Sæt VOLUUM_FORWARD_URL til din Voluum tracking domain så de stadig modtager.
    """
    # Get data - affiliate sender typisk GET med query params
    if request.method == "POST":
        payload = request.json or request.form.to_dict() or {}
        data = payload[0] if isinstance(payload, list) and payload else payload
    else:
        data = dict(request.args)
    
    if isinstance(data, dict):
        data = {str(k): v for k, v in data.items()}
    else:
        data = {}
    
    logger.info(f"Received postback: {data}")
    
    if not data:
        return jsonify({"error": "No data received"}), 400
    
    # KUN send for konverteringer med payout/revenue (FTD)
    payout_val = (
        data.get("payout") or data.get("revenue") or data.get("amount")
        or data.get("allConversionsRevenue") or data.get("Payout") or data.get("Revenue")
    )
    payout_num = 0
    if payout_val is not None and payout_val != "":
        try:
            payout_num = float(payout_val)
        except (TypeError, ValueError):
            pass
    
    # Altid videresend til Voluum (så de får alle konverteringer)
    _forward_to_voluum()
    
    # Spring over Telegram hvis ingen payout - KUN FTD med revenue
    if payout_num <= 0:
        logger.info(f"Ingen payout - springer Telegram over")
        return jsonify({"status": "skipped", "message": "No payout"}), 200
    
    # Kun spring over hvis tydeligt IKKE FTD (fx lead/reg). Tom eller ukendt = send (har payout)
    conv_type = str(data.get("conversionType", data.get("conversion_type", data.get("et", data.get("type", ""))))).upper()
    if conv_type and "FTD" not in conv_type and "CUSTOM" not in conv_type and "SALE" not in conv_type:
        if any(x in conv_type for x in ("LEAD", "REG", "REGISTRATION", "CLICK")):
            logger.info(f"Ikke FTD (type={conv_type}) - springer Telegram over")
            return jsonify({"status": "skipped", "message": "Not FTD"}), 200
    
    # Send Telegram (instant)
    message = format_ftd_message(data)
    send_telegram_message(message)
    return jsonify({"status": "ok"}), 200


@app.route("/debug", methods=["POST"])
def debug():
    """Se præcis hvad Zapier sender - brug denne URL i Zapier test, så vises data i response."""
    try:
        data = request.json or request.form.to_dict() or {}
    except Exception:
        data = {"raw": request.get_data(as_text=True)}
    if isinstance(data, list) and data:
        data = data[0]
    keys = list(data.keys()) if isinstance(data, dict) else []
    return jsonify({"received": data, "keys": keys}), 200


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
