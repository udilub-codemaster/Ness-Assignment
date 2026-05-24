import os
from dotenv import load_dotenv
import json

load_dotenv()

SHORT_TIMEOUT = 5000
DEFAULT_TIMEOUT = 10000
LONG_TIMEOUT = 20000
VARIANT_SKU_WAIT_MS = 1500
VARIANT_POLL_INTERVAL_MS = 100
VARIANT_POLL_ATTEMPTS = 15
VARIANT_AREA_WAIT_MS = (
    VARIANT_POLL_ATTEMPTS * VARIANT_POLL_INTERVAL_MS * 2 + VARIANT_SKU_WAIT_MS
)
MAX_PAGINATION_PAGES = 10
PAGE_LOADED_INDICATOR = "load"
DEFAULT_SEARCH_QUERY = "shoes"
DEFAULT_MAX_PRICE = 50.0
DEFAULT_ITEMS_LIMIT = 5


BASE_URL = os.getenv("EBAY_URL", "https://www.ebay.com")
SIGN_IN_URL = os.getenv("EBAY_SIGN_IN_URL", "https://signin.ebay.com/signin/")
EBAY_USERNAME = os.getenv("EBAY_USERNAME", "default_user")
EBAY_PASSWORD = os.getenv("EBAY_PASSWORD", "default_password")
EBAY_USER = os.getenv("EBAY_USERNAME")
EBAY_PASS = os.getenv("EBAY_PASSWORD")
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_FILE_PATH = os.path.join(PROJECT_ROOT, "data", "test_data.json")

with open(DATA_FILE_PATH, "r", encoding="utf-8") as f:
    _data = json.load(f)

SEARCH_QUERY = _data.get("search_query", DEFAULT_SEARCH_QUERY)
MAX_PRICE = float(_data.get("max_price", DEFAULT_MAX_PRICE))
ITEMS_LIMIT = int(_data.get("items_limit", DEFAULT_ITEMS_LIMIT))