#!/usr/bin/env python3
"""
eBay Card Monitor — four parallel scanners in one process.

  1. Chrome Mislabel Sniper  — finds Topps Chrome cards priced as base that may
                               actually be lightboard or image-variation SPs.
  2. Chrome Mispriced Sniper — finds *labeled* lightboard / image-variation cards
                               that are priced significantly below market value.
  3. Pokemon Lot Scanner     — finds BIN lots of Pokemon cards in LP or better
                               condition, $1,000–$3,000.
  4. Sports Card Lot Scanner — finds BIN sports card collections and lots,
                               $1,000–$3,000, suitable for flipping or grading.

Usage:
    python monitor.py                   # continuous loop (uses config.yaml next to script)
    python monitor.py --dry-run         # print matches, skip all alerts
    python monitor.py --once            # single scan pass, then exit
    python monitor.py --test-notify     # send test push to all configured channels
    python monitor.py --config my.yaml  # custom config path

Setup:
    1. pip install -r requirements.txt
    2. Copy config.yaml, fill in ebay_app_id + notification channels
    3. python monitor.py
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import yaml

from ebay_client import EbayFindingClient
from notifier import (
    send_alert, send_startup_message,
    send_ntfy_alert, send_ntfy_startup,
    send_pokemon_lot_alert, send_ntfy_pokemon_lot_alert,
    send_sports_lot_alert, send_ntfy_sports_lot_alert,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Condition keyword sets ─────────────────────────────────────────────────────

# Pokemon lots: require at least one positive condition signal in the title
_POKEMON_CONDITION_GOOD = {
    "nm", "n/m", "nm-m", "nm/m", "nm+",
    "near mint", "near-mint",
    "lp", "l/p", "lp+", "nm/lp", "nm-lp",
    "lightly played", "lightly-played",
    "mint",
    "psa", "bgs", "cgc", "beckett",     # graded cards → assumed LP or better
    "gem mint", "gem-mint",
    "ex/nm", "ex+", "excellent",
}

# Reject any listing containing these (shared bad-condition signals)
_CONDITION_BAD = {
    "hp",
    "heavily played", "heavy played",
    "mp",
    "moderately played", "moderate played",
    "poor condition",
    "damaged",
    "water damage",
    "bent", "creased",
}

# Alias used by Pokemon scanner
_POKEMON_CONDITION_BAD = _CONDITION_BAD

# Sports lots: sellers at $1k+ rarely state condition in the title.
# We only reject explicit bad-condition signals — no positive keyword required.
_SPORTS_COLLECTION_KEYWORDS = {
    "lot", "collection", "estate", "bundle", "bulk",
    "set", "complete set", "run", "hoard", "haul", "case",
    "break", "cards",
}


# ── Config / state helpers ─────────────────────────────────────────────────────

def load_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def load_seen_ids(path: str) -> set[str]:
    p = Path(path)
    if not p.exists():
        return set()
    return set(p.read_text().splitlines())


def save_seen_id(path: str, item_id: str) -> None:
    with open(path, "a") as f:
        f.write(item_id + "\n")


def _mark_seen(seen_ids: set[str], seen_path: str, item_id: str) -> None:
    seen_ids.add(item_id)
    save_seen_id(seen_path, item_id)


# ── Title utilities ────────────────────────────────────────────────────────────

def _title_lower(listing: dict) -> str:
    return listing["title"].lower()


def title_matches_player(title: str, player_name: str) -> bool:
    tl = title.lower()
    return all(token in tl for token in player_name.lower().split())


def title_has_any(title_lower: str, keywords: set[str]) -> bool:
    return any(kw in title_lower for kw in keywords)


def title_has_excluded_word(title: str, exclude_keywords: list[str]) -> bool:
    tl = title.lower()
    return any(word.lower() in tl for word in exclude_keywords)


# ── Scanner 1: Chrome mislabel sniper ─────────────────────────────────────────
# Searches for base-priced Chrome listings that might be unlabeled variations.

def poll_chrome_mislabel(
    config: dict,
    client: EbayFindingClient,
    seen_ids: set[str],
    dry_run: bool,
) -> list[dict]:
    """
    Search for each player's Topps Chrome listings under their base-card price
    threshold. Any result is potentially a mislabeled lightboard or image SP.
    """
    chrome_cfg = config.get("chrome_variations", {})
    if not chrome_cfg.get("enabled", True):
        return []

    base_kw = chrome_cfg.get("base_keywords", "2025 Topps Chrome NFL")
    global_max = float(chrome_cfg.get("global_max_price", 30.0))
    exclude_kw = chrome_cfg.get("exclude_keywords", [])
    seen_path = config["seen_ids_file"]
    players = chrome_cfg.get("players", [])
    webhook = config.get("discord_webhook_url", "")
    ntfy_topic = config.get("ntfy_topic", "")

    new_hits = []

    for player in players:
        name = player["name"]
        max_price = float(player.get("max_price") or global_max)
        note = str(player.get("note") or "").strip()
        search_query = f"{base_kw} {name}"

        listings = client.find_new_listings(
            keywords=search_query,
            max_price=max_price,
        )

        for listing in listings:
            item_id = listing["item_id"]
            title = listing["title"]
            price = listing["price"]

            if item_id in seen_ids:
                continue
            _mark_seen(seen_ids, seen_path, item_id)

            if not title_matches_player(title, name):
                continue
            if title_has_excluded_word(title, exclude_kw):
                continue

            log.info(
                "CHROME MISLABEL  %-22s  $%-6.2f  %s",
                name, price, title[:50],
            )
            new_hits.append({"type": "chrome_mislabel", "player": name, "listing": listing, "max_price": max_price})

            if not dry_run:
                if ntfy_topic:
                    send_ntfy_alert(ntfy_topic, name, listing, max_price)
                if webhook and webhook != "PASTE_YOUR_DISCORD_WEBHOOK_URL_HERE":
                    send_alert(webhook, name, listing, max_price, note=note)

    return new_hits


# ── Scanner 2: Chrome mispriced sniper ────────────────────────────────────────
# Finds cards that ARE labeled as lightboard/image-variation but underpriced.

def poll_chrome_mispriced(
    config: dict,
    client: EbayFindingClient,
    seen_ids: set[str],
    dry_run: bool,
) -> list[dict]:
    """
    Search for explicitly labeled variation cards (lightboard, image variation,
    SP) that are listed below known market thresholds.
    """
    chrome_cfg = config.get("chrome_variations", {})
    if not chrome_cfg.get("enabled", True):
        return []

    base_kw = chrome_cfg.get("base_keywords", "2025 Topps Chrome NFL")
    seen_path = config["seen_ids_file"]
    players = chrome_cfg.get("players", [])
    webhook = config.get("discord_webhook_url", "")
    ntfy_topic = config.get("ntfy_topic", "")

    # Variation-type → search suffix + label
    variation_searches = [
        ("lightboard", "lightboard", "Lightboard"),
        ("image variation", "image variation", "Image Variation"),
        ("image sp", "image sp", "Image SP"),
        ("photo variation", "photo variation", "Photo Variation"),
        ("image var", "image var", "Image Var"),
    ]

    new_hits = []

    for player in players:
        name = player["name"]
        note = str(player.get("note") or "").strip()

        for suffix, _kw, label in variation_searches:
            max_price = float(
                player.get(f"{suffix.replace(' ', '_')}_max_price") or
                player.get("lightboard_max_price") or 0
            )
            if max_price <= 0:
                continue

            search_query = f"{base_kw} {name} {suffix}"

            listings = client.find_new_listings(
                keywords=search_query,
                max_price=max_price,
            )

            for listing in listings:
                item_id = listing["item_id"]
                title = listing["title"]
                price = listing["price"]

                if item_id in seen_ids:
                    continue
                _mark_seen(seen_ids, seen_path, item_id)

                if not title_matches_player(title, name):
                    continue

                label_note = (
                    f"⚡ Labeled **{label}** but priced at only ${price:.2f} "
                    f"(threshold ${max_price:.2f}) — likely underpriced by seller.\n\n"
                    f"{note}"
                )

                log.info(
                    "CHROME MISPRICED %-22s  $%-6.2f  [%s]  %s",
                    name, price, label, title[:40],
                )
                new_hits.append({
                    "type": "chrome_mispriced",
                    "player": name,
                    "variation": label,
                    "listing": listing,
                    "max_price": max_price,
                })

                if not dry_run:
                    if ntfy_topic:
                        send_ntfy_alert(ntfy_topic, f"{name} {label} (UNDERPRICED)", listing, max_price)
                    if webhook and webhook != "PASTE_YOUR_DISCORD_WEBHOOK_URL_HERE":
                        send_alert(webhook, f"{name} — {label} Underpriced", listing, max_price, note=label_note)

    return new_hits


# ── Scanner 3: Pokemon lot monitor ────────────────────────────────────────────

def _pokemon_condition_ok(title_lower: str) -> bool:
    """
    Returns True if the title signals LP-or-better condition.
    Rejects explicit bad-condition signals. Passes through untested titles
    (no condition keywords at all) rather than silently dropping them.
    """
    if title_has_any(title_lower, _POKEMON_CONDITION_BAD):
        return False
    # Require at least one positive condition signal
    return title_has_any(title_lower, _POKEMON_CONDITION_GOOD)


def poll_pokemon_lots(
    config: dict,
    client: EbayFindingClient,
    seen_ids: set[str],
    dry_run: bool,
) -> list[dict]:
    """
    Scans for Pokemon card lots: BIN, LP or better condition, $1k–$3k.
    Paginates across all results so no listings are missed.
    """
    poke_cfg = config.get("pokemon_lots", {})
    if not poke_cfg.get("enabled", True):
        return []

    min_price = float(poke_cfg.get("min_price", 1000.0))
    max_price_cfg = poke_cfg.get("max_price")
    max_price = float(max_price_cfg) if max_price_cfg is not None else None
    max_pages = int(poke_cfg.get("max_pages", 5))
    search_queries = poke_cfg.get("search_queries", ["pokemon cards lot NM LP"])
    extra_exclude = poke_cfg.get("exclude_keywords", [])
    seen_path = config["seen_ids_file"]
    webhook = config.get("discord_webhook_url", "")
    ntfy_topic = config.get("ntfy_topic", "")

    new_hits = []
    seen_this_pass: set[str] = set()

    for query in search_queries:
        log.debug("Pokemon lots: %r  $%.0f–%s", query, min_price, f"${max_price:.0f}" if max_price else "∞")

        listings = client.find_items_all_pages(
            keywords=query,
            min_price=min_price,
            max_price=max_price,
            buy_it_now_only=True,
            max_pages=max_pages,
        )

        for listing in listings:
            item_id = listing["item_id"]
            title = listing["title"]
            price = listing["price"]
            tl = title.lower()

            if item_id in seen_ids or item_id in seen_this_pass:
                continue

            if "pokemon" not in tl:
                continue

            if not _pokemon_condition_ok(tl):
                log.debug("Skipping (condition) '%s'", title[:60])
                continue

            if title_has_excluded_word(title, extra_exclude):
                log.debug("Skipping (excluded kw) '%s'", title[:60])
                continue

            seen_this_pass.add(item_id)
            _mark_seen(seen_ids, seen_path, item_id)

            log.info("POKEMON LOT  $%-8.2f  %s", price, title[:55])
            new_hits.append({"type": "pokemon_lot", "listing": listing})

            if not dry_run:
                if ntfy_topic:
                    send_ntfy_pokemon_lot_alert(ntfy_topic, listing)
                if webhook and webhook != "PASTE_YOUR_DISCORD_WEBHOOK_URL_HERE":
                    send_pokemon_lot_alert(webhook, listing)

    return new_hits


# ── Scanner 4: Sports card lot monitor ────────────────────────────────────────

def poll_sports_lots(
    config: dict,
    client: EbayFindingClient,
    seen_ids: set[str],
    dry_run: bool,
) -> list[dict]:
    """
    Scans for sports card collections/lots: BIN, $1k–$3k.
    Does not require condition keywords in title — sellers at this price range
    rarely label condition, so we just reject explicit bad-condition signals.
    Confirms the listing looks like a collection (lot/collection/estate keywords)
    to filter out expensive singles.
    """
    sports_cfg = config.get("sports_card_lots", {})
    if not sports_cfg.get("enabled", True):
        return []

    min_price = float(sports_cfg.get("min_price", 1000.0))
    max_price_cfg = sports_cfg.get("max_price")
    max_price = float(max_price_cfg) if max_price_cfg is not None else None
    max_pages = int(sports_cfg.get("max_pages", 5))
    search_queries = sports_cfg.get("search_queries", ["sports cards lot collection"])
    extra_exclude = sports_cfg.get("exclude_keywords", [])
    seen_path = config["seen_ids_file"]
    webhook = config.get("discord_webhook_url", "")
    ntfy_topic = config.get("ntfy_topic", "")

    new_hits = []
    seen_this_pass: set[str] = set()

    for query in search_queries:
        log.debug("Sports lots: %r  $%.0f–%s", query, min_price, f"${max_price:.0f}" if max_price else "∞")

        listings = client.find_items_all_pages(
            keywords=query,
            min_price=min_price,
            max_price=max_price,
            buy_it_now_only=True,
            max_pages=max_pages,
        )

        for listing in listings:
            item_id = listing["item_id"]
            title = listing["title"]
            price = listing["price"]
            tl = title.lower()

            if item_id in seen_ids or item_id in seen_this_pass:
                continue

            # Reject explicit bad-condition signals
            if title_has_any(tl, _CONDITION_BAD):
                log.debug("Skipping (bad condition) '%s'", title[:60])
                continue

            # Must look like a collection not a single card
            if not title_has_any(tl, _SPORTS_COLLECTION_KEYWORDS):
                log.debug("Skipping (looks like single) '%s'", title[:60])
                continue

            if title_has_excluded_word(title, extra_exclude):
                log.debug("Skipping (excluded kw) '%s'", title[:60])
                continue

            seen_this_pass.add(item_id)
            _mark_seen(seen_ids, seen_path, item_id)

            log.info("SPORTS LOT   $%-8.2f  %s", price, title[:55])
            new_hits.append({"type": "sports_lot", "listing": listing})

            if not dry_run:
                if ntfy_topic:
                    send_ntfy_sports_lot_alert(ntfy_topic, listing)
                if webhook and webhook != "PASTE_YOUR_DISCORD_WEBHOOK_URL_HERE":
                    send_sports_lot_alert(webhook, listing)


# ── Unified poll ──────────────────────────────────────────────────────────────

def poll_once(
    config: dict,
    client: EbayFindingClient,
    seen_ids: set[str],
    dry_run: bool,
) -> list[dict]:
    hits: list[dict] = []
    hits += poll_chrome_mislabel(config, client, seen_ids, dry_run)
    hits += poll_chrome_mispriced(config, client, seen_ids, dry_run)
    hits += poll_pokemon_lots(config, client, seen_ids, dry_run)
    hits += poll_sports_lots(config, client, seen_ids, dry_run)
    return hits


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="eBay card monitor — Chrome variations + Pokemon/sports lots")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config.yaml"),
        help="Path to config YAML",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print matches, skip alerts")
    parser.add_argument("--once", action="store_true", help="Single poll then exit")
    parser.add_argument("--test-notify", action="store_true", help="Send test alerts and exit")
    args = parser.parse_args()

    if not os.path.exists(args.config):
        log.error("Config not found: %s", args.config)
        sys.exit(1)

    config = load_config(args.config)

    seen_path = config.get("seen_ids_file", "seen_ids.txt")
    if not os.path.isabs(seen_path):
        seen_path = str(Path(args.config).parent / seen_path)
    config["seen_ids_file"] = seen_path

    ebay_app_id = config.get("ebay_app_id", "")
    if not ebay_app_id or ebay_app_id == "PASTE_YOUR_EBAY_APP_ID_HERE":
        log.error("Set ebay_app_id in %s first.", args.config)
        sys.exit(1)

    webhook = config.get("discord_webhook_url", "")
    ntfy_topic = config.get("ntfy_topic", "")
    poll_interval = int(config.get("poll_interval_seconds", 90))

    chrome_cfg = config.get("chrome_variations", {})
    players = chrome_cfg.get("players", [])
    poke_cfg = config.get("pokemon_lots", {})
    pokemon_enabled = poke_cfg.get("enabled", True)
    pokemon_min = float(poke_cfg.get("min_price", 1000.0))
    pokemon_max = poke_cfg.get("max_price")
    sports_cfg = config.get("sports_card_lots", {})
    sports_enabled = sports_cfg.get("enabled", True)
    sports_min = float(sports_cfg.get("min_price", 1000.0))
    sports_max = sports_cfg.get("max_price")

    def _price_range(lo: float, hi) -> str:
        return f"${lo:.0f}–${float(hi):.0f}" if hi else f"${lo:.0f}+"

    if args.test_notify:
        sent = False
        watch_summary = [p["name"] for p in players]
        if pokemon_enabled:
            watch_summary.append(f"Pokemon lots BIN {_price_range(pokemon_min, pokemon_max)}")
        if sports_enabled:
            watch_summary.append(f"Sports card lots BIN {_price_range(sports_min, sports_max)}")
        if ntfy_topic:
            log.info("Sending test ntfy push to topic '%s'...", ntfy_topic)
            send_ntfy_startup(ntfy_topic, watch_summary)
            sent = True
        if webhook and webhook != "PASTE_YOUR_DISCORD_WEBHOOK_URL_HERE":
            log.info("Sending test Discord embed...")
            send_startup_message(webhook, watch_summary)
            sent = True
        if not sent:
            log.error("No notification channel configured. Set ntfy_topic or discord_webhook_url.")
            sys.exit(1)
        log.info("Done. Check your phone/Discord.")
        return

    client = EbayFindingClient(app_id=ebay_app_id)
    seen_ids = load_seen_ids(seen_path)

    log.info(
        "Monitor started — %d Chrome player(s) | Pokemon lots %s | Sports lots %s | %d seen",
        len(players),
        _price_range(pokemon_min, pokemon_max) if pokemon_enabled else "disabled",
        _price_range(sports_min, sports_max) if sports_enabled else "disabled",
        len(seen_ids),
    )

    if not args.dry_run:
        watch_summary = [p["name"] for p in players]
        if pokemon_enabled:
            watch_summary.append(f"Pokemon lots BIN {_price_range(pokemon_min, pokemon_max)}")
        if sports_enabled:
            watch_summary.append(f"Sports card lots BIN {_price_range(sports_min, sports_max)}")
        if ntfy_topic:
            send_ntfy_startup(ntfy_topic, watch_summary)
        if webhook and webhook != "PASTE_YOUR_DISCORD_WEBHOOK_URL_HERE":
            send_startup_message(webhook, watch_summary)

    if args.once:
        poll_once(config, client, seen_ids, dry_run=args.dry_run)
        return

    while True:
        try:
            hits = poll_once(config, client, seen_ids, dry_run=args.dry_run)
            if not hits:
                log.info("No new matches. Next check in %ds...", poll_interval)
        except KeyboardInterrupt:
            log.info("Stopped by user.")
            break
        except Exception as e:
            log.error("Poll error: %s", e, exc_info=True)

        try:
            time.sleep(poll_interval)
        except KeyboardInterrupt:
            log.info("Stopped by user.")
            break


if __name__ == "__main__":
    main()
