## 2026-06-24 - Add loading spinners to async buttons
**Learning:** The UI has multiple async buttons without visual feedback during API calls. Adding a disabled state and a spinner avoids double-clicks and makes the UI more reassuring.
**Action:** Apply this specific 'loading spinner to async submit button' pattern via `.finally()` in fetch wrappers to ensure buttons always become active again.
## 2026-06-25 - Adding keyboard support to div-based Bootstrap collapse toggles
**Learning:** The UI used standard `div` elements as Bootstrap collapse toggles. While this works with mouse clicks, standard `div`s aren't focusable and don't respond to keyboard events. Also missing ARIA states makes screen readers unable to announce them correctly.
**Action:** When using `div`s for toggles instead of `<button>`, always explicitly add `tabindex="0"`, `role="button"`, `aria-expanded`, and `aria-controls`. Furthermore, ensure you add explicit `keydown` event listeners to handle `Enter` and `Space` to replicate native button behavior.
