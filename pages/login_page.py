import config
from playwright.sync_api import Page
from pages.base_page import BasePage

class LoginPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        
        self._username_input = page.get_by_role("textbox", name="Email or username")
        self._password_input = page.get_by_placeholder("Password")
        
        self._continue_button = page.get_by_role("button", name="Continue")
        self._sign_in_button = page.get_by_role("button", name="Sign in")

    def login(
        self,
        username: str = config.EBAY_USERNAME,
        password: str = config.EBAY_PASSWORD,
    ) -> None:
        self._log(f"[Auth] Navigating to login page: {config.SIGN_IN_URL}")
        self.navigate(config.SIGN_IN_URL)
        
        self._username_input.wait_for(state="visible", timeout=config.DEFAULT_TIMEOUT)
        self._username_input.fill(username)
        
        self._continue_button.click(timeout=config.DEFAULT_TIMEOUT)

        try:
            self._password_input.wait_for(state="visible", timeout=config.DEFAULT_TIMEOUT)
            self._password_input.fill(password)

            self._sign_in_button.click(timeout=config.DEFAULT_TIMEOUT)
            self.page.wait_for_load_state(
                config.PAGE_LOADED_INDICATOR, timeout=config.LONG_TIMEOUT
            )
            self._log("[Auth] Login form submitted successfully.")
            
        except Exception as e:
            self._log(f"[Warning] Login field or button not interactive ({e}). Continuing to main flow.")