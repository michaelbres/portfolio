#!/usr/bin/env python3
"""
Card Sniper — eBay listing monitor for 2025 Topps Chrome NFL.

Watches for new Buy-It-Now listings below your price threshold for each player.
Sends a Discord alert when a potentially underpriced listing appears.

Usage:
    python sniper.py                     # uses config.yaml in same dir
    python sniper.py --config my.yaml    # custom config file
    python sniper.py --dry-run           # print matches, don't alert Discord
    python sniper.py --test-discord      # send a test Discord ping and exit

Setup:
    1. pip install -r requirements.txt
    2. Edit config.yaml — add your eBay App ID and Discord webhook URL
    3. python sniper.py
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import yaml

from ebay_client import EbayFindingClient
from notifier import send_alert, send_startup_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Config helpers ─────────────────────────────────────────────────────────────

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


# ── Title filtering ────────────────────────────────────────────────────────────

def title_matches_player(title: str, player_name: str) -> bool:
    """
    Case-insensitive check that all tokens of the player's name appear in title.
    e.g. "Brian Thomas Jr" → checks for "brian", "thomas", "jr" all present.
    Handles multi-token names robustly.
    """
    title_lower = title.lower()
    for token in player_name.lower().split():
        if token not in title_lower:
            return False
    return True


def title_has_excluded_word(title: str, exclude_keywords: list[str]) -> bool:
    title_lower = title.lower()
    for word in exclude_keywords:
        if word.lower() in title_lower:
            return True
    return False


# ── Core poll ─────────────────────────────────────────────────────────────────

def poll_once(
    config: dict,
    client: EbayFindingClient,
    seen_ids: set[str],
    dry_run: bool,
) -> list[dict]:
    """
    Run one search pass for all players.
    Returns list of new matches found.
    """
    base_kw = config.get("base_keywords", "2025 Topps Chrome NFL")
    global_max = config.get("global_max_price", 30.0)
    buy_it_now_only = config.get("buy_it_now_only", True)
    exclude_kw = config.get("exclude_keywords", [])
    webhook = config.get("discord_webhook_url", "")
    seen_path = config.get("seen_ids_file", "seen_ids.txt")
    players = config.get("players", [])

    new_hits = []

    for player in players:
        name = player["name"]
        max_price = float(player.get("max_price") or global_max)
        note = str(player.get("note") or "").strip()
        search_query = f"{base_kw} {name}"

        log.debug("Searching: %r (max $%.2f)", search_query, max_price)

        listings = client.find_new_listings(
            keywords=search_query,
            max_price=max_price,
            buy_it_now_only=buy_it_now_only,
        )

        for listing in listings:
            item_id = listing["item_id"]
            title = listing["title"]
            price = listing["price"]

            # Skip already-seen listings
            if item_id in seen_ids:
                continue

            # Mark as seen immediately to prevent re-alerting on next poll
            seen_ids.add(item_id)
            save_seen_id(seen_path, item_id)

            # Confirm the player name is actually in the title
            # (eBay keyword match can be loose)
            if not title_matches_player(title, name):
                log.debug("Skipping '%s' — player name not in title", title[:60])
                continue

            # Filter out junk listings
            if title_has_excluded_word(title, exclude_kw):
                log.debug("Skipping '%s' — excluded keyword", title[:60])
                continue

            # It's new and matches — fire the alert
            log.info(
                "MATCH  %-22s  $%-6.2f  %s",
                name,
                price,
                title[:50],
            )
            new_hits.append({"player": name, "listing": listing, "max_price": max_price})

            if not dry_run and webhook and webhook != "PASTE_YOUR_DISCORD_WEBHOOK_URL_HERE":
                send_alert(webhook, name, listing, max_price, note=note)
            elif dry_run:
                log.info("[DRY RUN] Would alert Discord for: %s", title)

    return new_hits


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="eBay card sniper for 2025 Topps Chrome NFL")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config.yaml"),
        help="Path to config YAML (default: config.yaml next to this script)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print matches but do NOT send Discord alerts",
    )
    parser.add_argument(
        "--test-discord",
        action="store_true",
        help="Send a test Discord message and exit",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single poll pass and exit (useful for cron)",
    )
    args = parser.parse_args()

    # ── Load config ────────────────────────────────────────────────────────────
    if not os.path.exists(args.config):
        log.error("Config not found: %s", args.config)
        sys.exit(1)

    config = load_config(args.config)
    seen_path = config.get("seen_ids_file", "seen_ids.txt")
    # Resolve relative path next to config file
    if not os.path.isabs(seen_path):
        seen_path = str(Path(args.config).parent / seen_path)
        config["seen_ids_file"] = seen_path

    ebay_app_id = config.get("ebay_app_id", "")
    webhook = config.get("discord_webhook_url", "")
    poll_interval = int(config.get("poll_interval_seconds", 60))
    players = config.get("players", [])

    if not ebay_app_id or ebay_app_id == "PASTE_YOUR_EBAY_APP_ID_HERE":
        log.error("Set ebay_app_id in %s first.", args.config)
        sys.exit(1)

    # ── Test Discord ────────────────────────────────────────────────────────────
    if args.test_discord:
        if not webhook or webhook == "PASTE_YOUR_DISCORD_WEBHOOK_URL_HERE":
            log.error("Set discord_webhook_url in %s first.", args.config)
            sys.exit(1)
        log.info("Sending test Discord message...")
        send_startup_message(webhook, ["[TEST] Jayden Daniels", "[TEST] Caleb Williams"])
        log.info("Done. Check your Discord channel.")
        return

    # ── Init ────────────────────────────────────────────────────────────────────
    client = EbayFindingClient(app_id=ebay_app_id)
    seen_ids = load_seen_ids(seen_path)
    log.info(
        "Card Sniper started — watching %d player(s), %d listing(s) already seen",
        len(players),
        len(seen_ids),
    )

    if not args.dry_run and webhook and webhook != "PASTE_YOUR_DISCORD_WEBHOOK_URL_HERE":
        send_startup_message(webhook, [p["name"] for p in players])

    if args.once:
        poll_once(config, client, seen_ids, dry_run=args.dry_run)
        return

    # ── Poll loop ───────────────────────────────────────────────────────────────
    while True:
        try:
            hits = poll_once(config, client, seen_ids, dry_run=args.dry_run)
            if not hits:
                log.info("No new matches. Next check in %ds...", poll_interval)
        except KeyboardInterrupt:
            log.info("Stopped by user.")
            break
        except Exception as e:
            log.error("Unexpected error during poll: %s", e, exc_info=True)
            # Don't crash — keep running, try again next interval

        try:
            time.sleep(poll_interval)
        except KeyboardInterrupt:
            log.info("Stopped by user.")
            break


if __name__ == "__main__":
    main()
