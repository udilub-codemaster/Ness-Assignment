import re


def normalize_option_text(text: str) -> str:
    return re.sub(r"selected$", "", text.strip(), flags=re.IGNORECASE).strip()


def label_needs_selection(button_text: str, value: str = "") -> bool:
    text = button_text.strip()
    if (value or "").strip().lower() == "select":
        return True
    normalized = re.sub(r"\s+", " ", text)
    if re.search(r":\s*select\s*$", normalized, re.IGNORECASE):
        return True
    if normalized.lower() in ("select", "- select -", "please select"):
        return True
    if re.match(r"^[A-Za-z /'()]+:\s*$", normalized):
        return True
    return False


def is_valid_variant_option(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return False
    lower = cleaned.lower()
    if lower == "select" or lower.startswith("select"):
        return False
    if "out of stock" in lower:
        return False
    if lower in ("positive", "neutral", "negative") or "rating" in lower:
        return False
    return True


def variant_sort_key(label: str) -> int:
    lower = label.lower()
    if "color" in lower or "colour" in lower:
        return 0
    if "size" in lower:
        return 1
    if "width" in lower:
        return 2
    if "style" in lower or "heel" in lower:
        return 3
    return 4
