## 2024-11-10 - Dynamic ARIA Label Restoration
**Learning:** Modifying DOM attributes (like `aria-label`) for temporary UI feedback can break accessibility if the original state was `null`, since reverting by setting to literal `'null'` creates an invalid attribute state.
**Action:** Always capture the original attribute state using `getAttribute()`. If the original state was `null`, use `removeAttribute()` during the revert instead of `setAttribute('aria-label', originalAria)`.
