# Retail Monitor (Python)

A 24/7 Discord alert bot that monitors **Amazon, Best Buy, Walmart, Target, Nike SNKRS, and Footsites** for deals, coupons, restocks, and limited releases.

## What it monitors

| Store | What triggers an alert |
|-------|----------------------|
| **Amazon** | Coupon codes (any %), price drops ≥15%, freebies ($0), restocks |
| **Best Buy** | Price drops ≥10%, restocks on consoles / GPUs / Apple products |
| **Walmart** | Price drops ≥15% (Rollbacks), restocks |
| **Target** | Price drops ≥10% (Circle deals), restocks |
| **Nike SNKRS** | Live drops going available, upcoming releases, style-code watchlist restocks |
| **Footsites** | Jordan / Adidas restock alerts with available sizes (Kasada-evaded) |

## Setup

### 1. Clone & install

```bash
git clone <your-repo-url>
cd retail-monitor-python
pip install -r requirements.txt
playwright install chromium --with-deps
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env and fill in your Discord webhook URLs
```

Required variables:
```
AMAZON_WEBHOOK_URL
BESTBUY_WEBHOOK_URL
WALMART_WEBHOOK_URL
TARGET_WEBHOOK_URL
FOOTSITES_WEBHOOK_URL
NIKE_SNKRS_WEBHOOK_URL
UPCOMING_DROPS_WEBHOOK_URL
COOK_GROUP_NAME        # Your group's name shown in embeds
COOK_GROUP_ICON_URL    # Icon URL shown in embed footers
```

### 3. (Optional) Set up your Discord server

```bash
# Add BOT_TOKEN and GUILD_ID to .env first
python discord_setup.py
```

This creates all roles, categories, and monitor channels automatically.

### 4. Run locally

```bash
python main.py
```

## Deploying to Railway

```bash
railway login
railway init          # creates a new Railway project
railway up            # deploys
railway vars set AMAZON_WEBHOOK_URL=https://discord.com/api/webhooks/...
# set all other webhook URLs the same way
```

Or connect your GitHub repo in the Railway dashboard and it auto-deploys on every push.

## Adding products

Edit [config/products.py](config/products.py) and add product URLs to the appropriate list.
No code changes needed — just paste the URL and restart.

## Anti-bot techniques used

| Site | Method |
|------|--------|
| All HTTP-based sites | `curl_cffi` with Chrome TLS fingerprint (JA3/JA4 impersonation) |
| Footsites (Kasada) | Playwright + `playwright-stealth` (patches `navigator.webdriver`, WebGL, plugins) |
| Amazon | UA rotation + CAPTCHA detection → 2-hour IP backoff |
| Walmart / Target / BB | UA rotation + rate-limit backoff (30–60 min) |

## Project structure

```
retail-monitor-python/
├── main.py              # Async orchestrator — runs all monitors concurrently
├── config/
│   ├── settings.py      # Environment variables
│   └── products.py      # All monitored product URLs
├── monitors/
│   ├── base.py          # BaseMonitor with error-resilient loop
│   ├── amazon.py
│   ├── bestbuy.py
│   ├── walmart.py
│   ├── target.py
│   ├── nike_snkrs.py
│   └── footsites.py
├── utils/
│   ├── discord_client.py   # Webhook sender with rich embeds
│   ├── anti_bot.py         # curl_cffi sessions, UA rotation, headers
│   └── storage.py          # Async JSON persistence
└── discord_setup.py     # One-time server setup script
```
