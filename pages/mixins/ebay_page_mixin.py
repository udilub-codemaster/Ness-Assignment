import config
from playwright.sync_api import Page


class EbayPageMixin:
    """Shared eBay page guards and load waits."""

    page: Page

    def wait_for_page_loaded(self) -> None:
        self.page.wait_for_load_state(
            config.PAGE_LOADED_INDICATOR,
            timeout=config.DEFAULT_TIMEOUT,
        )

    def is_ebay_error_page(self) -> bool:
        url = self.page.url.lower()
        title = (self.page.title() or "").lower()
        return "/n/error" in url or "error page" in title

    def is_ebay_captcha_page(self) -> bool:
        url = self.page.url.lower()
        if "captcha" in url or "splashui/challenge" in url:
            return True
        body = (self.page.locator("body").inner_text() or "").lower()[:600]
        return "verify yourself" in body or "pardon our interruption" in body

    def is_ebay_cart_url(self) -> bool:
        url = self.page.url.lower()
        return "cart.payments.ebay.com" in url or (
            "cart" in url and not self.is_ebay_error_page()
        )
