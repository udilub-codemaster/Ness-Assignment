import os
import config
from playwright.sync_api import Page
from pages.inventory_page import InventoryPage
from pages.cart_page import CartPage  # ייבוא העמוד החדש

def test_search_and_filter_prices(page: Page):
    inventory_page = InventoryPage(page)
    cart_page = CartPage(page)  # יצירת מופע של עמוד העגלה
    
    inventory_page.navigate_to_ebay()
    
    target_price = config.MAX_PRICE
    limit_count = config.ITEMS_LIMIT
    
    print(f"\n[Test] Starting search for '{config.SEARCH_QUERY}' under ${target_price}...")
    product_urls = inventory_page.search_items_by_name_under_price(
        query=config.SEARCH_QUERY,
        max_price=target_price,
        limit=limit_count,
        pool_size=limit_count * 3,
    )

    assert isinstance(product_urls, list), "Expected product_urls to be a list"
    assert len(product_urls) > 0, "Expected at least one product URL matching the price filter"
    assert len(product_urls) >= limit_count, (
        f"Expected at least {limit_count} candidate URLs in pool, got {len(product_urls)}"
    )

    # הוספת המוצרים לסל
    results = inventory_page.add_items_to_cart(
        product_urls=product_urls,
        max_price=target_price,
        target_count=limit_count,
    )

    assert len(results) == limit_count, (
        f"Expected {limit_count} products added to cart, got {len(results)}"
    )

    # assertCartTotalNotExceeds: read subtotal from cart page; assert in test only
    items_count = len(results)
    print(
        f"\n[Test] Step 4: Validating cart subtotal "
        f"(budget ${target_price} × {items_count} items)..."
    )

    cart_page.navigate_to_cart()
    actual_cart_total = cart_page.get_cart_total()
    max_allowed_budget = target_price * items_count

    print(
        f"[Test] Actual cart subtotal: ${actual_cart_total} | "
        f"Max allowed: ${max_allowed_budget} (${target_price} × {items_count})"
    )

    os.makedirs("logs/screenshots", exist_ok=True)
    cart_page.page.screenshot(path="logs/screenshots/final_cart_page.png")
    print("[Log] Saved final cart screenshot at logs/screenshots/final_cart_page.png")

    assert actual_cart_total <= max_allowed_budget, (
        f"Cart total (${actual_cart_total}) exceeds budget (${max_allowed_budget})"
    )    
    print("[Test] Success! Cart total validation passed flawlessly.")