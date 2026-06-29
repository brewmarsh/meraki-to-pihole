## 2026-06-26 - Accessibility improvements for form inputs and interactive elements
**Learning:** Bootstrap form-text helpers should be explicitly linked to their inputs using `aria-describedby`. Decorative icons like `▼` should be hidden from screen readers using `aria-hidden="true"`. Tooltip and label improvements (`aria-label` and `title`) are simple to add but greatly improve UX for log actions like Copy and Clear.
**Action:** Next time, ensure all form help text and purely decorative icons are appropriately tagged with ARIA attributes to enhance accessibility and usability.

## 2024-03-24 - Accessibility for Chart.js canvas elements
**Learning:** Screen readers cannot interpret the visual data drawn on `<canvas>` elements by default, often reading them as empty or ignoring them. For data visualizations like Chart.js, adding `role="img"` and a descriptive `aria-label` provides crucial context to assistive technologies.
**Action:** Always add `role="img"` and descriptive `aria-label`s explaining what the chart represents when implementing canvas-based visualizations.
## 2023-10-27 - Accordion ARIA & Caret Synchronization
**Learning:** Manual `click` event listeners to toggle `aria-expanded` and caret states (`▲`/`▼`) on Bootstrap accordions can easily fall out of sync or be implemented backwards. In this case, the ARIA state was reversed, and the initial caret state in the HTML contradicted the actual expanded DOM state.
**Action:** Always prefer hooking into the UI framework's native lifecycle events (e.g., Bootstrap's `show.bs.collapse` and `hide.bs.collapse`) for visual and ARIA toggles rather than brittle manual DOM event listeners. Ensure initial HTML markup matches the default state of components.
