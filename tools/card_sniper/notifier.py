"""
Discord webhook notifier for card sniper alerts.

Sends a rich embed with:
  - Player name + listing title
  - Price (large, colored)
  - Direct link to eBay listing
  - Thumbnail image if available
  - Timestamp of listing
"""

import logging
from datetime import datetime
from typing import Optional
import requests

log = logging.getLogger(__name__)

# Embed color: gold (0xFFD700) — stands out in Discord
_EMBED_COLOR = 0xFFD700


def send_alert(
    webhook_url: str,
    player_name: str,
    listing: dict,
    max_price: float,
    note: str = "",
) -> bool:
    """
    Post a Discord embed alert for a potential underpriced variation card.

    listing dict keys: item_id, title, price, currency, url, condition, image_url, listed_at
    Returns True on success.
    """
    price = listing["price"]
    title = listing["title"]
    url = listing.get("url", "")
    image_url = listing.get("image_url")
    listed_at: Optional[datetime] = listing.get("listed_at")
    condition = listing.get("condition", "Unknown")

    # How much below threshold?
    savings = max_price - price
    savings_pct = (savings / max_price) * 100

    description_lines = [
        f"**${price:.2f}** — {savings_pct:.0f}% below your ${max_price:.2f} threshold",
        f"Condition: {condition}",
    ]
    if listed_at:
        description_lines.append(
            f"Listed: <t:{int(listed_at.timestamp())}:R>"
        )

    embed = {
        "title": f"🎴  {player_name} — Possible Variation Card",
        "description": "\n".join(description_lines),
        "color": _EMBED_COLOR,
        "fields": [
            {
                "name": "Listing Title",
                "value": title[:256],  # Discord field value limit
                "inline": False,
            },
            *(
                [{
                    "name": "What to check",
                    "value": note[:1024],
                    "inline": False,
                }]
                if note else []
            ),
        ],
        "footer": {
            "text": "Card Sniper · Check image before buying · Variations are often mislabeled"
        },
    }

    if url:
        embed["url"] = url

    if image_url:
        embed["image"] = {"url": image_url}

    payload = {
        "username": "Card Sniper",
        "embeds": [embed],
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        log.info("Discord alert sent for %s ($%.2f)", player_name, price)
        return True
    except requests.RequestException as e:
        log.error("Discord webhook failed: %s", e)
        return False


def send_startup_message(webhook_url: str, player_names: list[str]) -> None:
    """Send a brief 'sniper started' message so you know it's running."""
    player_list = "\n".join(f"• {n}" for n in player_names)
    payload = {
        "username": "Card Sniper",
        "embeds": [
            {
                "title": "Card Sniper Started",
                "description": (
                    f"Watching **{len(player_names)}** players for 2025 Topps Chrome NFL:\n\n"
                    f"{player_list}"
                ),
                "color": 0x5865F2,  # Discord blurple
                "footer": {"text": "Ctrl+C to stop"},
            }
        ],
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning("Could not send startup message: %s", e)
