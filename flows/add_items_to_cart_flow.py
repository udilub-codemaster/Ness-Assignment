from typing import Optional

import config
from playwright.sync_api import BrowserContext

from pages.base_page import BasePage
from pages.product_page import ProductPage
from utils.screenshot_helpers import save_page_screenshot


class AddItemsToCartFlow:
    """Opens product URLs in new tabs and adds in-budget items to the cart."""

    def __init__(
        self,
        context: BrowserContext,
        max_price: float,
        target_count: Optional[int] = None,
    ):
        self._context = context
        self._max_price = max_price
        self._target = target_count or config.ITEMS_LIMIT

    def run(self, product_urls: list[str]) -> list[dict]:
        verified_products: list[dict] = []
        url_queue = list(product_urls)
        attempt = 0

        while url_queue and len(verified_products) < self._target:
            attempt += 1
            url = url_queue.pop(0)
            BasePage._log(
                f"\n[AddItemsToCartFlow] Attempt {attempt} "
                f"({len(verified_products)}/{self._target} added): {url}"
            )

            new_tab = self._context.new_page()
            product_page = ProductPage(new_tab)

            try:
                new_tab.goto(url, wait_until="load", timeout=config.LONG_TIMEOUT)
                title = product_page.get_product_title()
                price = product_page.get_product_price()
                BasePage._log(f"[AddItemsToCartFlow] Title: {title} | Price: {price}$")
                if price > self._max_price:
                    BasePage._log(
                        f"[Warning] Skipped — price {price}$ exceeds limit {self._max_price}$"
                    )
                    continue
                if not product_page.add_to_cart():
                    pending = product_page.variants.get_pending_variants()
                    reason = "pending_variants" if pending else "add_to_cart_failed"
                    BasePage._log(f"[Warning] Skipped — {reason}")
                    continue
                screenshot_path = (
                    f"logs/screenshots/item_{len(verified_products) + 1}_added.png"
                )
                save_page_screenshot(new_tab, screenshot_path)
                verified_products.append({"title": title, "price": price, "url": url})
            except Exception as exc:
                BasePage._log(f"[Warning] Skipped — error: {exc}")
            finally:
                new_tab.close()

        return verified_products
