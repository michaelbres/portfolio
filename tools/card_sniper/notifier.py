"""
Notification backends for card sniper alerts.

Supports two channels — configure one or both in config.yaml:
  1. Discord webhook  — rich embed with image, price, link
  2. ntfy.sh          — instant push to phone, zero account required
       Install: iOS App Store / Google Play → search "ntfy"
       Setup:   pick any topic name (e.g. "card-sniper-abc123"), subscribe in app
"""

import logging
from datetime import datetime
from typing import Optional
import requests

log = logging.getLogger(__name__)

_EMBED_COLOR = 0xFFD700   # gold


# ── ntfy.sh ───────────────────────────────────────────────────────────────────

def send_ntfy_alert(
    topic: str,
    player_name: str,
    listing: dict,
    max_price: float,
) -> bool:
    """
    Push a notification via ntfy.sh.

    topic is either:
      - a plain topic name  → posts to https://ntfy.sh/<topic>
      - a full URL          → posts directly (for self-hosted ntfy)
    """
    price = listing["price"]
    title = listing["title"]
    url = listing.get("url", "")

    ntfy_url = topic if topic.startswith("http") else f"https://ntfy.sh/{topic}"

    headers = {
        "Title": f"Card Sniper: {player_name} ${price:.2f}",
        "Priority": "high",
        "Tags": "credit_card,rotating_light",
        "Click": url or "",
    }

    body = f"${price:.2f} (under ${max_price:.2f} threshold)\n{title[:200]}"

    try:
        resp = requests.post(ntfy_url, data=body.encode("utf-8"), headers=headers, timeout=10)
        resp.raise_for_status()
        log.info("ntfy alert sent for %s ($%.2f)", player_name, price)
        return True
    except requests.RequestException as e:
        log.error("ntfy push failed: %s", e)
        return False


def send_ntfy_startup(topic: str, player_names: list[str]) -> None:
    ntfy_url = topic if topic.startswith("http") else f"https://ntfy.sh/{topic}"
    body = f"Watching {len(player_names)} players: {', '.join(player_names)}"
    try:
        requests.post(
            ntfy_url,
            data=body.encode("utf-8"),
            headers={"Title": "Card Sniper Started", "Tags": "white_check_mark"},
            timeout=10,
        )
    except requests.RequestException as e:
        log.warning("ntfy startup message failed: %s", e)


# ── Discord webhook ───────────────────────────────────────────────────────────

def send_alert(
    webhook_url: str,
    player_name: str,
    listing: dict,
    max_price: float,
    note: str = "",
) -> bool:
    """Post a Discord embed alert for a potential underpriced variation card."""
    price = listing["price"]
    title = listing["title"]
    url = listing.get("url", "")
    image_url = listing.get("image_url")
    listed_at: Optional[datetime] = listing.get("listed_at")
    condition = listing.get("condition", "Unknown")

    savings_pct = ((max_price - price) / max_price) * 100

    description_lines = [
        f"**${price:.2f}** — {savings_pct:.0f}% below your ${max_price:.2f} threshold",
        f"Condition: {condition}",
    ]
    if listed_at:
        description_lines.append(f"Listed: <t:{int(listed_at.timestamp())}:R>")

    embed = {
        "title": f"🎴  {player_name} — Possible Variation Card",
        "description": "\n".join(description_lines),
        "color": _EMBED_COLOR,
        "fields": [
            {"name": "Listing Title", "value": title[:256], "inline": False},
            *(
                [{"name": "What to check", "value": note[:1024], "inline": False}]
                if note else []
            ),
        ],
        "footer": {"text": "Card Sniper · Check image before buying · Variations are often mislabeled"},
    }

    if url:
        embed["url"] = url
    if image_url:
        embed["image"] = {"url": image_url}

    payload = {"username": "Card Sniper", "embeds": [embed]}

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        log.info("Discord alert sent for %s ($%.2f)", player_name, price)
        return True
    except requests.RequestException as e:
        log.error("Discord webhook failed: %s", e)
        return False


def send_startup_message(webhook_url: str, player_names: list[str]) -> None:
    player_list = "\n".join(f"• {n}" for n in player_names)
    payload = {
        "username": "Card Sniper",
        "embeds": [{
            "title": "Card Sniper Started",
            "description": (
                f"Watching **{len(player_names)}** players for 2025 Topps Chrome NFL:\n\n"
                f"{player_list}"
            ),
            "color": 0x5865F2,
            "footer": {"text": "Ctrl+C to stop"},
        }],
    }
    try:
        requests.post(webhook_url, json=payload, timeout=10)
    except requests.RequestException as e:
        log.warning("Could not send startup message: %s", e)
