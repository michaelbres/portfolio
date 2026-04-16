# Card Sniper — 2025 Topps Chrome NFL

Monitors eBay for new BIN listings that may be mislabeled variation cards.

## How it works

1. Every 60 seconds, searches eBay for each player in your list
2. Filters listings under your price threshold
3. Pings your Discord channel with a rich embed when a new one appears
4. You look at the image — if it's a variation listed as a base, you buy it

## Setup

### 1. Get an eBay App ID (free)

1. Go to [developer.ebay.com](https://developer.ebay.com) and sign in with your eBay account
2. Create an application → get your **App ID (Client ID)**
3. No OAuth needed — the Finding API just needs the App ID

### 2. Create a Discord webhook

1. Open your Discord server → go to a channel (e.g. `#card-alerts`)
2. Edit Channel → Integrations → Webhooks → New Webhook
3. Copy the webhook URL

### 3. Configure

Edit `config.yaml`:

```yaml
discord_webhook_url: "https://discord.com/api/webhooks/..."
ebay_app_id: "YourName-App-PRD-..."
```

Add or remove players under the `players:` list. Set `max_price` per player — this is the ceiling where you'd still buy a base card (so variations at that price are underpriced).

### 4. Run

```bash
pip install -r requirements.txt
python sniper.py
```

**Options:**
```
python sniper.py --dry-run          # test matching without Discord alerts
python sniper.py --test-discord     # verify your webhook works
python sniper.py --once             # single scan (for cron)
python sniper.py --config my.yaml   # custom config path
```

## What to look for

When you get an alert, click the listing link and check the **card image**:

| Sign of a variation | What it means |
|---|---|
| Different photo/pose than the base | Image variation — worth 5–50× more |
| Black/white or inverted colors | Negative refractor |
| Gold/chrome border shimmer | Shimmer/Cosmic refractor |
| Different uniform or background | Short print variant |

Base cards have a clean chrome finish with one standard photo. Anything different is potentially a variation.

## Running continuously (background)

**macOS/Linux — keep running in terminal:**
```bash
nohup python sniper.py > sniper.log 2>&1 &
tail -f sniper.log
```

**Or with screen:**
```bash
screen -S sniper
python sniper.py
# Ctrl+A, D to detach
```

## Tuning

- Lower `poll_interval_seconds` for faster detection (min ~45s to stay in eBay rate limits)
- Lower `max_price` per player = fewer alerts but higher signal quality
- Add players to the `players:` list at any time — restart sniper to pick up changes
- `buy_it_now_only: false` to also watch auctions (you'd need to bid, not snipe)
