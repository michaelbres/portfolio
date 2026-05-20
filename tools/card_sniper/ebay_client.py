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

    def find_items(
        self,
        keywords: str,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None,
        buy_it_now_only: bool = True,
        category_id: Optional[str] = None,
        max_results: int = 100,
        page: int = 1,
    ) -> list[dict]:
        """
        Flexible item search. max_price=None means no upper limit.
        Returns up to max_results (capped at 100 per eBay's limit per page).
        """
        fi = 0  # itemFilter index

        params: dict[str, str] = {
            "keywords": keywords,
            "sortOrder": "StartTimeNewest",
            "paginationInput.entriesPerPage": str(min(max_results, 100)),
            "paginationInput.pageNumber": str(page),
            f"itemFilter({fi}).name": "HideDuplicateItems",
            f"itemFilter({fi}).value": "true",
        }
        fi += 1

        if category_id:
            params["categoryId"] = category_id

        if max_price is not None:
            params[f"itemFilter({fi}).name"] = "MaxPrice"
            params[f"itemFilter({fi}).value"] = str(max_price)
            params[f"itemFilter({fi}).paramName"] = "Currency"
            params[f"itemFilter({fi}).paramValue"] = "USD"
            fi += 1

        if min_price is not None:
            params[f"itemFilter({fi}).name"] = "MinPrice"
            params[f"itemFilter({fi}).value"] = str(min_price)
            params[f"itemFilter({fi}).paramName"] = "Currency"
            params[f"itemFilter({fi}).paramValue"] = "USD"
            fi += 1

        params[f"itemFilter({fi}).name"] = "LocatedIn"
        params[f"itemFilter({fi}).value"] = "US"
        fi += 1

        if buy_it_now_only:
            params[f"itemFilter({fi}).name"] = "ListingType"
            params[f"itemFilter({fi}).value"] = "FixedPrice"
            fi += 1

        params["outputSelector(0)"] = "PictureURLSuperSize"
        params["outputSelector(1)"] = "SellerInfo"

        try:
            resp = self._session.get(_FINDING_URL, params=params, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as e:
            log.error("eBay API request failed: %s", e)
            return []

        return self._parse_xml(resp.text)

    def find_items_all_pages(
        self,
        keywords: str,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None,
        buy_it_now_only: bool = True,
        category_id: Optional[str] = None,
        max_pages: int = 5,
    ) -> list[dict]:
        """
        Fetch up to max_pages × 100 results, paginating automatically.
        Use for searches with no hard result cap (e.g. Pokemon lots).
        """
        all_items: list[dict] = []
        for page in range(1, max_pages + 1):
            page_items = self.find_items(
                keywords=keywords,
                max_price=max_price,
                min_price=min_price,
                buy_it_now_only=buy_it_now_only,
                category_id=category_id,
                max_results=100,
                page=page,
            )
            all_items.extend(page_items)
            if len(page_items) < 100:
                break  # last page
        return all_items

    # ── Backward-compat wrapper used by sniper.py ─────────────────────────────

    def find_new_listings(
        self,
        keywords: str,
        max_price: float,
        buy_it_now_only: bool = True,
        max_results: int = 20,
    ) -> list[dict]:
        return self.find_items(
            keywords=keywords,
            max_price=max_price,
            buy_it_now_only=buy_it_now_only,
            category_id="213",
            max_results=max_results,
        )

    # ── XML parsing ───────────────────────────────────────────────────────────

    def _parse_xml(self, xml_text: str) -> list[dict]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            log.error("Failed to parse eBay XML: %s", e)
            return []

        ack = root.findtext(_tag("ack"))
        if ack not in ("Success", "Warning"):
            error_msg = root.findtext(
                f".//{_tag('errorMessage')}/{_tag('error')}/{_tag('message')}"
            )
            log.error("eBay API error (ack=%s): %s", ack, error_msg)
            return []

        items = []
        for item in root.findall(f".//{_tag('item')}"):
            try:
                item_id = item.findtext(_tag("itemId"))
                title = item.findtext(_tag("title"))

                price_node = item.find(f".//{_tag('currentPrice')}")
                if price_node is None:
                    price_node = item.find(f".//{_tag('buyItNowPrice')}")
                price = float(price_node.text) if price_node is not None else None
                currency = price_node.get("currencyId", "USD") if price_node is not None else "USD"

                url = item.findtext(_tag("viewItemURL"))
                condition = item.findtext(f".//{_tag('conditionDisplayName')}")
                image_url = (
                    item.findtext(f".//{_tag('superSize')}")
                    or item.findtext(f".//{_tag('galleryURL')}")
                )

                listed_at_str = item.findtext(f".//{_tag('startTime')}")
                listed_at: Optional[datetime] = None
                if listed_at_str:
                    try:
                        listed_at = datetime.fromisoformat(listed_at_str.replace("Z", "+00:00"))
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
