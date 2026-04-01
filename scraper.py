"""
Target.com price scraper core logic.
"""

import csv
import os
import random
import time
from datetime import datetime, timezone

import requests

API_BASE        = "https://redsky.target.com/redsky_aggregations/v1/web/pdp_client_v1"
API_KEY         = "9f36aeafbe60771e321a7cc95a78140772ab3e96"
STORE_ID        = "3991"
VISITOR_ID      = "018F2D7E4CA102019ACED07796CE1060"
MAX_RETRIES     = 3     # max retries per TCIN on 403
# how long to wait before each retry attempt after a 403
RETRY_BACKOFF   = [30, 60, 120]

# Human-like delay tiers: (weight, min_sec, max_sec)
#   70 % → quick glance   1 – 3 s
#   20 % → reading        3 – 7 s
#   10 % → distracted     8 – 15 s
_DELAY_TIERS = [
    (0.70, 1.0,  3.0),
    (0.20, 3.0,  7.0),
    (0.10, 8.0, 15.0),
]

# Every BREAK_EVERY ± BREAK_JITTER requests, pause for BREAK_RANGE seconds
# to simulate a human stepping away briefly.
BREAK_EVERY  = 75
BREAK_JITTER = 25
BREAK_RANGE  = (20.0, 45.0)

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
        "key":                    API_KEY,
        "tcin":                   tcin,
        "is_bot":                 "false",
        "store_id":               STORE_ID,
        "pricing_store_id":       STORE_ID,
        "has_pricing_store_id":   "true",
        "has_financing_options":  "true",
        "include_obsolete":       "false",
        "visitor_id":             VISITOR_ID,
        "skip_personalized":      "true",
        "skip_variation_hierarchy": "true",
        "channel":                "WEB",
        "page":                   f"/p/A-{tcin}",
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


def _human_delay(request_index: int) -> float:
    """
    Return a randomised wait time that mimics human browsing cadence.

    Most pauses are short (quick click), some are medium (reading),
    a few are long (distracted).  Every ~75 requests an extra 'break'
    is injected so the session never looks like a metronomic bot.

    request_index is 1-based (the number of requests completed so far).
    """
    # Weighted tier selection
    roll = random.random()
    cumulative = 0.0
    lo, hi = 1.0, 3.0   # fallback to quick tier
    for weight, tier_lo, tier_hi in _DELAY_TIERS:
        cumulative += weight
        if roll < cumulative:
            lo, hi = tier_lo, tier_hi
            break
    delay = random.uniform(lo, hi)

    # Occasional longer break every BREAK_EVERY ± BREAK_JITTER requests
    next_break = BREAK_EVERY + random.randint(-BREAK_JITTER, BREAK_JITTER)
    if request_index % next_break == 0:
        delay += random.uniform(*BREAK_RANGE)

    return delay


def _new_session() -> requests.Session:
    return requests.Session()


def run_scraper(
    tcins: list[str],
    progress_cb=None,
    output_path: str | None = None,
    pause_event=None,
) -> list[dict]:
    """
    Scrape a list of TCINs and return rows.
    progress_cb(i, total, tcin, rows, error) is called after each TCIN is settled.

    If output_path is given, each row is written to that CSV file immediately
    after it is fetched so partial results survive an app restart or crash.
    The file is created fresh at the start of each run (overwrite).

    If pause_event (a threading.Event) is provided, the loop checks it before
    each TCIN and exits cleanly when set, allowing the caller to pause scraping
    mid-run without killing the thread.

    On HTTP 403 the scraper refreshes its session and retries up to MAX_RETRIES
    times, waiting RETRY_BACKOFF[attempt] seconds between each try.  All other
    requests use human-like randomised delays to avoid predictable cadence.
    """
    all_rows = []
    total = len(tcins)

    # Open the incremental output file once and keep it open for the whole run.
    out_fh = None
    out_writer = None
    if output_path:
        out_fh = open(output_path, "w", newline="", encoding="utf-8")
        out_writer = csv.DictWriter(out_fh, fieldnames=CSV_FIELDS)
        out_writer.writeheader()
        out_fh.flush()

    session = _new_session()
    try:
        for i, tcin in enumerate(tcins, 1):
            # Honour a pause request between TCINs (never mid-fetch).
            if pause_event is not None and pause_event.is_set():
                break

            rows = None
            last_error = None

            for attempt in range(MAX_RETRIES + 1):
                try:
                    data = fetch_tcin(session, tcin)
                    rows = parse_product(tcin, data)
                    break  # success — exit retry loop
                except requests.HTTPError as e:
                    status = e.response.status_code
                    if status == 403 and attempt < MAX_RETRIES:
                        wait = RETRY_BACKOFF[attempt]
                        if progress_cb:
                            progress_cb(
                                i, total, tcin, None,
                                f"HTTP 403 — waiting {wait}s before retry {attempt + 1}/{MAX_RETRIES}",
                            )
                        session.close()
                        session = _new_session()
                        time.sleep(wait)
                        continue
                    last_error = f"HTTP {status}"
                    break
                except Exception as e:
                    last_error = str(e)
                    break

            settled = rows if rows is not None else [error_row(tcin, last_error)]
            all_rows.extend(settled)

            # Flush to disk immediately so data survives a crash / sleep.
            if out_writer:
                out_writer.writerows(settled)
                out_fh.flush()
                os.fsync(out_fh.fileno())

            if progress_cb:
                if rows is not None:
                    progress_cb(i, total, tcin, rows, None)
                else:
                    progress_cb(i, total, tcin, None, last_error)

            if i < total:
                time.sleep(_human_delay(i))
    finally:
        session.close()
        if out_fh:
            out_fh.close()

    return all_rows
