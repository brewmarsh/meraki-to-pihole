## 2026-06-24 - Add loading spinners to async buttons
**Learning:** The UI has multiple async buttons without visual feedback during API calls. Adding a disabled state and a spinner avoids double-clicks and makes the UI more reassuring.
**Action:** Apply this specific 'loading spinner to async submit button' pattern via `.finally()` in fetch wrappers to ensure buttons always become active again.
