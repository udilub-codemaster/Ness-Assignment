import pytest
import config
from flows.cart_verification_flow import assert_cart_total_not_exceeds
from pages.cart_page import CartPage
from pages.inventory_page import InventoryPage


@pytest.mark.e2e
@pytest.mark.external
def test_search_add_to_cart_and_assert_budget(inventory_page: InventoryPage, cart_page: CartPage):
    product_urls = inventory_page.search_items_by_name_under_price(
        config.SEARCH_QUERY,
        config.MAX_PRICE,
        config.ITEMS_LIMIT,
    )

    inventory_page.add_items_to_cart(product_urls, config.MAX_PRICE)
    assert_cart_total_not_exceeds(cart_page, config.MAX_PRICE, len(product_urls))
