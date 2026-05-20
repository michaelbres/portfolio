# eBay Card Monitor

Three scanners in one process — configure once, run continuously.

| Scanner | What it finds |
|---|---|
| **Chrome Mislabel** | Topps Chrome listings priced as base cards that may be unrecognized lightboard or image-variation SPs |
| **Chrome Mispriced** | Listings where the seller *did* label it as "lightboard" or "image variation" but priced it too low |
| **Pokemon Lots** | Buy-It-Now lots of Pokemon cards in LP or better condition, $300 or more |

---

## Quick Start

### 1. Get a free eBay App ID

1. Go to [developer.ebay.com](https://developer.ebay.com) → sign in with your eBay account
2. Create an app → copy your **App ID (Client ID)**
3. No OAuth required — the Finding API only needs the App ID

### 2. Set up a notification channel

**ntfy.sh (easiest — free phone push, no account)**
1. Install "ntfy" from App Store or Google Play
2. Pick any unique topic name (e.g. `cards-monitor-myname123`)
3. In the app: tap **+** → enter your topic → Subscribe
4. Paste that same topic into `config.yaml` → `ntfy_topic`

**Discord webhook (rich embeds with card images)**
1. Open Discord → your server → a channel (e.g. `#card-alerts`)
2. Edit Channel → Integrations → Webhooks → New Webhook → Copy URL
3. Paste into `config.yaml` → `discord_webhook_url`

### 3. Configure

Edit `config.yaml`:

```yaml
ebay_app_id: "YourName-App-PRD-abc123..."
ntfy_topic: "your-unique-topic-name"
# or
discord_webhook_url: "https://discord.com/api/webhooks/..."
```

Tune per-player price thresholds and add/remove players under `chrome_variations.players`.

### 4. Run

```bash
pip install -r requirements.txt
python monitor.py
```

**Options:**
```
python monitor.py --dry-run       # print matches without sending alerts
python monitor.py --once          # single scan pass, then exit (for cron)
python monitor.py --test-notify   # verify your notification channels work
python monitor.py --config p.yaml # custom config path
```

---

## How the Chrome scanners work

### Mislabel sniper

Searches `"2025 Topps Chrome NFL [player name]"` for every configured player
at prices below `max_price`. At base-card prices, any listing *could* be an
unlabeled variation — the alert fires and you visually check the photo.

### Mispriced sniper

For each player that has `lightboard_max_price` or `image_variation_max_price`
set, runs additional keyword searches like `"2025 Topps Chrome NFL Jaxson Dart lightboard"`
and `"… image variation"`. Fires when a *labeled* variation card is listed below
your market-value threshold. This catches sellers who know they have a variation
but undervalue it.

### Variation visual tells

When an alert fires, click the listing link and check the card photo:

| What you see | What it is |
|---|---|
| Dotted/halftone grid pattern in the background | **Lightboard** — worth 3–10× base |
| Rainbow chrome border, completely different photo (white jersey, sideline, no helmet) | **Image variation SP** — worth 3–8× base |
| Red/white/blue digital pixel camo border | **Camo variation** — separate SP |
| Plain silver chrome border, standard in-game photo | Base card — probably not worth buying |

---

## How the Pokemon lot scanner works

Runs 10 keyword searches (`"pokemon cards lot NM"`, `"pokemon lot near mint"`, etc.)
and pages through all results priced at $300 or more, Buy-It-Now only.

**Condition filtering (hard-coded rules):**
- ✅ Alerts on titles that mention: `NM`, `near mint`, `lightly played`, `LP`, `mint`, `PSA`, `BGS`, `CGC`
- ❌ Rejects titles that mention: `HP`, `heavily played`, `MP`, `moderately played`, `damaged`, etc.

Results are deduplicated across all 10 queries so each lot only alerts once.

**After an alert:**
- Check the listing photos for actual card condition
- Look at how many cards are in the lot and the breakdown (rares, holos, vintage vs modern)
- Check seller feedback score
- Compare price-per-card to recent eBay sold comps

---

## Tuning

| Setting | Where | Effect |
|---|---|---|
| `poll_interval_seconds` | root | How often to re-scan (floor ~60s) |
| `max_price` per player | chrome_variations | Lower = fewer but higher-signal Chrome alerts |
| `lightboard_max_price` | per player | Set to ~80% of current lightboard market price |
| `image_variation_max_price` | per player | Set to ~80% of image variation market price |
| `min_price` | pokemon_lots | Raise to filter out small lots |
| `max_pages` | pokemon_lots | Raise to scan more inventory (1 page = 100 results) |
| `search_queries` | pokemon_lots | Add/remove search terms to widen or narrow results |

## Running continuously (background)

```bash
# macOS/Linux — detach from terminal
nohup python monitor.py > monitor.log 2>&1 &
tail -f monitor.log

# Or with screen
screen -S card-monitor
python monitor.py
# Ctrl+A, D to detach; screen -r card-monitor to reattach
```

## Legacy sniper

`sniper.py` still works unchanged for the original player-only Chrome search.
`monitor.py` is a superset that adds the mispriced scanner and Pokemon lots.
