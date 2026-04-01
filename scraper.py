"""
Target.com price scraper core logic.
"""

import time
from datetime import datetime, timezone

import requests

API_BASE   = "https://redsky.target.com/redsky_aggregations/v1/web/pdp_client_v1"
API_KEY    = "9f36aeafbe60771e321a7cc95a78140772ab3e96"
STORE_ID   = "3991"
VISITOR_ID = "018F2D7E4CA102019ACED07796CE1060"
DELAY_SEC  = 0.8

CSV_FIELDS = [
    "tcin",
    "title",
    "brand",
    "url",
    "current_price",
    "current_price_type",
    "regular_price",
    "save_dollar",
    "save_percent",
    "is_on_sale",
    "color",
    "size",
    "status",
    "fetched_at",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":  "application/json",
    "Origin":  "https://www.target.com",
}

SIZES = {"S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL", "XXL", "XXXL"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_color_size(title: str) -> tuple[str, str]:
    tokens = title.strip().split()
    if len(tokens) < 2:
        return "", ""
    if tokens[-2].upper() in SIZES:
        return tokens[-1], tokens[-2]
    if len(tokens) >= 3 and tokens[-3].upper() in SIZES:
        return " ".join(tokens[-2:]), tokens[-3]
    return "", ""


def error_row(tcin: str, message: str) -> dict:
    return {
        "tcin": tcin,
        "title": "",
        "brand": "",
        "url": "",
        "current_price": "",
        "current_price_type": "",
        "regular_price": "",
        "save_dollar": "",
        "save_percent": "",
        "is_on_sale": "",
        "color": "",
        "size": "",
        "status": f"ERROR: {message}",
        "fetched_at": now_iso(),
    }


def fetch_tcin(session: requests.Session, tcin: str) -> dict:
    params = {
        "key":              API_KEY,
        "tcin":             tcin,
        "visitor_id":       VISITOR_ID,
        "channel":          "WEB",
        "page":             f"/p/A-{tcin}",
        "pricing_store_id": STORE_ID,
    }
    headers = {**HEADERS, "Referer": f"https://www.target.com/p/-/A-{tcin}"}
    resp = session.get(API_BASE, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


def parse_product(tcin: str, data: dict) -> list[dict]:
    product = (data.get("data") or {}).get("product")
    if not product:
        return [error_row(tcin, "No product in response")]

    item    = product.get("item") or {}
    desc    = item.get("product_description") or {}
    brand   = (item.get("primary_brand") or {}).get("name", "")
    buy_url = (
        (item.get("enrichment") or {}).get("buy_url")
        or f"https://www.target.com/p/-/A-{tcin}"
    )

    children = product.get("children")

    if children:
        rows = []
        for child in children:
            c_item  = child.get("item") or {}
            c_desc  = c_item.get("product_description") or {}
            c_price = child.get("price") or {}
            c_url   = (
                (c_item.get("enrichment") or {}).get("buy_url")
                or buy_url
            )
            title = c_desc.get("title") or desc.get("title", "")
            color, size = extract_color_size(title)
            rows.append({
                "tcin":               child.get("tcin", tcin),
                "title":              title,
                "brand":              brand,
                "url":                c_url,
                "current_price":      c_price.get("current_retail", ""),
                "current_price_type": c_price.get("formatted_current_price_type", ""),
                "regular_price":      c_price.get("reg_retail", ""),
                "save_dollar":        c_price.get("save_dollar", ""),
                "save_percent":       c_price.get("save_percent", ""),
                "is_on_sale":         "TRUE" if c_price.get("formatted_current_price_type") == "sale" else "FALSE",
                "color":              color,
                "size":               size,
                "status":             "OK",
                "fetched_at":         now_iso(),
            })
        return rows

    price = product.get("price") or {}
    title = desc.get("title", "")
    color, size = extract_color_size(title)
    return [{
        "tcin":               tcin,
        "title":              title,
        "brand":              brand,
        "url":                buy_url,
        "current_price":      price.get("current_retail_min") or price.get("current_retail", ""),
        "current_price_type": price.get("formatted_current_price_type", ""),
        "regular_price":      price.get("reg_retail_max") or price.get("reg_retail", ""),
        "save_dollar":        price.get("save_dollar", ""),
        "save_percent":       price.get("save_percent", ""),
        "is_on_sale":         "TRUE" if price.get("formatted_current_price_type") == "sale" else "FALSE",
        "color":              color,
        "size":               size,
        "status":             "OK",
        "fetched_at":         now_iso(),
    }]


def run_scraper(tcins: list[str], progress_cb=None) -> list[dict]:
    """
    Scrape a list of TCINs and return rows.
    progress_cb(i, total, tcin, rows_or_error) is called after each fetch.
    """
    all_rows = []
    with requests.Session() as session:
        for i, tcin in enumerate(tcins, 1):
            try:
                data = fetch_tcin(session, tcin)
                rows = parse_product(tcin, data)
                all_rows.extend(rows)
                if progress_cb:
                    progress_cb(i, len(tcins), tcin, rows, None)
            except requests.HTTPError as e:
                msg = f"HTTP {e.response.status_code}"
                all_rows.append(error_row(tcin, msg))
                if progress_cb:
                    progress_cb(i, len(tcins), tcin, None, msg)
            except Exception as e:
                all_rows.append(error_row(tcin, str(e)))
                if progress_cb:
                    progress_cb(i, len(tcins), tcin, None, str(e))

            if i < len(tcins):
                time.sleep(DELAY_SEC)

    return all_rows
