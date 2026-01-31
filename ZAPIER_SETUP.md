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
   - **Data:** Vælg "Map" og tilføj felter fra Voluum:
     - `cid` eller `clickId` → fra Voluum
     - `payout` eller `revenue` → fra Voluum
     - `campaign` eller `campaignName` → fra Voluum
     - `country` eller `countryCode` → fra Voluum
     - `offer` eller `offerName` → fra Voluum
     - `source` eller `trafficSourceName` → fra Voluum
   - Klik **Test action**

4. **Publish** Zap’en

---

## Trin 4: Test

- Når en ny FTD kommer ind i Voluum, sender Zapier til din app
- Du får besked på Telegram

**Bemærk:** På Zapier Free plan tjekkes der typisk hvert 15. minut for nye konverteringer. For hurtigere (ca. hvert minut) kræves en betalt plan.
