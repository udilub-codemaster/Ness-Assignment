import re
from typing import Optional

CURRENCY_PATTERN = re.compile(
    r"(?:US\s*)?\$\s*([\d,]+\.\d{2})",
    re.IGNORECASE,
)


def parse_currency_amount(text: str) -> float:
    """Parse the first numeric price from arbitrary text (symbols stripped)."""
    if not text:
        raise ValueError("Cannot extract price from an empty string")
    cleaned_text = re.sub(r"[^\d.]", "", text)
    try:
        return float(cleaned_text)
    except ValueError as exc:
        raise ValueError(
            f"Could not convert cleaned text '{cleaned_text}' "
            f"(derived from '{text}') to float"
        ) from exc


def parse_price_from_listing_card(price_text: str) -> float:
    """Extract price from SRP card text; handles ranges like '$10 to $20'."""
    first_segment = price_text.split("to")[0]
    return parse_currency_amount(first_segment)


def parse_subtotal_from_summary(text: str) -> Optional[float]:
    """Find cart subtotal from order-summary block or page body text."""
    if not text:
        return None

    inline = re.search(
        r"Subtotal[^\d]*?(?:US\s*)?\$\s*([\d,]+\.\d{2})",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if inline:
        return float(inline.group(1).replace(",", ""))

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if not re.match(r"^Subtotal\b", line, re.IGNORECASE):
            continue
        for next_line in lines[index + 1 : index + 4]:
            match = CURRENCY_PATTERN.search(next_line)
            if match:
                return float(match.group(1).replace(",", ""))
            bare = re.fullmatch(r"([\d,]+\.\d{2})", next_line)
            if bare:
                return float(bare.group(1).replace(",", ""))
    return None
