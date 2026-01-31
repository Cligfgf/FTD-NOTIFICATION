#!/bin/bash
# Start instant FTD notifikationer via Voluum Postback
# Kræver: Server kører + eksponeret til internet (ngrok/localtunnel)

cd "$(dirname "$0")"

echo "Starter Voluum Postback Server på port 5001..."
echo ""

# Stop evt. eksisterende proces på port 5001
lsof -ti:5001 | xargs kill -9 2>/dev/null

# Start Flask server i baggrunden
python3 app.py &
APP_PID=$!
sleep 2

if ! kill -0 $APP_PID 2>/dev/null; then
    echo "❌ Kunne ikke starte server. Tjek at port 5001 er ledig."
    exit 1
fi

echo "✅ Server kører på http://localhost:5001"
echo ""
echo "For INSTANT notifikationer skal serveren være tilgængelig fra internet."
echo ""
echo "Option 1 - ngrok (anbefales):"
echo "  1. Download ngrok: https://ngrok.com/download"
echo "  2. I en NY terminal: ngrok http 5001"
echo "  3. Kopiér HTTPS URL (fx https://xxx.ngrok.io)"
echo "  4. I Voluum: Settings → Postback URLs → Create"
echo "  5. Postback URL: https://xxx.ngrok.io/postback?cid={clickid}&payout={payout}&campaign={campaignname}&country={country}&offer={offername}&source={trafficsourcename}"
echo ""
echo "Option 2 - Railway (permanent):"
echo "  1. Gå til railway.app"
echo "  2. Deploy fra GitHub med denne kode"
echo "  3. Tilføj TELEGRAM_BOT_TOKEN og TELEGRAM_CHAT_ID som env vars"
echo "  4. Brug Railway URL i Voluum postback"
echo ""
echo "Tryk Ctrl+C for at stoppe serveren"
wait $APP_PID
