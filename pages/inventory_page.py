import config
import re
from pages.base_page import BasePage
from playwright.sync_api import Page, Locator

class InventoryPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self._search_box = "#gh-ac"
        self._search_button = "#gh-search-btn"
        self._product_container = "ul.srp-results .s-card.s-card--vertical"
        self._product_link = "a.s-card__link, a[href*='/itm/']"
        self._product_price = ".s-card__price, .s-item__price"
        self._next_page_button = "a.pagination__next"
        self._max_price_filter = "input[aria-label*='Maximum Value'], input[placeholder='max']"
        self._submit_price_button = "button[aria-label='Submit price range']"

    def navigate_to_ebay(self):
        self.navigate(config.BASE_URL)

    def _wait_for_page_ready(self):
        self.page.wait_for_load_state(
            config.PAGE_LOADED_INDICATOR,
            timeout=config.DEFAULT_TIMEOUT,
        )

    def _execute_initial_search(self, query: str):
        search_input = self.page.locator(self._search_box)
        search_input.wait_for(state="visible", timeout=config.DEFAULT_TIMEOUT)
        search_input.fill(query)
        self.click_element(self._search_button)
        self._wait_for_page_ready()
        print(f"[Debug] Executed initial search for: {query}")

    def _apply_max_price_filter(self, max_price: float):
        max_price_input = self.page.locator(self._max_price_filter)
        submit_btn = self.page.locator(self._submit_price_button)
        try:
            max_price_input.wait_for(state="visible", timeout=config.SHORT_TIMEOUT)
            max_price_input.fill(str(int(max_price) if max_price == int(max_price) else max_price))
            max_price_input.blur()
            print(f"[Debug] Filled max price: {max_price}")
            submit_btn.wait_for(state="enabled", timeout=config.SHORT_TIMEOUT)
            submit_btn.click(timeout=config.SHORT_TIMEOUT)
            print("[Debug] Clicked Submit price range button.")
            self._wait_for_page_ready()
            print("[Debug] Successfully applied max price filter via UI.")
        except Exception as e:
            print(f"[Warning] Could not apply UI max price filter (Error: {e}), falling back to code-level filtering.")

    def _extract_price(self, card_locator: Locator) -> float:
        try:
            price_text = card_locator.locator(self._product_price).first.inner_text()
            cleaned_price = float(re.sub(r"[^\d.]", "", price_text.split("to")[0]))
            return cleaned_price
        except Exception:
            return float("inf")

    def _get_valid_urls_from_current_page(self, max_price: float, limit: int, current_urls: list) -> list:
        self.page.locator(self._product_container).first.wait_for(
            state="visible", timeout=config.DEFAULT_TIMEOUT
        )
        cards = self.page.locator(self._product_container).all()
        for card in cards:
            if len(current_urls) >= limit:
                break
            price = self._extract_price(card)
            if price <= max_price:
                link_element = card.locator(self._product_link).first
                url = link_element.get_attribute("href")
                if url and url not in current_urls:
                    current_urls.append(url)
        return current_urls

    def _go_to_next_page(self) -> bool:
        next_btn = self.page.locator(self._next_page_button)
        if next_btn.is_visible() and next_btn.is_enabled():
            next_btn.click()
            self._wait_for_page_ready()
            return True
        return False

    def search_items_by_name_under_price(self, query: str, max_price: float, limit: int = 5) -> list:
        self._execute_initial_search(query)
        self._apply_max_price_filter(max_price)
        valid_urls = []
        pages_scanned = 0
        while len(valid_urls) < limit and pages_scanned < config.MAX_PAGINATION_PAGES:
            valid_urls = self._get_valid_urls_from_current_page(max_price, limit, valid_urls)
            pages_scanned += 1
            if len(valid_urls) >= limit:
                break
            if not self._go_to_next_page():
                break
        print(f"\n[InventoryPage] Found {len(valid_urls)} product URLs matching criteria:")
        for i, url in enumerate(valid_urls, 1):
            print(f"  [{i}] {url}")
        return valid_urls
