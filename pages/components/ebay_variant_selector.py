import random
import re
import config
from playwright.sync_api import Page, Locator
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
        self._variant_error_text = re.compile(
            r"please select|select a|select an|mandatory|before you can|"
            r"choose a|out of stock.*select",
            re.IGNORECASE,
        )
        self._variant_controls_cached: bool | None = None

    def _selection_applied(self, button: Locator) -> bool:
        text = (button.text_content() or "").strip()
        value = (button.get_attribute("value") or "").strip()
        return not label_needs_selection(text, value)

    def _get_listbox_panel(self, button: Locator) -> Locator:
        controls_id = button.get_attribute("aria-controls")
        if controls_id:
            return self.page.locator(f"#{controls_id}")
        container = button.locator(
            "xpath=ancestor::div[contains(@class,'listbox-button')][1]"
        )
        panel = container.locator("[role='listbox']")
        if panel.count() > 0:
            return panel.first
        return self.page.locator(f"{self._sku_section} [role='listbox']").first

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
        return bool(
            self.page.evaluate(
                """() => {
                    if (document.querySelector(
                        '[data-testid="x-msku"], .x-msku, .x-sku, #msku-variation'
                    )) {
                        return true;
                    }
                    const text = (document.body?.innerText || '').slice(0, 8000);
                    return /:\\s*select\\b/i.test(text);
                }"""
            )
        )

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

    def _has_variant_controls(self) -> bool:
        return self._probe_variant_controls(use_cache=True)

    def _is_feedback_listbox(self, button: Locator) -> bool:
        container = button.locator(
            "xpath=ancestor::div[contains(@class,'listbox-button')][1]"
        )
        native = container.locator("select.listbox__native")
        if native.count() == 0:
            return False
        name = (native.get_attribute("name") or "").lower()
        return "feedback" in name

    def list_variation_buttons(self) -> list[Locator]:
        """All SKU/MSKU listbox pickers (eBay may use 2+ x-sku blocks and 3+ variants)."""
        buttons = self.page.locator(self._variation_listbox_buttons)
        variation_buttons = []
        for i in range(buttons.count()):
            button = buttons.nth(i)
            if self._is_feedback_listbox(button):
                continue
            variation_buttons.append(button)
        return variation_buttons

    def count_variant_listboxes(self) -> int:
        return len(self.list_variation_buttons())

    def get_pending_variants_via_js(self) -> list[str]:
        return self.page.evaluate(
            """() => {
                const needs = (text, val) => {
                    const t = (text || '').replace(/\\s+/g, ' ').trim();
                    if ((val || '').toLowerCase() === 'select') return true;
                    if (/:\\s*select\\s*$/i.test(t)) return true;
                    if (t.toLowerCase() === 'select') return true;
                    return false;
                };
                const sel =
                    'div.vim.x-sku .listbox-button button.listbox-button__control, '
                    + 'div.x-sku .listbox-button button.listbox-button__control, '
                    + 'div.vim.x-msku .listbox-button button.listbox-button__control, '
                    + 'div.x-msku-evo .listbox-button button.listbox-button__control';
                return [...document.querySelectorAll(sel)]
                    .filter((btn) => {
                        const name = btn.closest('.listbox-button')
                            ?.querySelector('select.listbox__native')?.getAttribute('name') || '';
                        return !name.toLowerCase().includes('feedback');
                    })
                    .map((btn) => btn.textContent.trim())
                    .filter((t) => needs(t, ''));
            }"""
        )

    def get_pending_variants(self) -> list[str]:
        pending = []
        for button in self.list_variation_buttons():
            text = (button.text_content() or "").strip()
            value = (button.get_attribute("value") or "").strip()
            if label_needs_selection(text, value):
                pending.append(text)
        return pending

    def _get_pending_variant_targets(self) -> list[dict]:
        return self.page.evaluate(
            """() => {
                const needs = (text, val) => {
                    const t = (text || '').replace(/\\s+/g, ' ').trim();
                    if ((val || '').toLowerCase() === 'select') return true;
                    if (/:\\s*select\\s*$/i.test(t)) return true;
                    if (t.toLowerCase() === 'select') return true;
                    return false;
                };
                const sel =
                    'div.vim.x-sku .listbox-button button.listbox-button__control, '
                    + 'div.x-sku .listbox-button button.listbox-button__control, '
                    + 'div.vim.x-msku .listbox-button button.listbox-button__control, '
                    + 'div.x-msku-evo .listbox-button button.listbox-button__control';
                return [...document.querySelectorAll(sel)]
                    .filter((btn) => {
                        const name = btn.closest('.listbox-button')
                            ?.querySelector('select.listbox__native')?.getAttribute('name') || '';
                        return !name.toLowerCase().includes('feedback');
                    })
                    .map((btn) => ({
                        text: btn.textContent.trim(),
                        value: btn.getAttribute('value') || '',
                        controls: btn.getAttribute('aria-controls'),
                        needs: needs(btn.textContent, btn.getAttribute('value')),
                    }))
                    .filter((b) => b.needs && b.controls);
            }"""
        )

    def _get_listbox_panel_for_button(self, button: Locator) -> Locator | None:
        controls_id = button.get_attribute("aria-controls")
        if not controls_id:
            return None
        panel = self.page.locator(f"#{controls_id}")
        return panel if panel.count() > 0 else None

    def _listbox_is_open(self, button: Locator, panel: Locator | None) -> bool:
        if button.get_attribute("aria-expanded") == "true":
            return True
        if panel is None:
            return False
        try:
            if panel.is_visible():
                return True
        except Exception:
            pass
        return (
            panel.locator(
                "[role='option']:visible, .listbox__option:visible"
            ).count()
            > 0
        )

    def _open_listbox(self, button: Locator) -> bool:
        panel = self._get_listbox_panel_for_button(button)
        button.scroll_into_view_if_needed()
        button.click(timeout=config.DEFAULT_TIMEOUT)

        for _ in range(30):
            if self._listbox_is_open(button, panel):
                return True
            self.page.wait_for_timeout(100)

        if self._listbox_is_open(button, panel):
            return True

        button.click(timeout=config.DEFAULT_TIMEOUT)
        for _ in range(15):
            if self._listbox_is_open(button, panel):
                return True
            self.page.wait_for_timeout(100)
        return self._listbox_is_open(button, panel)

    def _select_variant_playwright(self, controls_id: str, label: str) -> bool:
        button = self.page.locator(
            f"button.listbox-button__control[aria-controls='{controls_id}']"
        )
        if button.count() == 0:
            self._log(f"[Debug] Listbox '{label}': button not found for panel #{controls_id}")
            return False

        button = button.first
        single_variant = self.count_variant_listboxes() == 1

        if not single_variant and self._select_via_native_select(button, label):
            return True

        if not single_variant:
            self._close_open_listboxes()
            self.page.wait_for_timeout(300)

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
            self._log(f"[Debug] Listbox '{label}': no visible options in panel #{controls_id}")
            self._close_open_listboxes()
            return False

        random.shuffle(valid)
        for option, choice in valid:
            self._log(f"[Debug] Listbox '{label}': selecting '{choice}' (Playwright)")
            if self._activate_listbox_option(button, controls_id, option, choice):
                applied = (button.text_content() or "").strip()
                self._log(f"[Debug] Listbox '{label}': applied -> '{applied}'")
                self._close_open_listboxes()
                self.page.wait_for_timeout(400)
                return True

        self._close_open_listboxes()
        self._log(f"[Debug] Listbox '{label}': option click did not apply")
        return False

    def _select_variant_js(self, controls_id: str, label: str) -> bool:
        applied = self.page.evaluate(
            """({ controlsId }) => {
                const needs = (text, val) => {
                    if ((val || '').toLowerCase() === 'select') return true;
                    return /:\\s*select\\s*$/i.test((text || '').replace(/\\s+/g, ' ').trim());
                };
                const sel =
                    'div.vim.x-sku .listbox-button button.listbox-button__control, '
                    + 'div.x-sku .listbox-button button.listbox-button__control, '
                    + 'div.vim.x-msku .listbox-button button.listbox-button__control, '
                    + 'div.x-msku-evo .listbox-button button.listbox-button__control';
                const btn = [...document.querySelectorAll(sel)]
                    .find((b) => b.getAttribute('aria-controls') === controlsId);
                if (!btn) return { ok: false, reason: 'button_not_found' };

                btn.click();
                const panel = document.getElementById(controlsId);
                const panelOpen = () => {
                    if (!panel) return false;
                    if (btn.getAttribute('aria-expanded') === 'true') return true;
                    const vis = [...panel.querySelectorAll('[role="option"], .listbox__option')]
                        .filter((o) => o.offsetParent !== null);
                    return vis.length > 0;
                };
                if (!panelOpen()) btn.click();
                if (!panelOpen()) return { ok: false, reason: 'panel_not_open' };

                if (!panel) return { ok: false, reason: 'panel_not_found' };

                const opts = [...panel.querySelectorAll('[role="option"], .listbox__option')]
                    .filter((o) => o.offsetParent !== null);
                const valid = opts
                    .map((o, j) => ({
                        j,
                        t: o.textContent.trim().replace(/selected$/i, '').trim(),
                    }))
                    .filter(
                        (x) =>
                            x.t &&
                            !/^select/i.test(x.t) &&
                            !/out of stock/i.test(x.t) &&
                            !/rating/i.test(x.t)
                    );
                if (!valid.length) return { ok: false, reason: 'no_valid_options' };

                const pick = valid[Math.floor(Math.random() * valid.length)];
                const target = opts[pick.j];
                target.dispatchEvent(
                    new MouseEvent('mousedown', { bubbles: true, cancelable: true })
                );
                target.dispatchEvent(
                    new MouseEvent('mouseup', { bubbles: true, cancelable: true })
                );
                target.click();

                const native = btn
                    .closest('.listbox-button')
                    ?.querySelector('select.listbox__native');
                if (native) {
                    for (const opt of native.options) {
                        const label = opt.textContent.trim().replace(/selected$/i, '').trim();
                        if (label === pick.t || label.includes(pick.t)) {
                            native.value = opt.value;
                            native.dispatchEvent(new Event('input', { bubbles: true }));
                            native.dispatchEvent(new Event('change', { bubbles: true }));
                            break;
                        }
                    }
                }

                return {
                    ok: !needs(btn.textContent, btn.getAttribute('value')),
                    picked: pick.t,
                    after: btn.textContent.trim(),
                };
            }""",
            {"controlsId": controls_id},
        )
        if applied.get("ok"):
            self._log(
                f"[Debug] Listbox '{label}' -> '{applied.get('after')}' "
                f"(JS, picked {applied.get('picked')})"
            )
            self._close_open_listboxes()
            self.page.wait_for_timeout(400)
            return True
        return False

    def _select_variants_via_js(self) -> int:
        selected = 0
        max_rounds = max(10, self.count_variant_listboxes() * 3)

        for round_num in range(1, max_rounds + 1):
            pending = self._get_pending_variant_targets()
            if not pending:
                break

            pending.sort(key=lambda b: variant_sort_key(b["text"]))
            self._log(
                f"[Debug] Variant round {round_num}: "
                f"{len(pending)} unselected — {[p['text'] for p in pending]}"
            )

            for target in pending:
                label = target["text"]
                controls_id = target["controls"]
                if self._select_variant_playwright(controls_id, label):
                    selected += 1
                    continue
                if self._select_variant_js(controls_id, label):
                    selected += 1

        return selected

    def _close_open_listboxes(self):
        self.page.keyboard.press("Escape")
        expanded = self.page.locator(
            f"{self._sku_section} button.listbox-button__control[aria-expanded='true']"
        )
        for i in range(expanded.count()):
            try:
                expanded.nth(i).click(timeout=2000)
            except Exception:
                pass

    def _collect_valid_listbox_options(self, listbox: Locator) -> list[tuple[Locator, str]]:
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

    def _sync_listbox_selection_js(self, controls_id: str, choice: str) -> bool:
        return bool(
            self.page.evaluate(
                """({ controlsId, choiceText }) => {
                    const norm = (t) =>
                        (t || '')
                            .replace(/\\s+/g, ' ')
                            .trim()
                            .replace(/selected$/i, '')
                            .trim();
                    const needs = (text, val) => {
                        if ((val || '').toLowerCase() === 'select') return true;
                        return /:\\s*select\\s*$/i.test(norm(text));
                    };
                    const btn = document.querySelector(
                        `button.listbox-button__control[aria-controls="${controlsId}"]`
                    );
                    const panel = document.getElementById(controlsId);
                    if (!btn || !panel) return false;

                    if (btn.getAttribute('aria-expanded') !== 'true') {
                        btn.click();
                    }

                    const want = norm(choiceText);
                    const opts = [...panel.querySelectorAll('[role="option"], .listbox__option')]
                        .filter((o) => o.offsetParent !== null);
                    const target =
                        opts.find((o) => norm(o.textContent) === want) ||
                        opts.find((o) => norm(o.textContent).includes(want));

                    if (!target) return false;

                    target.dispatchEvent(
                        new MouseEvent('mousedown', { bubbles: true, cancelable: true })
                    );
                    target.dispatchEvent(
                        new MouseEvent('mouseup', { bubbles: true, cancelable: true })
                    );
                    target.click();

                    const native = btn
                        .closest('.listbox-button')
                        ?.querySelector('select.listbox__native');
                    if (native) {
                        for (const opt of native.options) {
                            const label = norm(opt.textContent);
                            if (label === want || label.includes(want)) {
                                native.value = opt.value;
                                native.dispatchEvent(new Event('input', { bubbles: true }));
                                native.dispatchEvent(new Event('change', { bubbles: true }));
                                break;
                            }
                        }
                    }

                    return !needs(btn.textContent, btn.getAttribute('value'));
                }""",
                {"controlsId": controls_id, "choiceText": choice},
            )
        )

    def _activate_listbox_option(
        self,
        button: Locator,
        controls_id: str,
        option: Locator,
        choice: str,
    ) -> bool:
        click_targets = [
            option,
            option.locator(".listbox__option").first,
        ]
        for target in click_targets:
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
            self.page.wait_for_timeout(350)
            if self._selection_applied(button):
                return True

        if self._sync_listbox_selection_js(controls_id, choice):
            self.page.wait_for_timeout(350)
            return self._selection_applied(button)

        return False

    def _select_via_listbox_ui(self, button: Locator, label: str) -> bool:
        listbox = self._get_listbox_panel(button)
        controls_id = button.get_attribute("aria-controls") or ""

        if self.count_variant_listboxes() > 1:
            self._close_open_listboxes()
            self.page.wait_for_timeout(300)

        if not self._open_listbox(button):
            return False

        valid = self._collect_valid_listbox_options(listbox)
        if not valid:
            self._log(f"[Debug] Listbox '{label}': no options in panel #{button.get_attribute('aria-controls')}.")
            self._close_open_listboxes()
            return False

        random.shuffle(valid)
        for option, choice in valid:
            self._log(f"[Debug] Listbox '{label}': selecting '{choice}'")
            if controls_id and self._activate_listbox_option(
                button, controls_id, option, choice
            ):
                applied = (button.text_content() or "").strip()
                self._log(f"[Debug] Listbox '{label}': applied -> '{applied}'")
                self._close_open_listboxes()
                return True

        self._close_open_listboxes()
        self._log(f"[Debug] Listbox '{label}': UI click did not apply.")
        return False

    def _select_via_native_select(self, button: Locator, label: str) -> bool:
        container = button.locator(
            "xpath=ancestor::div[contains(@class,'listbox-button')][1]"
        )
        native = container.locator("select.listbox__native")
        if native.count() == 0:
            return False

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
            if self._selection_applied(button):
                self._close_open_listboxes()
                return True
            self.page.wait_for_timeout(200)

        controls_id = button.get_attribute("aria-controls") or ""
        option_text = normalize_option_text(
            options.nth(idx).text_content() or ""
        )
        if controls_id and option_text and self._sync_listbox_selection_js(
            controls_id, option_text
        ):
            self.page.wait_for_timeout(350)
            if self._selection_applied(button):
                self._close_open_listboxes()
                return True

        self._close_open_listboxes()
        return False

    def _select_random_listbox_option(self, button: Locator, label: str) -> bool:
        value = (button.get_attribute("value") or "").strip()
        if not label_needs_selection(label, value):
            self._log(f"[Debug] Listbox '{label}' already has a value, skipping.")
            return False

        single_variant = self.count_variant_listboxes() == 1
        strategies = (
            (self._select_via_listbox_ui, self._select_via_native_select)
            if single_variant
            else (self._select_via_listbox_ui, self._select_via_native_select)
        )

        for attempt in range(2):
            for strategy in strategies:
                if strategy(button, label):
                    return True
            self._log(f"[Debug] Listbox '{label}': retry {attempt + 2}/2")
        return False

    def _select_random_legacy_dropdowns(self) -> int:
        dropdowns = self.page.locator(self._legacy_variation_dropdowns)
        selected = 0
        for i in range(dropdowns.count()):
            dropdown = dropdowns.nth(i)
            options = dropdown.locator("option").all_text_contents()
            valid_options = [
                opt.strip()
                for opt in options
                if is_valid_variant_option(opt)
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

        total = self.count_variant_listboxes()
        self._log(f"[Debug] Found {total} variant listbox(es) on this listing.")

        js_selected = self._select_variants_via_js()
        legacy_selected = self._select_random_legacy_dropdowns()

        pending = self.get_pending_variants()
        js_pending = self.get_pending_variants_via_js()
        if js_pending and not pending:
            pending = js_pending
        if pending:
            self._log(f"[Warning] Variants still unselected after JS: {pending}")
            for button in self.list_variation_buttons():
                label = (button.text_content() or "").strip()
                if label_needs_selection(
                    label, (button.get_attribute("value") or "").strip()
                ):
                    self._close_open_listboxes()
                    self._select_random_listbox_option(button, label)
            pending = self.get_pending_variants()
            if pending:
                self._log(f"[Warning] Variants still unselected: {pending}")
        elif js_selected or legacy_selected:
            self._log(
                f"[Debug] Variants set via JS ({js_selected}) and "
                f"legacy ({legacy_selected})."
            )
