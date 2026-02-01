"""
Voluum FTD Telegram Notification Bot
=====================================
Modtager postback webhooks fra Voluum og sender notifikationer til Telegram.
+ Zero-revenue check: offers med 80+ clicks uden omsætning i 1,5 time.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, request, jsonify
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
VOLUUM_FORWARD_URL = os.getenv("VOLUUM_FORWARD_URL", "").rstrip("/")  # fx https://lowasteisranime.com
VOLUUM_EMAIL = os.getenv("VOLUUM_EMAIL")
VOLUUM_PASSWORD = os.getenv("VOLUUM_PASSWORD")
CRON_SECRET = os.getenv("CRON_SECRET", "")  # Beskytter /cron/* – sæt til et hemmeligt ord
CLICK_THRESHOLD = int(os.getenv("CLICK_THRESHOLD", "60"))
WAIT_HOURS = float(os.getenv("WAIT_HOURS", "1.5"))
# Regel 2: 125+ clicks siden sidste omsætning, 1 time ventetid
CLICK_THRESHOLD_HIGH = int(os.getenv("CLICK_THRESHOLD_HIGH", "125"))
WAIT_HOURS_HIGH = float(os.getenv("WAIT_HOURS_HIGH", "1"))

# State-filer for zero-revenue (i projektmappen)
_DATA_DIR = Path(__file__).parent
ZERO_SENT_FILE = _DATA_DIR / ".zero_revenue_sent.json"
ZERO_PENDING_FILE = _DATA_DIR / ".zero_revenue_pending.json"
ZERO_LAST_FILE = _DATA_DIR / ".zero_revenue_last.json"
ZERO_DATE_FILE = _DATA_DIR / ".zero_revenue_date.txt"  # Ny dag = nulstil sent

# Flask app
app = Flask(__name__)

# Sidste postback-resultat (til fejlfinding)
_last_postback = {"status": None, "message": None, "at": None}

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
    mapping = {
        "germany": "DE", "denmark": "DK", "sweden": "SE", "norway": "NO", "finland": "FI",
        "czech republic": "CZ", "italy": "IT", "spain": "ES", "france": "FR", "poland": "PL",
        "uk": "GB", "united kingdom": "GB", "georgia": "GE", "austria": "AT", "switzerland": "CH",
        "netherlands": "NL", "belgium": "BE", "portugal": "PT", "greece": "GR", "romania": "RO",
        "australia": "AU", "hungary": "HU", "ireland": "IE", "turkey": "TR",
    }
    iso = mapping.get(s.lower(), s[:2] if len(s) == 2 else "")
    if not iso or len(iso) != 2:
        return "🌍"
    try:
        return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso.upper() if "A" <= c <= "Z")
    except (TypeError, ValueError):
        return "🌍"


def country_to_owner(country: str) -> str:
    """Anders/Mikkel/Gustav baseret på land."""
    s = str(country).strip().lower()
    anders = {"united kingdom", "uk", "australia", "france"}
    mikkel = {"poland", "portugal", "norway", "italy", "greece", "romania", "ireland", "finland", "switzerland"}
    gustav = {"spain", "germany", "austria", "sweden", "czech republic", "hungary", "belgium", "netherlands", "turkey"}
    if s in anders:
        return "Anders"
    if s in mikkel:
        return "Mikkel"
    if s in gustav:
        return "Gustav"
    return "Anders/Mikkel/Gustav"


def format_zero_revenue_message(offer: str, country: str, clicks: int) -> str:
    """Zero-revenue besked: landeflag - offer ser dårlig ud X, den har fået Y uden at omsætte..."""
    flag = country_to_flag(country or "")
    owner = country_to_owner(country or "")
    return f'{flag} - {offer} ser dårlig ud {owner}, den har fået {clicks} uden at omsætte, hvis det var mig ville jeg nok tage den af :D'


def format_ftd_message(data: dict) -> str:
    """Format FTD – flag, offer, payout på én linje."""
    offer = (data.get("offer") or data.get("offerName") or data.get("offer_id")
        or data.get("lander") or data.get("Lander name") or data.get("Campaign name") or "?")
    country = (data.get("country") or data.get("countryCode") or data.get("geo") or data.get("cc") or "")
    # Brug Revenue (foretrækkes) eller Payout – første positive værdi
    def _first_positive(*vals):
        for v in vals:
            if v is None or v == "":
                continue
            try:
                n = float(str(v).replace("$", "").replace(",", ".").strip())
                if n > 0:
                    return v
            except (TypeError, ValueError):
                pass
        return 0
    payout = _first_positive(
        data.get("Revenue"), data.get("revenue"), data.get("Revenue (USD)"),
        data.get("allConversionsRevenue"), data.get("conversionRevenue"),
        data.get("payout"), data.get("Payout"), data.get("amount")
    )
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


def _normalize_postback_data(raw: dict) -> dict:
    """Gør data case-insensitive og understøt Zapier/Voluum feltnavne."""
    if not isinstance(raw, dict):
        return {}
    data = {}
    for k, v in raw.items():
        key = str(k).strip()
        if key:
            data[key.lower()] = v
    return data


@app.route("/postback", methods=["GET", "POST"])
def postback():
    """
    Modtag postback - send til Telegram (instant) og videresend til Voluum.
    Zapier POST til denne URL med Voluum conversion data.
    """
    if request.method == "POST":
        payload = request.json or request.form.to_dict() or {}
        raw = payload[0] if isinstance(payload, list) and payload else payload
        # Zapier/Voluum: nested {"conversion": {...}}, {"data": {...}}, eller flad obj
        if isinstance(raw, dict):
            raw = raw.get("conversion") or raw.get("data") or raw
    else:
        raw = dict(request.args)

    if not isinstance(raw, dict):
        raw = {}
    data = {str(k): v for k, v in raw.items()}
    data_lower = _normalize_postback_data(data)

    logger.info(f"Received postback: {data}")

    if not data:
        _last_postback.update({"status": "error", "message": "No data", "at": datetime.utcnow().isoformat()})
        return jsonify({"error": "No data received"}), 400

    # Revenue (foretrækkes) eller Payout fra Voluum – spring over 0, brug første positive værdi
    def _parse_num(val):
        if val is None or val == "":
            return 0
        try:
            s = str(val).replace("$", "").replace(",", ".").strip()
            return float(s) if s else 0
        except (TypeError, ValueError):
            return 0

    def _get_revenue(d):
        keys = ("Revenue", "revenue", "Revenue (USD)", "Revenue(USD)", "allConversionsRevenue",
                "conversionRevenue", "totalRevenue", "payout", "Payout", "amount", "Amount")
        for key in keys:
            v = d.get(key)
            if v is not None and v != "" and _parse_num(v) > 0:
                return v
        for k, v in d.items():
            if v is not None and v != "" and ("revenue" in k.lower() or "payout" in k.lower()):
                if _parse_num(v) > 0:
                    return v
        return None

    payout_val = _get_revenue(data) or _get_revenue(data_lower)
    payout_num = 0
    if payout_val is not None and payout_val != "":
        try:
            s = str(payout_val).replace("$", "").replace(",", ".").strip()
            if s:
                payout_num = float(s)
        except (TypeError, ValueError):
            pass

    _forward_to_voluum()

    if payout_num <= 0:
        _last_postback.update({"status": "skipped", "message": "No payout", "at": datetime.utcnow().isoformat(), "debug_keys": list(data.keys())})
        logger.info(f"Ingen payout - springer Telegram over. Data: {data}")
        return jsonify({"status": "skipped", "message": "No payout", "debug_received": data}), 200

    # Kun spring over ved tydelig lead/reg - DEPOSIT/FTD sendes altid
    conv_type = str(
        data.get("conversionType") or data.get("conversion_type") or data.get("Conversion type")
        or data.get("et") or data.get("type") or ""
    ).upper()
    if conv_type and any(x in conv_type for x in ("LEAD", "REG", "REGISTRATION", "CLICK")):
        if "FTD" not in conv_type and "CUSTOM" not in conv_type and "SALE" not in conv_type and "DEPOSIT" not in conv_type:
            _last_postback.update({"status": "skipped", "message": f"Not FTD (type={conv_type})", "at": datetime.utcnow().isoformat()})
            logger.info(f"Ikke FTD (type={conv_type}) - springer Telegram over")
            return jsonify({"status": "skipped", "message": "Not FTD", "debug_received": data}), 200

    message = format_ftd_message(data)
    ok, err = send_telegram_message(message)
    if not ok:
        _last_postback.update({"status": "error", "message": err, "at": datetime.utcnow().isoformat()})
        logger.error(f"Telegram fejl: {err}")
        return jsonify({"status": "error", "message": err, "debug_received": data}), 500
    _last_postback.update({"status": "ok", "message": "Sent", "at": datetime.utcnow().isoformat()})
    return jsonify({"status": "ok"}), 200


@app.route("/fetch-ftds", methods=["GET"])
def fetch_ftds():
    """
    Hent de 3 seneste FTD'er fra Voluum og send til Telegram-gruppen.
    Bruger TELEGRAM_CHAT_ID (sæt til gruppe-id fx -5135606632).
    URL: https://DIN-RAILWAY-URL/fetch-ftds?secret=DIT_CRON_SECRET
    """
    err = _require_cron_secret()
    if err:
        return err

    if not VOLUUM_EMAIL or not VOLUUM_PASSWORD:
        return jsonify({"error": "VOLUUM_EMAIL og VOLUUM_PASSWORD mangler"}), 500

    # Auth
    try:
        r = requests.post("https://api.voluum.com/auth/session",
            json={"email": VOLUUM_EMAIL, "password": VOLUUM_PASSWORD},
            headers={"Content-Type": "application/json"}, timeout=15)
        r.raise_for_status()
        token = r.json().get("token")
    except requests.RequestException as e:
        logger.error(f"Voluum auth fejl: {e}")
        return jsonify({"error": str(e)}), 500

    # Hent kampagner med konverteringer (sidste 24t)
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    from_t = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:00:00.000Z")
    to_t = now.strftime("%Y-%m-%dT%H:00:00.000Z")
    url = f"https://api.voluum.com/report?from={from_t}&to={to_t}&tz=UTC&groupBy=campaign&limit=500"
    try:
        resp = requests.get(url, headers={"cwauth-token": token, "Content-Type": "application/json"}, timeout=30)
        resp.raise_for_status()
        rows = resp.json().get("rows", [])
    except requests.RequestException as e:
        logger.error(f"Voluum report fejl: {e}")
        return jsonify({"error": str(e)}), 500

    def _revenue(row):
        r1 = float(row.get("allConversionsRevenue", 0) or row.get("revenue", 0) or 0)
        r2 = float(row.get("customRevenue1", 0) or 0)
        r3 = float(row.get("customRevenue2", 0) or 0)
        return r1 + r2 + r3

    # Kun kampagner med revenue, sorteret efter opdateret (nyeste først)
    with_rev = [r for r in rows if _revenue(r) > 0]
    with_rev.sort(key=lambda r: r.get("updated") or r.get("created") or "", reverse=True)
    top3 = with_rev[:3]

    sent_count = 0
    for row in top3:
        data = {
            "offer": row.get("offerName") or row.get("offer") or row.get("campaignNamePostfix") or row.get("campaignName") or "?",
            "country": row.get("offerCountry") or row.get("campaignCountry") or row.get("countryCode") or "",
            "revenue": _revenue(row),
            "payout": _revenue(row),
        }
        msg = format_ftd_message(data)
        ok, _ = send_telegram_message(msg)
        if ok:
            sent_count += 1

    return jsonify({"status": "ok", "ftds_sent": sent_count, "message": f"Sendt {sent_count} af {len(top3)} til Telegram"}), 200


@app.route("/diagnose", methods=["GET"])
def diagnose():
    """Se sidste postback-resultat – brug til fejlfinding."""
    return jsonify({
        "last_postback": _last_postback,
        "tip": "Hvis status er 'skipped' med 'No payout', tjek at Zapier sender Revenue/Payout felt. Brug /debug i Zapier POST URL for at se raw data."
    }), 200


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


def _require_cron_secret():
    """Return 401 if CRON_SECRET ikke matcher."""
    if not CRON_SECRET:
        return jsonify({"error": "CRON_SECRET ikke sat i Railway"}), 500
    got = request.args.get("secret") or (request.json or {}).get("secret")
    if got != CRON_SECRET:
        return jsonify({"error": "Ugyldig secret"}), 401
    return None


@app.route("/cron/zero-revenue", methods=["GET"])
def cron_zero_revenue():
    """
    Tjek offers med 80+ clicks uden revenue i 1,5 time. Send til Telegram.
    Kald fra cron-job.org hvert 10. minut.
    URL: https://DIN-RAILWAY-URL/cron/zero-revenue?secret=DIT_CRON_SECRET
    """
    err = _require_cron_secret()
    if err:
        return err

    if not VOLUUM_EMAIL or not VOLUUM_PASSWORD:
        return jsonify({"error": "VOLUUM_EMAIL og VOLUUM_PASSWORD mangler"}), 500

    # Hent token
    try:
        r = requests.post("https://api.voluum.com/auth/session",
            json={"email": VOLUUM_EMAIL, "password": VOLUUM_PASSWORD},
            headers={"Content-Type": "application/json"}, timeout=15)
        r.raise_for_status()
        token = r.json().get("token")
    except requests.RequestException as e:
        logger.error(f"Voluum auth fejl: {e}")
        return jsonify({"error": str(e)}), 500

    # Hent offer-report (kun i dag)
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    from_t = now.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:00:00.000Z")
    to_t = now.strftime("%Y-%m-%dT%H:00:00.000Z")
    url = f"https://api.voluum.com/report?from={from_t}&to={to_t}&tz=UTC&groupBy=offer&limit=500"
    try:
        resp = requests.get(url, headers={"cwauth-token": token, "Content-Type": "application/json"}, timeout=30)
        resp.raise_for_status()
        rows = resp.json().get("rows", [])
    except requests.RequestException as e:
        logger.error(f"Voluum report fejl: {e}")
        return jsonify({"error": str(e)}), 500

    def get_clicks(row):
        return int(row.get("uniqueClicks", 0) or 0)

    def get_revenue(row):
        r1 = float(row.get("allConversionsRevenue", 0) or row.get("revenue", 0) or 0)
        r2 = float(row.get("customRevenue1", 0) or 0)
        r3 = float(row.get("customRevenue2", 0) or 0)
        return r1 + r2 + r3

    # Regel 1: 0 revenue i dag, 80+ clicks, 1,5t ventetid
    # Regel 2: Har omsat, men 150+ clicks SIDEN sidste omsætning, 1t ventetid
    # Maks 1 besked per offer
    zero_rev_rows = [r for r in rows if get_clicks(r) >= CLICK_THRESHOLD and get_revenue(r) <= 0]
    has_rev_rows = [r for r in rows if get_revenue(r) > 0]
    rows_by_oid = {r.get("offerId"): r for r in rows if r.get("offerId")}

    now_dt = datetime.utcnow()
    today_str = now_dt.strftime("%Y-%m-%d")
    is_new_day = False
    if ZERO_DATE_FILE.exists():
        try:
            if ZERO_DATE_FILE.read_text().strip() != today_str:
                is_new_day = True
        except Exception:
            pass
    ZERO_DATE_FILE.write_text(today_str)

    sent = set()
    pending = {}
    last_snap = {}
    if not is_new_day:
        if ZERO_SENT_FILE.exists():
            try:
                sent = set(json.loads(ZERO_SENT_FILE.read_text()))
            except Exception:
                pass
        if ZERO_PENDING_FILE.exists():
            try:
                pending = json.loads(ZERO_PENDING_FILE.read_text())
            except Exception:
                pass
        if ZERO_LAST_FILE.exists():
            try:
                last_snap = json.loads(ZERO_LAST_FILE.read_text())
            except Exception:
                pass

    new_pending = {}
    new_snap = {}
    sent_count = 0

    # Regel 1: 0 revenue, 60+ clicks, 1,5t
    for row in zero_rev_rows:
        oid = row.get("offerId", "")
        if not oid or oid in sent:
            continue
        offer = row.get("offerName") or row.get("offer", "?")
        uclicks = get_clicks(row)
        entry = pending.get(oid, {})
        first_80 = entry.get("first_seen_80") or entry.get("first_seen")
        if not first_80:
            first_80 = now_dt.timestamp()
        try:
            elapsed = (now_dt.timestamp() - float(first_80)) / 3600
        except (TypeError, ValueError):
            new_pending[oid] = {"first_seen_80": first_80}
            new_snap[oid] = {"clicks": uclicks, "revenue": 0}
            continue
        if elapsed >= WAIT_HOURS:
            country = row.get("offerCountry", row.get("campaignCountry", ""))
            msg = format_zero_revenue_message(offer, country, uclicks)
            ok, _ = send_telegram_message(msg)
            if ok:
                sent.add(oid)
                sent_count += 1
                logger.info(f"Zero-revenue alert (80+): {offer}")
            new_snap[oid] = {"clicks": uclicks, "revenue": 0}
            continue
        new_pending[oid] = {"first_seen_80": first_80}
        new_snap[oid] = {"clicks": uclicks, "revenue": 0}

    # Regel 2: Har omsat, men 150+ clicks siden sidste omsætning, 1t
    for row in has_rev_rows:
        oid = row.get("offerId", "")
        if not oid or oid in sent:
            continue
        uclicks = get_clicks(row)
        rev = get_revenue(row)
        prev = last_snap.get(oid, {})
        prev_clicks = int(prev.get("clicks", 0) or 0)
        prev_rev = float(prev.get("revenue", 0) or 0)
        new_snap[oid] = {"clicks": uclicks, "revenue": rev}

        if prev_rev <= 0:
            continue  # Første gang vi ser offer med revenue – mangler baseline
        if rev > prev_rev:
            continue  # Ny omsætning – nulstil timer
        clicks_since = uclicks - prev_clicks
        if clicks_since < CLICK_THRESHOLD_HIGH:
            continue

        offer = row.get("offerName") or row.get("offer", "?")
        entry = pending.get(oid, {})
        first_150 = entry.get("first_seen_150")
        if not first_150:
            first_150 = now_dt.timestamp()
        try:
            elapsed = (now_dt.timestamp() - float(first_150)) / 3600
        except (TypeError, ValueError):
            new_pending[oid] = {**entry, "first_seen_150": first_150}
            continue
        if elapsed >= WAIT_HOURS_HIGH:
            country = row.get("offerCountry", row.get("campaignCountry", ""))
            msg = format_zero_revenue_message(offer, country, uclicks)
            ok, _ = send_telegram_message(msg)
            if ok:
                sent.add(oid)
                sent_count += 1
                logger.info(f"Zero-revenue alert (150+ siden omsætning): {offer}")
            continue
        new_pending[oid] = {**entry, "first_seen_150": first_150}

    # Behold pending for offers vi stadig tracker
    for oid, row in rows_by_oid.items():
        if oid not in new_snap:
            new_snap[oid] = {"clicks": get_clicks(row), "revenue": get_revenue(row)}

    ZERO_SENT_FILE.write_text(json.dumps(list(sent)))
    ZERO_PENDING_FILE.write_text(json.dumps(new_pending))
    ZERO_LAST_FILE.write_text(json.dumps(new_snap))

    return jsonify({"status": "ok", "alerts_sent": sent_count}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    
    logger.info(f"Starting Voluum FTD Bot on port {port}")
    logger.info(f"Telegram configured: {bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)}")
    
    app.run(host="0.0.0.0", port=port, debug=debug)
