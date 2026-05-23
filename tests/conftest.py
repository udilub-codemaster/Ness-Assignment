import os
import pytest
from playwright.sync_api import Page
from pages.cart_page import CartPage
from pages.inventory_page import InventoryPage


@pytest.fixture
def inventory_page(page: Page) -> InventoryPage:
    inventory = InventoryPage(page)
    inventory.navigate_to_ebay()
    return inventory


@pytest.fixture
def cart_page(page: Page) -> CartPage:
    return CartPage(page)


def pytest_collection_modifyitems(config, items):
    if os.getenv("GITHUB_ACTIONS") == "true":
        skip_captcha = pytest.mark.skip(
            reason="Skipping UI tests in CI environment to avoid Captcha"
        )
        for item in items:
            if "test_e2e" in item.nodeid or "search" in item.nodeid:
                item.add_marker(skip_captcha)