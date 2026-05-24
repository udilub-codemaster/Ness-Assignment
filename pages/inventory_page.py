import config
from typing import Optional
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Locator, Page

from flows.add_items_to_cart_flow import AddItemsToCartFlow
from pages.base_page import BasePage
from utils.listing_helpers import (
    build_filtered_search_url,
    is_cartable_listing_text,
    url_has_filtered_search_params,
)
from utils.price_parser import parse_price_from_listing_card


class InventoryPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self._product_container = "ul.srp-results .s-card.s-card--vertical"
        self._product_link = "a.s-card__link, a[href*='/itm/']"
        self._product_price = ".s-card__price, .s-item__price"
        self._next_page_button = "a.pagination__next"
        self._last_search_query: str | None = None

    def navigate_to_ebay(self) -> None:
        self.navigate(config.BASE_URL)

    def search_with_filters(self, query: str, max_price: float) -> None:
        """Navigate once to SRP with BIN + max-price filters in the URL."""
        self._last_search_query = query
        url = build_filtered_search_url(query, max_price, config.BASE_URL)
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                self.navigate(url)
                self._wait_for_results_ready()
                if not url_has_filtered_search_params(self.page.url, max_price):
                    raise RuntimeError(
                        f"Filter params missing from URL: {self.page.url}"
                    )
                if not self._results_look_filtered(max_price):
                    raise RuntimeError(
                        "No in-budget listings on first page; filters may not be active."
                    )
                self._log(
                    f"[InventoryPage] Filtered search loaded (attempt {attempt + 1}): "
                    f"{query!r}, max ${max_price}, Buy It Now"
                )
                return
            except Exception as exc:
                last_error = exc
                self._log(
                    f"[InventoryPage] Filtered search attempt {attempt + 1} failed: {exc}"
                )
        raise RuntimeError(
            f"Could not load filtered search for {query!r} under ${max_price}"
        ) from last_error

    def _wait_for_results_ready(self) -> None:
        self.page.locator(self._product_container).first.wait_for(
            state="visible", timeout=config.DEFAULT_TIMEOUT
        )

    def _results_look_filtered(self, max_price: float) -> bool:
        cards = self.page.locator(self._product_container).all()[:8]
        if not cards:
            return False
        for card in cards:
            try:
                card_text = card.inner_text()
            except Exception:
                continue
            if not is_cartable_listing_text(card_text):
                continue
            if self._parse_card_price(card) <= max_price:
                return True
        return False

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

    def go_to_next_results_page(self, max_price: float) -> bool:
        next_btn = self.page.locator(self._next_page_button)
        if not (next_btn.is_visible() and next_btn.is_enabled()):
            return False
        next_btn.click(timeout=config.DEFAULT_TIMEOUT)
        self.wait_for_page_loaded()
        if url_has_filtered_search_params(self.page.url, max_price):
            return True
        query = self._query_from_current_url(self.page.url) or self._last_search_query
        if not query:
            self._log("[Warning] Pagination dropped filter params and query unknown.")
            return False
        self._log(
            "[Warning] Pagination dropped filter params; reloading filtered search."
        )
        self.search_with_filters(query, max_price)
        return True

    @staticmethod
    def _query_from_current_url(url: str) -> str | None:
        values = parse_qs(urlparse(url).query).get("_nkw")
        if values and values[0].strip():
            return values[0].strip()
        return None

    def search_items_by_name_under_price(
        self,
        query: str,
        max_price: float,
        limit: int = 5,
        pool_size: Optional[int] = None,
    ) -> list:
        target_pool = pool_size or max(limit * 3, limit)
        self.search_with_filters(query, max_price)
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
            if not self.go_to_next_results_page(max_price):
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
        return AddItemsToCartFlow(
            self.page.context,
            max_price=max_price,
            target_count=target_count,
        ).run(product_urls)
