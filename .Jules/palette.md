## 2026-06-26 - Accessibility improvements for form inputs and interactive elements
**Learning:** Bootstrap form-text helpers should be explicitly linked to their inputs using `aria-describedby`. Decorative icons like `▼` should be hidden from screen readers using `aria-hidden="true"`. Tooltip and label improvements (`aria-label` and `title`) are simple to add but greatly improve UX for log actions like Copy and Clear.
**Action:** Next time, ensure all form help text and purely decorative icons are appropriately tagged with ARIA attributes to enhance accessibility and usability.
## 2024-05-24 - Bootstrap Form-Switch Accessibility
**Learning:** Bootstrap `form-switch` checkboxes require an explicit `role="switch"` attribute. Without it, screen readers announce them as standard checkboxes instead of instant-toggling switches, which can confuse users expecting immediate UI changes.
**Action:** Always add `role="switch"` when implementing `form-switch` toggles in Bootstrap.
