import re

import config
from playwright.sync_api import Page

from pages.base_page import BasePage
from utils.price_parser import CURRENCY_PATTERN, parse_subtotal_from_summary
from utils.string_helpers import parse_currency_amount


class CartPage(BasePage):
    _CART_URLS = (
        "https://cart.payments.ebay.com/sc/view",
        "https://cart.payments.ebay.com/",
    )
    _SUMMARY_SECTIONS = (
        "[data-testid='cart-summary']",
        "[class*='cart-order-summary']",
        "[class*='order-summary']",
        "section:has-text('Order summary')",
        "aside:has-text('Subtotal')",
    )

    def __init__(self, page: Page):
        super().__init__(page)
        self._cart_icon_link = (
            "a[aria-label*='Your shopping cart'], "
            "a[aria-label*='shopping cart'], "
            "a[href*='cart.payments.ebay.com'], "
            "a[href*='cart.ebay.com']"
        )
        self._empty_cart_text = (
            "text=You don't have any items in your cart, "
            "text=Your cart is empty"
        )

    def open_cart_via_header(self) -> bool:
        try:
            cart_link = self.page.locator(self._cart_icon_link).first
            cart_link.wait_for(state="visible", timeout=config.SHORT_TIMEOUT)
            self._log("[CartPage] Opening cart via header cart link...")
            cart_link.click(timeout=config.DEFAULT_TIMEOUT)
            self.page.wait_for_load_state("load", timeout=config.LONG_TIMEOUT)
            self.page.wait_for_timeout(1500)
            return self.is_ebay_cart_url() and not self.is_ebay_error_page()
        except Exception as exc:
            self._log(f"[CartPage] Header cart navigation failed: {exc}")
            return False

    def open_cart_by_url(self) -> None:
        for cart_url in self._CART_URLS:
            self._log(f"[CartPage] Navigating to cart: {cart_url}")
            self.page.goto(cart_url, wait_until="load", timeout=config.LONG_TIMEOUT)
            self.page.wait_for_timeout(1500)
            if self.is_ebay_error_page():
                self._log(f"[Warning] Cart URL redirected to error page: {self.page.url}")
                continue
            if self.is_ebay_cart_url():
                self._log(f"[CartPage] Cart loaded at: {self.page.url}")
                return
        raise RuntimeError(
            f"Could not reach eBay cart page. Last URL: {self.page.url}. "
            f"Use cart.payments.ebay.com (www.ebay.com/cart returns /n/error)."
        )

    def navigate_to_cart(self) -> None:
        try:
            self.open_cart_by_url()
            if not self.is_ebay_captcha_page():
                return
            self._log("[CartPage] Direct cart URL hit captcha; trying header cart link...")
        except Exception as exc:
            self._log(f"[CartPage] Direct cart URL failed: {exc}")

        if self.open_cart_via_header() and not self.is_ebay_captcha_page():
            return

        if self.is_ebay_captcha_page():
            raise RuntimeError(
                "eBay showed a captcha/verification page when opening the cart. "
                "Complete verification manually and re-run the test."
            )
        self.open_cart_by_url()

    def is_cart_empty(self) -> bool:
        if self.page.locator(self._empty_cart_text).count() > 0:
            return True
        return "don't have any items in your cart" in (
            self.page.locator("body").inner_text().lower()
        )

    def _read_subtotal_from_sections(self) -> float | None:
        for selector in self._SUMMARY_SECTIONS:
            section = self.page.locator(selector)
            if section.count() == 0:
                continue
            for index in range(min(section.count(), 3)):
                summary_text = section.nth(index).inner_text()
                price = parse_subtotal_from_summary(summary_text)
                if price is not None:
                    self._log(
                        f"[CartPage] Subtotal ${price} parsed from summary ({selector})"
                    )
                    return price
        return None

    def _read_subtotal_fallback(self, body_text: str) -> float | None:
        price = parse_subtotal_from_summary(body_text)
        if price is not None:
            self._log(f"[CartPage] Subtotal ${price} parsed from page body")
            return price

        currency_nodes = self.page.locator("span, div, p").filter(
            has_text=CURRENCY_PATTERN
        )
        for index in range(currency_nodes.count()):
            raw = (currency_nodes.nth(index).inner_text() or "").strip()
            if re.search(r"\d", raw):
                try:
                    value = parse_currency_amount(raw)
                    self._log(f"[CartPage] Fallback currency node: '{raw}' -> ${value}")
                    return value
                except ValueError:
                    continue
        return None

    def get_cart_total(self) -> float:
        if self.is_ebay_captcha_page():
            raise AssertionError(
                "Cannot read cart total — eBay verification/captcha page is showing."
            )
        if self.is_cart_empty():
            raise AssertionError(
                "Cart is empty — items may not have been added to this browser session."
            )

        price = self._read_subtotal_from_sections()
        if price is not None:
            return price

        body_text = self.page.locator("body").inner_text()
        price = self._read_subtotal_fallback(body_text)
        if price is not None:
            return price

        subtotal_index = body_text.lower().find("subtotal")
        snippet = (
            body_text[subtotal_index : subtotal_index + 80]
            if subtotal_index >= 0
            else body_text[:120]
        )
        raise AssertionError(
            f"Could not find cart subtotal price on page. Summary snippet: {snippet}"
        )
