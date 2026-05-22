import re


def extract_float_from_string(text: str) -> float:
    """Parse the first numeric price from arbitrary text (symbols stripped)."""
    return parse_currency_amount(text)


def parse_currency_amount(text: str) -> float:
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
