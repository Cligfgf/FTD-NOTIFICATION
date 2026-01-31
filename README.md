# Voluum FTD Telegram Bot

Real-time FTD (First Time Deposit) notifikationer fra Voluum til Telegram.

## Quick Setup

### 1. Opret Telegram Bot

1. Åbn Telegram og find **@BotFather**
2. Send `/newbot` og følg instruktionerne
3. Kopier bot token (ligner: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Find dit Chat ID

1. Start en chat med din nye bot og send en besked
2. Åbn i browser: `https://api.telegram.org/bot<DIN_TOKEN>/getUpdates`
3. Find `"chat":{"id": XXXXXX}` - tallet er dit chat ID
4. For grupper: Tilføj botten til gruppen først, send en besked, og tjek igen

### 3. Konfigurer serveren

```bash
cd voluum-telegram-bot
cp .env.example .env
# Rediger .env med dine værdier
```

### 4. Kør lokalt (til test)

```bash
pip install -r requirements.txt
python app.py
```

### 5. Test at det virker

Åbn i browser: `http://localhost:5000/test`

Du skulle nu modtage en test-besked på Telegram!

---

## ⚡ INSTANT notifikationer (anbefales)

For **øjeblikkelige** FTD-beskeder skal du bruge **postback** – ikke API polling.

### Hurtig opsætning med ngrok

1. **Download ngrok:** https://ngrok.com/download (gratis)
2. **Start serveren:**
   ```bash
   cd voluum-telegram-bot
   python3 app.py
   ```
3. **I en ny terminal – eksponér til internet:**
   ```bash
   ngrok http 5001
   ```
4. **Kopiér HTTPS URL** (fx `https://abc123.ngrok.io`)
5. **I Voluum:** Settings → Postback URLs → Create
6. **Postback URL:**
   ```
   https://DIN-NGROK-URL/postback?cid={clickid}&payout={payout}&campaign={campaignname}&country={country}&offer={offername}&source={trafficsourcename}
   ```
7. Vælg din Affiliate Network og Conversion type: FTD
8. Gem – nu får du besked **øjeblikkeligt** ved hver FTD

**Bemærk:** ngrok URL ændres ved genstart (gratis). For permanent URL: deploy til Railway/Render.

---

## Alternativ: API Polling (forsinkelse 5-30 min)

Du kan hente FTD direkte fra Voluum API – ingen server-deployment nødvendig.

### Tilføj Voluum credentials til .env

```
VOLUUM_EMAIL=din@email.dk
VOLUUM_PASSWORD=dit_password
```

Eller brug **Access Keys** (anbefales): Voluum → Settings → Security → Access Keys

```
VOLUUM_ACCESS_KEY_ID=din_key
VOLUUM_ACCESS_KEY_SECRET=din_secret
```

### Kør polling-scriptet

```bash
python3 voluum_poll.py
```

Scriptet tjekker Voluum hvert 60. sekund (ændres med `POLL_INTERVAL` i .env) og sender nye FTD til Telegram.

**Bemærk:** Voluum API-strukturen kan variere. Hvis du får fejl, åbn Voluum panel → F12 → Network → se hvordan report-requests ser ud, og tjek [developers.voluum.com](https://developers.voluum.com).

---

## Voluum Postback Setup

I Voluum skal du sætte en postback URL op der peger på din server.

### Postback URL Format

```
https://din-server.com/postback?cid={clickid}&payout={payout}&campaign={campaignname}&country={country}&offer={offername}&source={trafficsourcename}
```

### Tilgængelige Voluum Tokens

| Token | Beskrivelse |
|-------|-------------|
| `{clickid}` | Voluum click ID |
| `{payout}` | Konverteringspayout |
| `{revenue}` | Revenue |
| `{campaignname}` | Kampagne navn |
| `{country}` | Land (2-bogstavs kode) |
| `{offername}` | Offer navn |
| `{trafficsourcename}` | Traffic source navn |
| `{var1}` - `{var10}` | Custom variables |

### Opsætning i Voluum

1. Gå til **Settings** → **Postback URLs**
2. Klik **Create**
3. Vælg din **Affiliate Network**
4. Sæt **Postback URL** til din server URL med tokens
5. Vælg **Conversion type**: FTD (eller den konverteringstype du vil tracke)
6. Gem

---

## Hosting Options

### Option 1: Railway.app (Anbefalet - Gratis tier)

1. Push koden til GitHub
2. Opret konto på [railway.app](https://railway.app)
3. New Project → Deploy from GitHub
4. Tilføj environment variables (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
5. Railway giver dig en URL som: `your-app.railway.app`

### Option 2: Render.com

1. Opret konto på [render.com](https://render.com)
2. New → Web Service → Connect GitHub repo
3. Settings:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
4. Tilføj environment variables

### Option 3: VPS (DigitalOcean, Hetzner, etc.)

```bash
# På serveren
git clone <your-repo>
cd voluum-telegram-bot
pip install -r requirements.txt

# Kør med gunicorn
gunicorn -w 2 -b 0.0.0.0:5000 app:app

# Eller brug systemd service for at køre permanent
```

### Option 4: Lokal med ngrok (til test)

```bash
# Terminal 1
python app.py

# Terminal 2
ngrok http 5000
```

Brug ngrok URL'en som din Voluum postback URL.

---

## API Endpoints

| Endpoint | Method | Beskrivelse |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/postback` | GET/POST | Modtag Voluum postback |
| `/test` | GET | Send test notification |

---

## Troubleshooting

### Ingen beskeder modtages

1. Tjek at bot token og chat ID er korrekte
2. Sørg for at du har startet en chat med botten
3. Tjek server logs for fejl
4. Test med `/test` endpoint

### Postback virker ikke

1. Tjek at Voluum postback URL er korrekt
2. Tjek at serveren er tilgængelig fra internettet
3. Se server logs for indkommende requests

### Chat ID for grupper

For grupper er chat ID negativt (f.eks. `-123456789`). Sørg for at inkludere minus-tegnet.
