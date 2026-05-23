from pages.base_page import BasePage
from pages.cart_page import CartPage
from utils.screenshot_helpers import save_page_screenshot


def assert_cart_total_not_exceeds(
    cart_page: CartPage,
    budget_per_item: float,
    items_count: int,
) -> None:
    cart_page.navigate_to_cart()
    actual_total = cart_page.get_cart_total()
    screenshot_path = "logs/screenshots/final_cart_page.png"
    save_page_screenshot(cart_page.page, screenshot_path)
    BasePage._log(f"[CartVerificationFlow] Saved cart screenshot at {screenshot_path}")
    max_allowed = budget_per_item * items_count
    assert actual_total <= max_allowed, (
        f"Cart total (${actual_total}) exceeds budget (${max_allowed})"
    )
