import config
from typing import Optional

from playwright.sync_api import Locator, Page

from flows.add_items_to_cart_flow import AddItemsToCartFlow
from pages.base_page import BasePage
from utils.listing_helpers import format_max_price_for_filter, is_cartable_listing_text
from utils.price_parser import parse_price_from_listing_card


class InventoryPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self._search_box = "#gh-ac"
        self._search_button = "#gh-search-btn"
        self._product_container = "ul.srp-results .s-card.s-card--vertical"
        self._product_link = "a.s-card__link, a[href*='/itm/']"
        self._product_price = ".s-card__price, .s-item__price"
        self._next_page_button = "a.pagination__next"
        self._max_price_filter = (
            "input[aria-label*='Maximum Value'], input[placeholder='max']"
        )
        self._submit_price_button = "button[aria-label='Submit price range']"

    def navigate_to_ebay(self) -> None:
        self.navigate(config.BASE_URL)

    def search_for_query(self, query: str) -> None:
        search_input = self.page.locator(self._search_box)
        search_input.wait_for(state="visible", timeout=config.DEFAULT_TIMEOUT)
        search_input.fill(query)
        self.click_element(self._search_button)
        self.wait_for_page_loaded()
        self._log(f"[InventoryPage] Search executed for: {query}")

    def apply_price_ceiling_filter(self, max_price: float) -> None:
        max_price_input = self.page.locator(self._max_price_filter)
        submit_btn = self.page.locator(self._submit_price_button)
        try:
            max_price_input.wait_for(state="visible", timeout=config.SHORT_TIMEOUT)
            max_price_input.fill(format_max_price_for_filter(max_price))
            self._log(f"[InventoryPage] Filled max price: {max_price}")
            max_price_input.press("Enter")
            submit_btn.wait_for(state="visible", timeout=config.SHORT_TIMEOUT)
            if submit_btn.is_enabled():
                submit_btn.click(timeout=config.SHORT_TIMEOUT)
                self._log("[InventoryPage] Clicked Submit price range button.")
            self.wait_for_page_loaded()
            self._log("[InventoryPage] Applied max price filter via UI.")
        except Exception as exc:
            self._log(
                f"[Warning] Could not apply UI max price filter ({exc}); "
                "using code-level filtering only."
            )

    def apply_buy_it_now_filter(self) -> None:
        try:
            bin_link = self.page.locator("a[href*='LH_BIN=1']").first
            bin_link.wait_for(state="visible", timeout=config.SHORT_TIMEOUT)
            bin_link.click()
            self.wait_for_page_loaded()
            self._log("[InventoryPage] Applied Buy It Now filter via UI.")
            return
        except Exception:
            pass
        url = self.page.url
        if "LH_BIN=1" not in url:
            separator = "&" if "?" in url else "?"
            self.page.goto(f"{url}{separator}LH_BIN=1")
            self.wait_for_page_loaded()
            self._log("[InventoryPage] Applied Buy It Now filter via URL (LH_BIN=1).")

    def _parse_card_price(self, card: Locator) -> float:
        try:
            price_text = card.locator(self._product_price).first.inner_text()
            return parse_price_from_listing_card(price_text)
        except Exception:
            return float("inf")

    def collect_product_urls_on_page(
        self, max_price: float, limit: int, current_urls: list
    ) -> list:
        self.page.locator(self._product_container).first.wait_for(
            state="visible", timeout=config.DEFAULT_TIMEOUT
        )
        cards = self.page.locator(self._product_container).all()
        for card in cards:
            if len(current_urls) >= limit:
                break
            try:
                card_text = card.inner_text()
            except Exception:
                card_text = ""
            if not is_cartable_listing_text(card_text):
                continue
            price = self._parse_card_price(card)
            if price <= max_price:
                link_element = card.locator(self._product_link).first
                url = link_element.get_attribute("href")
                if url and url not in current_urls:
                    current_urls.append(url)
        return current_urls

    def go_to_next_results_page(self) -> bool:
        next_btn = self.page.locator(self._next_page_button)
        if next_btn.is_visible() and next_btn.is_enabled():
            next_btn.click()
            self.wait_for_page_loaded()
            return True
        return False

    def search_items_by_name_under_price(
        self,
        query: str,
        max_price: float,
        limit: int = 5,
        pool_size: Optional[int] = None,
    ) -> list:
        target_pool = pool_size or max(limit * 3, limit)
        self.search_for_query(query)
        self.apply_price_ceiling_filter(max_price)
        self.apply_buy_it_now_filter()
        valid_urls: list[str] = []
        pages_scanned = 0
        while (
            len(valid_urls) < target_pool
            and pages_scanned < config.MAX_PAGINATION_PAGES
        ):
            valid_urls = self.collect_product_urls_on_page(
                max_price, target_pool, valid_urls
            )
            pages_scanned += 1
            if len(valid_urls) >= target_pool:
                break
            if not self.go_to_next_results_page():
                break
        self._log(
            f"\n[InventoryPage] Found {len(valid_urls)} product URLs matching criteria:"
        )
        for index, url in enumerate(valid_urls, 1):
            self._log(f"  [{index}] {url}")
        return valid_urls

    def add_items_to_cart(
        self,
        product_urls: list,
        max_price: float,
        target_count: Optional[int] = None,
    ) -> list:
        """Delegates multi-tab add workflow; keeps stable API for tests."""
        return AddItemsToCartFlow(
            self.page.context,
            max_price=max_price,
            target_count=target_count,
        ).run(product_urls)
