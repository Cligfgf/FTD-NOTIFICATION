# Zapier opsætning – Voluum FTD til Telegram

## Trin 1: Push opdateret kode til GitHub

```bash
cd ~/Desktop/voluum-telegram-bot
git add .
git commit -m "Zapier support"
git push
```

(Railway deployer automatisk ved push)

---

## Trin 2: Opret Zapier konto

1. Gå til **zapier.com**
2. Klik **Sign up** (gratis)
3. Opret konto med email

---

## Trin 3: Opret Zap

1. Klik **Create Zap**
2. **Trigger (When this happens):**
   - Søg efter **Voluum**
   - Vælg **Voluum**
   - Vælg trigger: **Conversion** eller **Get Conversion** / **New Conversion**
   - Klik **Sign in to Voluum** – log ind med dine Voluum credentials
   - Vælg konto
   - Klik **Test trigger** – Zapier henter en test-konvertering

3. **Filter (valgfrit men anbefales):**
   - Klik **+** mellem Get Conversion og POST
   - Vælg **Filter**
   - Betingelse: **Payout** (fra Get Conversion) **is greater than** **0**
   - Så sendes kun konverteringer med revenue til din app

4. **Action (Do this):**
   - Klik **+** (Add step)
   - Søg efter **Webhooks by Zapier**
   - Vælg **POST**
   - **URL:** `https://DIN-RAILWAY-URL/postback`
     (Erstat med din Railway URL – fx `https://web-production-d7e9.up.railway.app/postback`)
   - **Payload Type:** JSON
   - **Data:** Vælg "Map" og tilføj felter fra Voluum (vælg fra dropdown – **ikke** skriv manuelt):
     - **Revenue** eller **Payout** → VIGTIGT, kræves for FTD-besked
     - `cid` eller `clickId`
     - `offer` eller `offerName` eller `Lander name`
     - `country` eller `countryCode`
     - `campaign` eller `campaignName`
     - `conversionType` eller `Conversion type` (valgfrit)
   - Klik **Test action**

4. **Publish** Zap’en

---

## Trin 4: Test

- Når en ny FTD kommer ind i Voluum, sender Zapier til din app
- Du får besked på Telegram

**Bemærk:** På Zapier Free plan tjekkes der typisk hvert 15. minut for nye konverteringer. For hurtigere (ca. hvert minut) kræves en betalt plan.

---

## Alternativ: Hent de 3 seneste FTD'er (Zapier Schedule)

Hent de **3 seneste FTD'er** fra Voluum og send til Telegram-gruppen:

1. **Create Zap**
2. **Trigger:** Søg **Schedule by Zapier** → vælg **Every 15 minutes** (eller 30 min)
3. **Action:** Søg **Webhooks by Zapier** → vælg **GET**
4. **URL:** `https://web-production-d7e9.up.railway.app/fetch-ftds?secret=DIT_CRON_SECRET`
   - Erstat `DIT_CRON_SECRET` med samme værdi som `CRON_SECRET` i Railway Variables
5. **Publish** Zap'en

**Vigtigt:** Sæt `TELEGRAM_CHAT_ID` i Railway til gruppe-id (fx `-5135606632`) så beskeder kommer i gruppen.

---

## Fejlfinding: FTD kommer ikke

1. **Tjek at Zap er slået til** (Published, ikke Draft)
2. **Tjek POST URL** – skal være `https://web-production-d7e9.up.railway.app/postback` (eller din Railway URL)
3. **Tjek felt-mapping** – i Webhooks-step: vælg felter fra Voluum (ikke skriv feltnavne manuelt). Vigtigst: **Revenue** eller **Payout** med talværdi > 0
4. **Test** – i Zapier: Test trigger → Test action. Tjek at POST får 200 OK
5. **Brug /diagnose** – åbn `https://DIN-RAILWAY-URL/diagnose` i browser. Viser sidste postback-resultat (ok/skipped/error)
6. **Brug /debug** – sæt POST URL midlertidigt til `.../debug` for at se præcis hvad Zapier sender. Skift tilbage til `/postback` bagefter
7. **Railway logs** – i Railway: Logs-tab. Se om requests ankommer og evt. fejlmeddelelser
