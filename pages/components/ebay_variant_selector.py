import random
import re

import config
from playwright.sync_api import Locator, Page

from pages.base_page import BasePage
from utils.variant_helpers import (
    is_valid_variant_option,
    label_needs_selection,
    normalize_option_text,
    variant_sort_key,
)


class EbayVariantSelector(BasePage):

    def __init__(self, page: Page):
        super().__init__(page)
        self._legacy_variation_dropdowns = (
            "select[id*='x-msku-vsw'], select.x-msku-select-box, select[id*='msku']"
        )
        self._sku_section = "div.vim.x-sku, div.x-sku, div.vim.x-msku, div.x-msku-evo"
        self._variation_listbox_buttons = (
            "div.vim.x-sku .listbox-button button.listbox-button__control, "
            "div.x-sku .listbox-button button.listbox-button__control, "
            "div.vim.x-msku .listbox-button button.listbox-button__control, "
            "div.x-msku-evo .listbox-button button.listbox-button__control"
        )
        self._variant_hint_selectors = (
            "[data-testid='x-msku'], .x-msku, .x-sku, #msku-variation"
        )
        self._variant_error_text = re.compile(
            r"please select|select a|select an|mandatory|before you can|"
            r"choose a|out of stock.*select",
            re.IGNORECASE,
        )
        self._select_hint_text = re.compile(r":\s*select\b", re.IGNORECASE)
        self._variant_controls_cached: bool | None = None

    def _selection_applied(self, button: Locator) -> bool:
        text = (button.text_content() or "").strip()
        value = (button.get_attribute("value") or "").strip()
        return not label_needs_selection(text, value)

    def _listbox_needs_selection(self, button: Locator) -> bool:
        text = (button.text_content() or "").strip()
        value = (button.get_attribute("value") or "").strip()
        if not label_needs_selection(text, value):
            return False
        native = self._get_native_select(button)
        if native is not None and self._native_selection_applied(button, native):
            return False
        return True

    def _invalidate_variant_cache(self) -> None:
        self._variant_controls_cached = None

    def has_controls(self) -> bool:
        return self._probe_variant_controls(use_cache=True)

    def _count_variant_controls_now(self) -> int:
        listbox_count = self.page.locator(self._variation_listbox_buttons).count()
        if listbox_count > 0:
            return listbox_count
        return self.page.locator(self._legacy_variation_dropdowns).count()

    def _variant_hints_present(self) -> bool:
        if self.page.locator(self._sku_section).count() > 0:
            return True
        if self.page.locator(self._variant_hint_selectors).count() > 0:
            return True
        return self.page.get_by_text(self._select_hint_text).count() > 0

    def _wait_for_variant_area(self) -> None:
        if self._count_variant_controls_now() > 0:
            return
        if not self._variant_hints_present():
            return

        for _ in range(config.VARIANT_POLL_ATTEMPTS):
            if self._count_variant_controls_now() > 0:
                return
            self.page.wait_for_timeout(config.VARIANT_POLL_INTERVAL_MS)

        try:
            self.page.locator(self._sku_section).first.wait_for(
                state="attached", timeout=config.VARIANT_SKU_WAIT_MS
            )
        except Exception:
            pass

        for _ in range(config.VARIANT_POLL_ATTEMPTS):
            if self._count_variant_controls_now() > 0:
                return
            self.page.wait_for_timeout(config.VARIANT_POLL_INTERVAL_MS)

    def _probe_variant_controls(self, *, use_cache: bool = True) -> bool:
        if use_cache and self._variant_controls_cached is not None:
            return self._variant_controls_cached

        self._wait_for_variant_area()
        has_controls = self._count_variant_controls_now() > 0
        self._variant_controls_cached = has_controls
        return has_controls

    def _is_feedback_listbox(self, button: Locator) -> bool:
        container = button.locator(
            "xpath=ancestor::div[contains(@class,'listbox-button')][1]"
        )
        native = container.locator("select.listbox__native")
        if native.count() == 0:
            return False
        name = (native.get_attribute("name") or "").lower()
        return "feedback" in name

    def _list_variation_buttons(self) -> list[Locator]:
        buttons = self.page.locator(self._variation_listbox_buttons)
        variation_buttons = []
        for i in range(buttons.count()):
            button = buttons.nth(i)
            if self._is_feedback_listbox(button):
                continue
            variation_buttons.append(button)
        return variation_buttons

    def _count_variant_listboxes(self) -> int:
        return len(self._list_variation_buttons())

    def get_pending_variants(self) -> list[str]:
        pending = []
        for button in self._list_variation_buttons():
            if self._listbox_needs_selection(button):
                pending.append((button.text_content() or "").strip())
        return pending

    def _get_pending_variant_targets(self) -> list[dict]:
        pending = []
        for button in self._list_variation_buttons():
            if not self._listbox_needs_selection(button):
                continue
            text = (button.text_content() or "").strip()
            controls = button.get_attribute("aria-controls") or ""
            if controls:
                pending.append({"text": text, "controls": controls})
        return pending

    def _listbox_is_open(self, button: Locator) -> bool:
        # x-msku-evo keeps option nodes visible when collapsed; aria-expanded is reliable.
        return button.get_attribute("aria-expanded") == "true"

    def _native_selection_applied(self, button: Locator, native: Locator) -> bool:
        if self._selection_applied(button):
            return True
        options = native.locator("option")
        for i in range(options.count()):
            option = options.nth(i)
            if option.get_attribute("selected") is not None:
                text = normalize_option_text(option.text_content() or "")
                if is_valid_variant_option(text):
                    return True
        try:
            current_value = native.input_value()
        except Exception:
            return False
        if not current_value:
            return False
        for i in range(options.count()):
            option = options.nth(i)
            if (option.get_attribute("value") or "") != current_value:
                continue
            text = normalize_option_text(option.text_content() or "")
            return is_valid_variant_option(text)
        return False

    def dismiss_variant_overlay(self) -> None:
        """Dismiss expanded SKU overlays before clicking elsewhere (e.g. Add to cart)."""
        self.page.keyboard.press("Escape")
        try:
            self.page.locator("h1.x-item-title__mainTitle").click(timeout=1500)
        except Exception:
            pass
        self.page.wait_for_timeout(200)

    def _collapse_listbox_if_open(self, button: Locator | None = None) -> None:
        """Close expanded listboxes only — no title click, no retry loop."""
        expanded = self.page.locator(
            f"{self._sku_section} button.listbox-button__control[aria-expanded='true']"
        )
        if expanded.count() == 0 and (
            button is None or button.get_attribute("aria-expanded") != "true"
        ):
            return

        self.page.keyboard.press("Escape")
        targets: list[Locator] = []
        if button is not None and button.get_attribute("aria-expanded") == "true":
            targets.append(button)
        for i in range(expanded.count()):
            targets.append(expanded.nth(i))

        seen: set[str] = set()
        for target in targets:
            try:
                if target.get_attribute("aria-expanded") != "true":
                    continue
                key = target.get_attribute("aria-controls") or str(id(target))
                if key in seen:
                    continue
                seen.add(key)
                target.click(timeout=1500)
            except Exception:
                pass
        self.page.wait_for_timeout(150)

    def _open_listbox(self, button: Locator) -> bool:
        button.scroll_into_view_if_needed()
        button.click(timeout=config.DEFAULT_TIMEOUT)

        for _ in range(30):
            if self._listbox_is_open(button):
                return True
            self.page.wait_for_timeout(100)

        if self._listbox_is_open(button):
            return True

        button.click(timeout=config.DEFAULT_TIMEOUT)
        for _ in range(15):
            if self._listbox_is_open(button):
                return True
            self.page.wait_for_timeout(100)
        return self._listbox_is_open(button)

    def _find_listbox_button(self, controls_id: str) -> Locator | None:
        button = self.page.locator(
            f"button.listbox-button__control[aria-controls='{controls_id}']"
        )
        return button.first if button.count() > 0 else None

    def _click_locator_targets(self, *targets: Locator) -> bool:
        for target in targets:
            if target.count() == 0:
                continue
            try:
                target.scroll_into_view_if_needed()
                target.click(timeout=config.DEFAULT_TIMEOUT)
            except Exception:
                try:
                    target.click(force=True, timeout=config.DEFAULT_TIMEOUT)
                except Exception:
                    continue
            return True
        return False

    def _try_native_random_select(
        self, button: Locator, label: str, native: Locator
    ) -> bool:
        if self._native_selection_applied(button, native):
            return True

        options = native.locator("option")
        valid_indices = []
        for i in range(options.count()):
            option = options.nth(i)
            text = normalize_option_text(option.text_content() or "")
            if option.get_attribute("disabled") is not None:
                continue
            if text and not is_valid_variant_option(text):
                continue
            if not text and i == 0:
                continue
            valid_indices.append(i)

        if not valid_indices:
            valid_indices = list(range(1, options.count()))
        if not valid_indices:
            return False

        idx = random.choice(valid_indices)
        self._log(f"[Debug] Listbox '{label}': selecting index {idx} via native select")
        try:
            native.select_option(index=idx, force=True)
        except Exception:
            native.select_option(index=idx)

        for _ in range(15):
            if self._native_selection_applied(button, native):
                return True
            self.page.wait_for_timeout(200)

        return self._native_selection_applied(button, native)

    def _sync_listbox_choice(
        self, button: Locator, controls_id: str, choice: str
    ) -> bool:
        want = normalize_option_text(choice)
        native = self._get_native_select(button)
        if native is not None:
            native_options = native.locator("option")
            for i in range(native_options.count()):
                option = native_options.nth(i)
                option_label = normalize_option_text(option.text_content() or "")
                if option_label == want or want in option_label:
                    try:
                        native.select_option(index=i, force=True)
                    except Exception:
                        native.select_option(index=i)
                    break
            self.page.wait_for_timeout(350)
            return self._native_selection_applied(button, native)

        panel = self.page.locator(f"#{controls_id}")
        if panel.count() == 0:
            return False

        if button.get_attribute("aria-expanded") != "true":
            self._open_listbox(button)

        options = panel.locator("[role='option'], .listbox__option")
        for i in range(options.count()):
            option = options.nth(i)
            try:
                if not option.is_visible():
                    continue
            except Exception:
                pass
            opt_text = normalize_option_text(option.text_content() or "")
            if opt_text != want and want not in opt_text:
                continue
            self._click_locator_targets(
                option, option.locator(".listbox__option").first
            )
            break

        self.page.wait_for_timeout(350)
        self._collapse_listbox_if_open(button)
        return self._selection_applied(button)

    def _apply_listbox_choice(
        self,
        button: Locator,
        controls_id: str,
        option: Locator,
        choice: str,
    ) -> bool:
        if self._click_locator_targets(
            option, option.locator(".listbox__option").first
        ):
            self.page.wait_for_timeout(350)
            if self._selection_applied(button):
                self._collapse_listbox_if_open(button)
                return True

        if self._sync_listbox_choice(button, controls_id, choice):
            return self._selection_applied(button)

        return False

    def _try_ui_random_select(
        self, button: Locator, controls_id: str, label: str
    ) -> bool:
        if not self._open_listbox(button):
            self._log(f"[Debug] Listbox '{label}': could not expand dropdown")
            return False

        panel = self.page.locator(f"#{controls_id}")
        try:
            panel.wait_for(state="visible", timeout=config.SHORT_TIMEOUT)
        except Exception:
            pass

        valid = self._collect_valid_listbox_options(panel)
        if not valid:
            self._log(
                f"[Debug] Listbox '{label}': no visible options in panel #{controls_id}"
            )
            self._collapse_listbox_if_open()
            return False

        random.shuffle(valid)
        for option, choice in valid:
            self._log(f"[Debug] Listbox '{label}': selecting '{choice}'")
            if self._apply_listbox_choice(button, controls_id, option, choice):
                applied = (button.text_content() or "").strip()
                self._log(f"[Debug] Listbox '{label}': applied -> '{applied}'")
                self._collapse_listbox_if_open(button)
                self.page.wait_for_timeout(400)
                return True

        self._collapse_listbox_if_open()
        self._log(f"[Debug] Listbox '{label}': option click did not apply")
        return False

    def _select_random_for_listbox(self, button: Locator, label: str) -> bool:
        """Pick a random valid option for one variant listbox."""
        if not self._listbox_needs_selection(button):
            return True

        controls_id = button.get_attribute("aria-controls") or ""
        if not controls_id:
            return False

        native = self._get_native_select(button)
        if native is not None and self._try_native_random_select(button, label, native):
            return True
        if native is not None and self._native_selection_applied(button, native):
            return True

        single_variant = self._count_variant_listboxes() == 1
        if single_variant and native is not None:
            self._log(
                f"[Debug] Listbox '{label}': native select failed on single-variant listing"
            )
            return False

        if not single_variant:
            self._collapse_listbox_if_open()
            self.page.wait_for_timeout(300)

        return self._try_ui_random_select(button, controls_id, label)

    def _select_variants_via_playwright(self) -> int:
        selected = 0
        max_rounds = max(10, self._count_variant_listboxes() * 3)

        for round_num in range(1, max_rounds + 1):
            pending = self._get_pending_variant_targets()
            if not pending:
                break

            pending.sort(key=lambda target: variant_sort_key(target["text"]))
            self._log(
                f"[Debug] Variant round {round_num}: "
                f"{len(pending)} unselected — {[p['text'] for p in pending]}"
            )

            for target in pending:
                label = target["text"]
                button = self._find_listbox_button(target["controls"])
                if button is None or not self._listbox_needs_selection(button):
                    continue
                if self._select_random_for_listbox(button, label):
                    selected += 1

        return selected

    def _collect_valid_listbox_options(
        self, listbox: Locator
    ) -> list[tuple[Locator, str]]:
        valid = []
        options = listbox.locator("[role='option'], .listbox__option")
        for i in range(options.count()):
            option = options.nth(i)
            try:
                if not option.is_visible():
                    continue
            except Exception:
                pass
            option_text = normalize_option_text(option.text_content() or "")
            if is_valid_variant_option(option_text):
                valid.append((option, option_text))
        return valid

    def _get_native_select(self, button: Locator) -> Locator | None:
        container = button.locator(
            "xpath=ancestor::div[contains(@class,'listbox-button')][1]"
        )
        native = container.locator("select.listbox__native")
        if native.count() == 0:
            return None
        return native.first

    def _select_random_legacy_dropdowns(self) -> int:
        dropdowns = self.page.locator(self._legacy_variation_dropdowns)
        selected = 0
        for i in range(dropdowns.count()):
            dropdown = dropdowns.nth(i)
            options = dropdown.locator("option").all_text_contents()
            valid_options = [
                opt.strip() for opt in options if is_valid_variant_option(opt)
            ]
            if not valid_options:
                continue
            random_choice = random.choice(valid_options)
            self._log(f"[Debug] Legacy dropdown {i + 1}: selecting '{random_choice}'")
            dropdown.select_option(label=random_choice)
            selected += 1
        return selected

    def has_variant_selection_error(self) -> bool:
        errors = self.page.locator(
            "div.x-alert, div.ux-message, [role='alert'], .ux-call-to-action-variation"
        ).filter(has_text=self._variant_error_text)
        return errors.count() > 0

    def select_all_random(self, *, force_probe: bool = False):
        if force_probe:
            self._invalidate_variant_cache()
        if not self._probe_variant_controls(use_cache=not force_probe):
            self._log("[Debug] No variation controls on this listing.")
            return

        total = self._count_variant_listboxes()
        self._log(f"[Debug] Found {total} variant listbox(es) on this listing.")

        pw_selected = self._select_variants_via_playwright()
        legacy_selected = self._select_random_legacy_dropdowns()

        pending = self.get_pending_variants()
        if pending:
            self._log(f"[Warning] Variants still unselected: {pending}")
        elif pw_selected or legacy_selected:
            self._log(
                f"[Debug] Variants set via Playwright ({pw_selected}) and "
                f"legacy ({legacy_selected})."
            )

        self.dismiss_variant_overlay()
