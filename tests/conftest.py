import os
import pytest


def pytest_collection_modifyitems(config, items):
    if os.getenv("GITHUB_ACTIONS") == "true":
        skip_captcha = pytest.mark.skip(
            reason="Skipping UI tests in CI environment to avoid Captcha"
        )
        for item in items:
            if "test_e2e" in item.nodeid or "search" in item.nodeid:
                item.add_marker(skip_captcha)