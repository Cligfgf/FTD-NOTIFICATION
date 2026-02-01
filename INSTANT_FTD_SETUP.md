# Instant FTD – Live notifikationer til Telegram

For **øjeblikkelige** FTD-beskeder (ikke 15 min forsinkelse) skal postback komme **direkte** fra affiliate-netværket til vores server.

---

## Sådan virker det (instant)

```
Affiliate får FTD → Sender postback til vores Railway URL → Vi sender til Telegram + videresender til Voluum
```

**Ingen Zapier, ingen polling – beskeden kommer med det samme.**

---

## Trin 1: Railway Variables

I Railway → dit projekt → Variables, sørg for:

| Variable | Værdi |
|----------|-------|
| `TELEGRAM_BOT_TOKEN` | Din bot token |
| `TELEGRAM_CHAT_ID` | Gruppens ID (fx `-5135606632`) |
| `VOLUUM_FORWARD_URL` | Din Voluum tracking domain (fx `https://lowasteisranime.com`) |

---

## Trin 2: Postback URL i affiliate-netværket

I **hvert** affiliate-netværk, hvor du har offers:  
Sæt **Postback URL** til vores endpoint:

```
https://web-production-d7e9.up.railway.app/postback
```

Med parametre som netværket understøtter, fx:

- `?cid={clickid}` eller `?clickid={clickid}`
- `&payout={payout}` eller `&amount={payout}`
- `&txid={transactionid}` (hvis de har det)

**Eksempel (hvis netværket bruger standard postback):**
```
https://web-production-d7e9.up.railway.app/postback?cid={clickid}&payout={payout}&txid={txid}
```

---

## Trin 3: VOLUUM_FORWARD_URL

Sæt `VOLUUM_FORWARD_URL` til den URL, Voluum normalt bruger (fx din tracking domain).  
Vi videresender postback derhen, så Voluum stadig modtager alle konverteringer.

---

## Flow

1. Bruger laver FTD på casino/site
2. Affiliate-netværket sender postback til vores Railway URL
3. Vi modtager den, sender besked til Telegram-gruppen og videresender til Voluum
4. Beskeden er i Telegram næsten med det samme

---

## Hvis du ikke kan ændre postback

Hvis du ikke må/skal ændre postback-URL i affiliate-netværket:

- **Zapier:** Voluum trigger → Webhooks POST til vores `/postback`
- Sæt **Polling interval** til **1 minut** i Zap:  
  Zap-editor → tandhjuls-ikon → **Polling interval** → 1 minute  
  (Kun hvis din Zapier-plan tillader det)

Det giver stadig 1–15 min forsinkelse, ikke rigtig “live”.

---

## Test

Åbn i browseren:
```
https://web-production-d7e9.up.railway.app/postback?cid=test123&payout=150&country=Germany&offer=TestOffer
```

Du bør få en FTD-besked i Telegram-gruppen med det samme.
