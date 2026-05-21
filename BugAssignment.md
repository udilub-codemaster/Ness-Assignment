# Code review assignment

## There are a few problems in the provided code that can cause issues

### 1. The code imports both Selenium and Playwright packages — we only need one (Playwright)

**The problem**

Unnecessary dependencies increase memory use and suggest copy-paste without cleanup. That can also create conflicts later when more code is added.

**The fix**

Remove Selenium imports; keep only Playwright.

```python
# Remove lines like:
# from selenium import webdriver
```

---

### 2. Missing context manager for browser lifecycle

**The problem**

The browser is started with `sync_playwright().start()` and `chromium.launch()` without a Python context manager (`with`).

If the test fails or raises partway through, teardown may never run. That can leave browser processes running in the background (zombie processes and memory leaks on the runner machine).

**The fix**

Prefer **pytest-playwright** fixtures so lifecycle is managed for you: import `Page` from Playwright and inject it into the test. That typically launches Chromium by default and can reduce boilerplate.

---

### 3. Using `time.sleep` for waiting

**The problem**

Hard-coded sleeps make tests flaky: if load time increases, the test can fail before the element appears; if the UI is already ready, time is wasted.

**The fix**

Rely on Playwright’s auto-waiting. For specific conditions, use explicit waits, for example:

```python
page.wait_for_selector("selector")
# or with expect():
expect(locator).to_be_visible()
```

---

### 4. Missing assertion

**The problem**

The flow runs actions but does not assert outcomes (e.g. a locator is defined but never checked). Without assertions, the “test” always passes unless the page hard-crashes, so it won’t catch regressions.

**The fix**

Add meaningful assertions, for example:

```python
expect(results.first).to_be_visible(timeout=5000)
# or:
expect(results).to_have_count(5)
```

---

### 5. Browser teardown inside the test

**The problem**

Calling `browser.close()` at the end of the test is fragile: if an earlier line fails, cleanup never runs and the browser can stay open.

**The fix**

Move cleanup to **pytest fixtures** in `conftest.py` or use a context manager so teardown runs whether the test passes or fails.

Example fixture pattern:

```python
import pytest
from playwright.sync_api import sync_playwright
from pages.inventory_page import InventoryPage


@pytest.fixture(scope="function")
def session_page():
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    yield page

    page.close()
    context.close()
    browser.close()
    playwright.stop()


@pytest.fixture(scope="function")
def inventory_page(session_page):
    return InventoryPage(session_page)
```
