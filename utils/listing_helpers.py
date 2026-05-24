import re
from urllib.parse import parse_qs, urlencode, urlparse


def is_cartable_listing_text(text: str) -> bool:
    """Skip auction-only cards when BIN is not also offered."""
    lower = text.lower()
    has_buy_it_now = "buy it now" in lower
    has_auction = bool(re.search(r"\d+\s*bid", lower)) or "place bid" in lower
    if has_auction and not has_buy_it_now:
        return False
    return True


def format_max_price_for_filter(max_price: float) -> str:
    if max_price == int(max_price):
        return str(int(max_price))
    return str(max_price)


def filtered_search_params(query: str, max_price: float) -> dict[str, str]:
    """eBay SRP params: keyword, Buy It Now only, max price ceiling."""
    return {
        "_nkw": query,
        "LH_BIN": "1",
        "_udhi": format_max_price_for_filter(max_price),
    }


def build_filtered_search_url(
    query: str, max_price: float, base_url: str = "https://www.ebay.com"
) -> str:
    base = base_url.rstrip("/")
    return f"{base}/sch/i.html?{urlencode(filtered_search_params(query, max_price))}"


def url_has_filtered_search_params(url: str, max_price: float) -> bool:
    qs = parse_qs(urlparse(url).query)
    expected_udhi = format_max_price_for_filter(max_price)
    bin_active = qs.get("LH_BIN", [""])[0] == "1"
    udhi_active = qs.get("_udhi", [""])[0] == expected_udhi
    return bin_active and udhi_active
