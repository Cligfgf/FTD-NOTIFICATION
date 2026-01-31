#!/usr/bin/env python3
"""Send de 3 seneste kampagner med FTD til Telegram."""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
import requests

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
VOLUUM_EMAIL = os.getenv("VOLUUM_EMAIL")
VOLUUM_PASSWORD = os.getenv("VOLUUM_PASSWORD")


def get_token():
    r = requests.post("https://api.voluum.com/auth/session",
        json={"email": VOLUUM_EMAIL, "password": VOLUUM_PASSWORD},
        headers={"Content-Type": "application/json"}, timeout=15)
    r.raise_for_status()
    return r.json().get("token")


def fetch_report(token):
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    from_t = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:00:00.000Z")
    to_t = now.strftime("%Y-%m-%dT%H:00:00.000Z")
    url = f"https://api.voluum.com/report?from={from_t}&to={to_t}&tz=UTC&groupBy=campaign&limit=500"
    r = requests.get(url, headers={"cwauth-token": token, "Content-Type": "application/json"}, timeout=30)
    r.raise_for_status()
    return r.json().get("rows", [])


def send_telegram(msg):
    r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    r.raise_for_status()


def country_to_flag(code):
    if not code:
        return "🌍"
    s = str(code).strip()
    # Voluum sender fuldt landenavn - kort mapping
    mapping = {"czech republic": "CZ", "norway": "NO", "sweden": "SE", "denmark": "DK", "finland": "FI",
               "germany": "DE", "italy": "IT", "spain": "ES", "france": "FR", "poland": "PL", "uk": "GB"}
    code = mapping.get(s.lower(), s[:2] if len(s) == 2 else "🌍")
    if code == "🌍" or len(code) != 2:
        return "🌍"
    try:
        return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper() if "A" <= c <= "Z")
    except (TypeError, ValueError):
        return "🌍"


def format_ftd(row, i):
    # Offer - IKKE campaignName. campaignNamePostfix indeholder ofte offer-delen
    offer = row.get("offerName") or row.get("offer") or row.get("lander") or row.get("campaignNamePostfix") or "?"
    country = row.get("campaignCountry", row.get("countryCode", ""))
    rev = float(row.get("allConversionsRevenue", 0) or 0) + float(row.get("customRevenue1", 0) or 0) + float(row.get("customRevenue2", 0) or 0)
    p = f"${rev:.2f}"
    flag = country_to_flag(str(country)[:2] if country else "")
    return f"{p} - {offer} - {flag}"



if __name__ == "__main__":
    token = get_token()
    rows = fetch_report(token)
    # Kampagner med konverteringer, sorteret efter updated (nyeste først)
    with_conv = [r for r in rows if (int(r.get("conversions", 0) or 0) + int(r.get("customConversions1", 0) or 0) + int(r.get("customConversions2", 0) or 0)) > 0]
    with_conv.sort(key=lambda r: r.get("updated") or r.get("created") or 0, reverse=True)
    top3 = with_conv[:3]
    if not top3:
        print("Ingen kampagner med FTD fundet")
        sys.exit(0)
    for i, row in enumerate(top3, 1):
        send_telegram(format_ftd(row, i))
        print(f"Sendt: {row.get('campaignName')}")
    print(f"✅ Sendt {len(top3)} beskeder til Telegram")
