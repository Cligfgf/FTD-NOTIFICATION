"""
Voluum FTD Telegram Bot - API Polling Version
==============================================
Henter FTD direkte fra Voluum API - ingen deployment nødvendig.
Kør lokalt eller med cron/scheduler.

Brug: python3 voluum_poll.py
"""

import os
import time
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# Config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
VOLUUM_EMAIL = os.getenv("VOLUUM_EMAIL")
VOLUUM_PASSWORD = os.getenv("VOLUUM_PASSWORD")
VOLUUM_ACCESS_KEY_ID = os.getenv("VOLUUM_ACCESS_KEY_ID")
VOLUUM_ACCESS_KEY_SECRET = os.getenv("VOLUUM_ACCESS_KEY_SECRET")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "30"))  # sekunder - tjek oftere

# Fil til at huske sidst sete kampagne-statistik (sammenlign for nye FTD)
STATE_FILE = Path(__file__).parent / ".voluum_state.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_voluum_token():
    """Hent session token fra Voluum API."""
    url = "https://api.voluum.com/auth/session"
    
    if VOLUUM_ACCESS_KEY_ID and VOLUUM_ACCESS_KEY_SECRET:
        payload = {
            "accessKeyId": VOLUUM_ACCESS_KEY_ID,
            "accessKeySecret": VOLUUM_ACCESS_KEY_SECRET,
        }
    elif VOLUUM_EMAIL and VOLUUM_PASSWORD:
        payload = {"email": VOLUUM_EMAIL, "password": VOLUUM_PASSWORD}
    else:
        logger.error("Manglende Voluum credentials - brug VOLUUM_EMAIL/PASSWORD eller VOLUUM_ACCESS_KEY_ID/SECRET")
        return None

    try:
        r = requests.post(url, json=payload, timeout=15, headers={"Content-Type": "application/json"})
        r.raise_for_status()
        data = r.json()
        return data.get("token")
    except requests.RequestException as e:
        logger.error(f"Voluum auth fejl: {e}")
        if hasattr(e, "response") and e.response is not None:
            try:
                err = e.response.json()
                logger.error(f"Voluum svar: {err}")
            except Exception:
                pass
        return None


def fetch_voluum_report(token, hours_back=24):
    """Hent kampagne-report fra Voluum API. Voluum kræver tid rundet til hele timer."""
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    from_time = (now - timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:00:00.000Z")
    to_time = now.strftime("%Y-%m-%dT%H:00:00.000Z")
    
    url = f"https://api.voluum.com/report?from={from_time}&to={to_time}&tz=UTC&groupBy=campaign"
    headers = {"cwauth-token": token, "Content-Type": "application/json"}
    
    all_rows = []
    offset = 0
    limit = 100
    
    while True:
        try:
            r = requests.get(f"{url}&limit={limit}&offset={offset}", timeout=30, headers=headers)
            if r.status_code != 200:
                logger.error(f"Voluum fejl {r.status_code}: {r.text[:200]}")
                return []
            data = r.json()
            rows = data.get("rows", [])
            if not rows:
                break
            all_rows.extend(rows)
            if len(rows) < limit or data.get("truncated") is False:
                break
            offset += limit
        except requests.RequestException as e:
            logger.error(f"Voluum report fejl: {e}")
            return []
    
    return all_rows


def send_telegram(message: str) -> bool:
    """Send besked til Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
        }, timeout=10)
        r.raise_for_status()
        return True
    except requests.RequestException as e:
        logger.error(f"Telegram fejl: {e}")
        return False


def format_campaign_delta(row: dict, delta_conv: int, delta_rev: float) -> str:
    """Format kampagne-delta til Telegram (alle konverteringer med revenue)."""
    campaign = row.get("campaignName", "N/A")
    country = row.get("campaignCountry", "N/A")
    source = row.get("trafficSourceName", "N/A")
    return f"""🎉 <b>NYE KONVERTERINGER!</b> 🎉

📢 <b>Campaign:</b> {campaign}
📍 <b>Country:</b> {country}
🔗 <b>Source:</b> {source}

➕ <b>Nye konverteringer:</b> {delta_conv}
💰 <b>Ny revenue:</b> ${delta_rev:.2f}

⏰ <b>Tid:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}"""


def get_last_state() -> dict:
    """Hent sidst gemt kampagne-statistik."""
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def save_state(state: dict):
    """Gem kampagne-statistik til næste sammenligning."""
    STATE_FILE.write_text(json.dumps(state, indent=0))


def poll_once(token: str):
    """Kør én poll-runde - sammenlign med sidst og send notifikationer ved nye FTD."""
    rows = fetch_voluum_report(token, hours_back=4)  # 4t window for hurtigere opdatering
    last = get_last_state()
    current = {}
    is_first_run = len(last) == 0  # Første kørsel - gem kun baseline, send ingen notifikationer
    
    for row in rows:
        cid = row.get("campaignId")
        if not cid:
            continue
        
        # Alle konverteringer: conversions + customConversions1+2
        conv = int(row.get("conversions", 0) or 0)
        c1 = int(row.get("customConversions1", 0) or 0)
        c2 = int(row.get("customConversions2", 0) or 0)
        total_conv = conv + c1 + c2
        
        # Al revenue: allConversionsRevenue + customRevenue1+2
        rev_main = float(row.get("allConversionsRevenue", 0) or row.get("revenue", 0) or 0)
        rev_c1 = float(row.get("customRevenue1", 0) or 0)
        rev_c2 = float(row.get("customRevenue2", 0) or 0)
        total_rev = rev_main + rev_c1 + rev_c2
        
        current[cid] = {"conversions": total_conv, "revenue": total_rev}
        
        prev = last.get(cid, {"conversions": 0, "revenue": 0})
        delta_conv = total_conv - prev.get("conversions", 0)
        delta_rev = total_rev - prev.get("revenue", 0)
        
        # Send når der er nye konverteringer og/eller ny revenue (og ikke første kørsel)
        if not is_first_run and (delta_conv > 0 or delta_rev > 0):
            msg = format_campaign_delta(row, delta_conv, delta_rev)
            if send_telegram(msg):
                logger.info(f"FTD notifikation sendt: {row.get('campaignName')} (+{delta_conv} conv)")
    
    save_state(current)


def main():
    """Hovedloop."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Telegram ikke konfigureret. Sæt TELEGRAM_BOT_TOKEN og TELEGRAM_CHAT_ID i .env")
        return
    
    if not (VOLUUM_EMAIL and VOLUUM_PASSWORD) and not (VOLUUM_ACCESS_KEY_ID and VOLUUM_ACCESS_KEY_SECRET):
        logger.error("Voluum ikke konfigureret. Sæt VOLUUM_EMAIL+VOLUUM_PASSWORD eller VOLUUM_ACCESS_KEY_ID+VOLUUM_ACCESS_KEY_SECRET i .env")
        return
    
    logger.info(f"Starter Voluum FTD polling (interval: {POLL_INTERVAL}s)")
    
    while True:
        token = get_voluum_token()
        if token:
            poll_once(token)
        else:
            logger.warning("Kunne ikke hente Voluum token - prøver igen om %ds", POLL_INTERVAL)
        
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    import sys
    if "--reset" in sys.argv:
        if STATE_FILE.exists():
            STATE_FILE.unlink()
            print("✅ State nulstillet - ny baseline ved næste kørsel")
        else:
            print("Ingen state fil at nulstille")
    elif "--test-auth" in sys.argv:
        token = get_voluum_token()
        if token:
            print("✅ Voluum auth OK - token hentet")
            rows = fetch_voluum_report(token, hours_back=24)
            total_conv = sum(int(r.get("conversions", 0) or 0) + int(r.get("customConversions1", 0) or 0) + int(r.get("customConversions2", 0) or 0) for r in rows)
            print(f"   Kampagner (sidste 24t): {len(rows)}")
            print(f"   Total konverteringer: {total_conv}")
        else:
            print("❌ Voluum auth fejlede - tjek credentials i .env")
    else:
        main()
