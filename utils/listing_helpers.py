import re


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
