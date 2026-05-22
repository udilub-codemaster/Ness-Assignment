import sys

import config
from playwright.sync_api import Page

from pages.mixins.ebay_page_mixin import EbayPageMixin


class BasePage(EbayPageMixin):
    def __init__(self, page: Page):
        self.page = page

    @staticmethod
    def _log(message: str) -> None:
        try:
            print(message)
        except UnicodeEncodeError:
            encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
            safe = message.encode(encoding, errors="replace").decode(
                encoding, errors="replace"
            )
            print(safe)

    def navigate(self, url: str, **kwargs) -> None:
        kwargs.setdefault("timeout", config.LONG_TIMEOUT)
        self.page.goto(url, **kwargs)

    def click_element(self, locator: str) -> None:
        self.page.locator(locator).click()
