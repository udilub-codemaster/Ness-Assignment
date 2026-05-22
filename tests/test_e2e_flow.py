from playwright.sync_api import Page
from pages.inventory_page import InventoryPage
import config
import pytest

def test_search_and_filter_prices(page: Page):

    inventory_page = InventoryPage(page)
    inventory_page.navigate_to_ebay()
    target_price = 50.0
    limit_count = 5
    print(f"\n[Test] Starting search for 'shoes' under ${target_price}...")
    product_urls = inventory_page.search_items_by_name_under_price(
        query=config.SEARCH_QUERY,
        max_price=config.MAX_PRICE,
        limit=config.ITEMS_LIMIT,
    )

    assert isinstance(product_urls, list), "Expected product_urls to be a list"
    assert len(product_urls) > 0, "Expected at least one product URL matching the price filter"
    assert len(product_urls) <= limit_count, f"Expected up to {limit_count} URLs, but got {len(product_urls)}"
