"""
eBay Finding API client.

Uses the public Finding API (no OAuth needed, just an App ID).
Endpoint: https://svcs.ebay.com/services/search/FindingService/v1

Docs: https://developer.ebay.com/api-docs/user-guides/static/finding-user-guide-landing.html
"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional
import requests

log = logging.getLogger(__name__)

_FINDING_URL = "https://svcs.ebay.com/services/search/FindingService/v1"
_NS = "http://www.ebay.com/marketplace/search/v1/services"


def _tag(name: str) -> str:
    return f"{{{_NS}}}{name}"


class EbayFindingClient:
    def __init__(self, app_id: str, timeout: int = 15):
        self.app_id = app_id
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "X-EBAY-SOA-SECURITY-APPNAME": app_id,
            "X-EBAY-SOA-OPERATION-NAME": "findItemsByKeywords",
            "X-EBAY-SOA-SERVICE-VERSION": "1.13.0",
            "X-EBAY-SOA-RESPONSE-DATA-FORMAT": "XML",
        })

    def find_new_listings(
        self,
        keywords: str,
        max_price: float,
        buy_it_now_only: bool = True,
        max_results: int = 20,
    ) -> list[dict]:
        """
        Search for recent BIN listings matching keywords under max_price.
        Returns list of listing dicts with keys:
          item_id, title, price, currency, url, condition, image_url, listed_at
        """
        params = {
            "keywords": keywords,
            "sortOrder": "StartTimeNewest",
            "paginationInput.entriesPerPage": str(max_results),
            "paginationInput.pageNumber": "1",
            # Filter: US only (site 0), category 213 = Sports Trading Cards
            "categoryId": "213",
            # Only US listings
            "itemFilter(0).name": "HideDuplicateItems",
            "itemFilter(0).value": "true",
            "itemFilter(1).name": "MaxPrice",
            "itemFilter(1).value": str(max_price),
            "itemFilter(1).paramName": "Currency",
            "itemFilter(1).paramValue": "USD",
            "itemFilter(2).name": "LocatedIn",
            "itemFilter(2).value": "US",
        }

        if buy_it_now_only:
            params["itemFilter(3).name"] = "ListingType"
            params["itemFilter(3).value"] = "FixedPrice"

        # Also request output selectors for image + condition
        params["outputSelector(0)"] = "PictureURLSuperSize"
        params["outputSelector(1)"] = "SellerInfo"

        try:
            resp = self._session.get(
                _FINDING_URL,
                params=params,
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            log.error("eBay API request failed: %s", e)
            return []

        return self._parse_xml(resp.text)

    def _parse_xml(self, xml_text: str) -> list[dict]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            log.error("Failed to parse eBay XML: %s", e)
            return []

        ack = root.findtext(_tag("ack"))
        if ack not in ("Success", "Warning"):
            error_msg = root.findtext(f".//{_tag('errorMessage')}/{_tag('error')}/{_tag('message')}")
            log.error("eBay API error (ack=%s): %s", ack, error_msg)
            return []

        items = []
        for item in root.findall(f".//{_tag('item')}"):
            try:
                item_id = item.findtext(_tag("itemId"))
                title = item.findtext(_tag("title"))

                # Price
                price_node = item.find(f".//{_tag('currentPrice')}")
                if price_node is None:
                    # BIN fallback
                    price_node = item.find(f".//{_tag('buyItNowPrice')}")
                price = float(price_node.text) if price_node is not None else None
                currency = price_node.get("currencyId", "USD") if price_node is not None else "USD"

                # URL
                url = item.findtext(_tag("viewItemURL"))

                # Condition
                condition = item.findtext(f".//{_tag('conditionDisplayName')}")

                # Image
                image_url = (
                    item.findtext(f".//{_tag('superSize')}")
                    or item.findtext(f".//{_tag('galleryURL')}")
                )

                # Listing time
                listed_at_str = item.findtext(f".//{_tag('startTime')}")
                listed_at: Optional[datetime] = None
                if listed_at_str:
                    try:
                        listed_at = datetime.fromisoformat(
                            listed_at_str.replace("Z", "+00:00")
                        )
                    except ValueError:
                        pass

                if item_id and title and price is not None:
                    items.append({
                        "item_id": item_id,
                        "title": title,
                        "price": price,
                        "currency": currency,
                        "url": url,
                        "condition": condition,
                        "image_url": image_url,
                        "listed_at": listed_at,
                    })
            except Exception as e:
                log.warning("Skipping malformed eBay item: %s", e)
                continue

        return items
