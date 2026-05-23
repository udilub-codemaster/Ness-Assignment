import re

import config
from playwright.sync_api import Page

from pages.base_page import BasePage
from pages.components.ebay_variant_selector import EbayVariantSelector
from utils.string_helpers import extract_float_from_string
from utils.variant_helpers import label_needs_selection


class ProductPage(BasePage):

    def __init__(self, page: Page):
        super().__init__(page)
        self._product_title = "h1.x-item-title__mainTitle"
        self._product_price = "div.x-price-primary span.ux-textspans"
        self._add_to_cart_button = (
            "a[data-testid='ux-call-to-action']:has-text('Add to cart'), "
            "a:has-text('Add to basket'), "
            "button:has-text('Add to cart'), "
            "button:has-text('Add to basket')"
        )
        self.variants = EbayVariantSelector(page)

    def get_product_title(self) -> str:
        self.page.locator(self._product_title).wait_for(
            state="visible", timeout=config.DEFAULT_TIMEOUT
        )
        return self.page.locator(self._product_title).text_content().strip()

    def get_product_price(self) -> float:
        self.page.locator(self._product_price).first.wait_for(
            state="visible", timeout=config.DEFAULT_TIMEOUT
        )
        raw_price = self.page.locator(self._product_price).first.text_content()
        return extract_float_from_string(raw_price)

    def get_pending_variants(self) -> list[str]:
        return self.variants.get_pending_variants()

    def has_add_to_cart(self) -> bool:
        cart_btn = self.page.locator(self._add_to_cart_button).first
        try:
            cart_btn.wait_for(state="visible", timeout=config.SHORT_TIMEOUT)
            return True
        except Exception:
            return False

    def is_auction_only_listing(self) -> bool:
        place_bid = self.page.get_by_role(
            "button", name=re.compile(r"place bid", re.IGNORECASE)
        )
        return place_bid.count() > 0

    def _click_add_to_cart_button(self) -> bool:
        has_variants = self.variants.has_controls()
        pending = self.get_pending_variants()

        if has_variants and pending:
            self._log(
                f"[Warning] Cannot add to cart — mandatory variants not selected: {pending}"
            )
            return False

        if has_variants and self.variants.count_variant_listboxes() > 0:
            unselected = [
                (b.text_content() or "").strip()
                for b in self.variants.list_variation_buttons()
                if label_needs_selection(
                    (b.text_content() or "").strip(),
                    (b.get_attribute("value") or "").strip(),
                )
            ]
            if unselected:
                self._log(
                    f"[Warning] Cannot add to cart — {len(unselected)} listbox(es) "
                    f"still need selection: {unselected}"
                )
                return False

        cart_btn = self.page.locator(self._add_to_cart_button).first
        try:
            cart_btn.wait_for(state="visible", timeout=config.DEFAULT_TIMEOUT)
        except Exception:
            if self.is_auction_only_listing():
                self._log(
                    "[Warning] Skipping auction listing (Place bid only, no Add to cart)."
                )
            else:
                self._log("[Warning] Add to cart button not found on this listing.")
            return False

        if has_variants:
            self.variants.dismiss_variant_overlay()

        cart_btn.scroll_into_view_if_needed()
        try:
            cart_btn.click(timeout=config.DEFAULT_TIMEOUT)
        except Exception:
            self._log("[Debug] Add to cart blocked — retrying with force click.")
            cart_btn.click(force=True, timeout=config.DEFAULT_TIMEOUT)
        self.page.wait_for_timeout(800)

        if self.variants.has_variant_selection_error():
            return False

        return True

    def add_to_cart(self) -> bool:
        self.variants.select_all_random()
        if self._click_add_to_cart_button():
            return True

        if self.variants.has_variant_selection_error():
            self._log(
                "[Debug] Variant error after add — re-probing controls and retrying."
            )
            self.variants.select_all_random(force_probe=True)
            if self._click_add_to_cart_button():
                return True
            self._log(
                "[Warning] Add to cart blocked — eBay shows mandatory variant error."
            )

        return False
