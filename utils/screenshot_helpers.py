import os

from playwright.sync_api import Page


def save_page_screenshot(page: Page, path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    page.screenshot(path=path)
