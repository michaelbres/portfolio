"""
eBay Finding API — completed/sold items only.

Uses findCompletedItems with SoldItemsOnly=true.
Same App ID as the sniper tool (EBAY_APP_ID env var).
"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, date
from typing import Optional
import requests

log = logging.getLogger(__name__)

_URL = "https://svcs.ebay.com/services/search/FindingService/v1"
_NS  = "http://www.ebay.com/marketplace/search/v1/services"

SPORTS_CATEGORIES = {
    "football":   "214",   # Football Trading Cards
    "baseball":   "213",   # Baseball Trading Cards
    "basketball": "216",   # Basketball Trading Cards
    "all":        "212",   # Non-Sport Trading Cards parent — use Sports parent
}
# Actually the correct parent for all sports cards
_SPORTS_CARDS_CATEGORY = "212"  # Trading Cards (parent)
_CATEGORY_IDS = {
    "baseball":   "213",
    "football":   "214",
    "basketball": "216",
}


def _tag(name: str) -> str:
    return f"{{{_NS}}}{name}"


def fetch_completed_sales(
    app_id: str,
    keywords: str,
    sport: str = "all",
    days: int = 90,
    max_results: int = 100,
) -> list[dict]:
    """
    Return sold eBay listings matching keywords from the last `days` days.

    Each item dict has:
        title, price, currency, url, condition, listed_at (datetime), sold_at (datetime)
    """
    if not app_id:
        raise ValueError("EBAY_APP_ID not configured")

    category = _CATEGORY_IDS.get(sport, "")

    headers = {
        "X-EBAY-SOA-SECURITY-APPNAME":    app_id,
        "X-EBAY-SOA-OPERATION-NAME":      "findCompletedItems",
        "X-EBAY-SOA-SERVICE-VERSION":     "1.13.0",
        "X-EBAY-SOA-RESPONSE-DATA-FORMAT":"XML",
    }

    params: dict[str, str] = {
        "keywords":                        keywords,
        "sortOrder":                       "EndTimeSoonest",
        "paginationInput.entriesPerPage":  str(min(max_results, 100)),
        "paginationInput.pageNumber":      "1",
        "itemFilter(0).name":              "SoldItemsOnly",
        "itemFilter(0).value":             "true",
        "itemFilter(1).name":              "LocatedIn",
        "itemFilter(1).value":             "US",
        "outputSelector(0)":               "SellerInfo",
    }
    if category:
        params["categoryId"] = category

    try:
        resp = requests.get(_URL, headers=headers, params=params, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error("eBay API request failed: %s", e)
        return []

    items = _parse(resp.text, days)
    log.info("eBay completed items for %r: %d results", keywords, len(items))
    return items


def _parse(xml_text: str, days: int) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        log.error("eBay XML parse error: %s", e)
        return []

    ack = root.findtext(_tag("ack"))
    if ack not in ("Success", "Warning"):
        err = root.findtext(f".//{_tag('message')}")
        log.error("eBay error ack=%s: %s", ack, err)
        return []

    cutoff = datetime.utcnow().timestamp() - days * 86400
    items = []

    for item in root.findall(f".//{_tag('item')}"):
        try:
            title = item.findtext(_tag("title")) or ""
            url   = item.findtext(_tag("viewItemURL")) or ""

            # Price — sellingStatus.currentPrice for completed
            price_node = item.find(f".//{_tag('currentPrice')}")
            if price_node is None:
                continue
            price = float(price_node.text)

            # End time (= sale time for completed)
            end_str = item.findtext(f".//{_tag('endTime')}")
            sold_at: Optional[datetime] = None
            if end_str:
                sold_at = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                if sold_at.timestamp() < cutoff:
                    continue   # outside the requested window

            condition = item.findtext(f".//{_tag('conditionDisplayName')}") or ""

            items.append({
                "title":     title,
                "price":     price,
                "currency":  price_node.get("currencyId", "USD"),
                "url":       url,
                "condition": condition,
                "sold_at":   sold_at,
            })
        except Exception as e:
            log.debug("Skipping malformed item: %s", e)

    return items
