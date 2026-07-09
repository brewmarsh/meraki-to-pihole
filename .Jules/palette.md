## 2026-06-26 - Accessibility improvements for form inputs and interactive elements
**Learning:** Bootstrap form-text helpers should be explicitly linked to their inputs using `aria-describedby`. Decorative icons like `▼` should be hidden from screen readers using `aria-hidden="true"`. Tooltip and label improvements (`aria-label` and `title`) are simple to add but greatly improve UX for log actions like Copy and Clear.
**Action:** Next time, ensure all form help text and purely decorative icons are appropriately tagged with ARIA attributes to enhance accessibility and usability.

## 2024-03-24 - Accessibility for Chart.js canvas elements
**Learning:** Screen readers cannot interpret the visual data drawn on `<canvas>` elements by default, often reading them as empty or ignoring them. For data visualizations like Chart.js, adding `role="img"` and a descriptive `aria-label` provides crucial context to assistive technologies.
**Action:** Always add `role="img"` and descriptive `aria-label`s explaining what the chart represents when implementing canvas-based visualizations.
## 2023-10-27 - Accordion ARIA & Caret Synchronization
**Learning:** Manual `click` event listeners to toggle `aria-expanded` and caret states (`▲`/`▼`) on Bootstrap accordions can easily fall out of sync or be implemented backwards. In this case, the ARIA state was reversed, and the initial caret state in the HTML contradicted the actual expanded DOM state.
**Action:** Always prefer hooking into the UI framework's native lifecycle events (e.g., Bootstrap's `show.bs.collapse` and `hide.bs.collapse`) for visual and ARIA toggles rather than brittle manual DOM event listeners. Ensure initial HTML markup matches the default state of components.

## 2026-06-30 - Accessible Focus on Custom Overlays
**Learning:** When displaying custom overlay modals or screens (like `#welcome-screen`), keyboard users may not immediately understand context because focus remains on the underlying content behind the modal. The browser doesn't automatically move focus to dynamically shown elements unless they are native dialogs.
**Action:** Always ensure that when displaying custom overlays, the active focus is explicitly set via `.focus()` to the primary action or close button within the overlay.

## 2026-07-02 - Inline validation for non-form inputs
**Learning:** Native HTML5 validation attributes (like `min` and `max`) do not automatically prevent action when an input is used outside of a `<form>` submission context. In standalone inputs, JavaScript must explicitly check `.reportValidity()` before executing logic or making API calls, otherwise the browser allows invalid states to silently pass.
**Action:** Whenever using standalone inputs linked to buttons (e.g., input groups), always use `.reportValidity()` in the button click handler to trigger native browser validation tooltips and block invalid actions.

## 2026-07-04 - Programmatic ARIA Attribute Scoping
**Learning:** When using JavaScript to programmatically apply accessibility attributes (like `tabindex` and `role="button"`) to UI components using broad CSS classes (like `.card-header`), you risk applying them to static elements that should not be interactive. This creates confusing phantom buttons for screen readers and clutters the keyboard tab order.
**Action:** Always use specific attribute selectors (e.g., `[data-bs-toggle="collapse"]`) when programmatically attaching ARIA roles or keyboard event listeners to ensure they are only applied to genuinely interactive variants of a component.

## 2026-07-05 - Native form validation for standalone required inputs
**Learning:** When using standalone inputs (outside a `<form>` tag) that are required, simply adding the `required` attribute is highly effective when paired with `.reportValidity()` in the associated button's click handler. This blocks invalid empty submissions and leverages the browser's native, accessible validation tooltips without needing custom error UI.
**Action:** Always add the `required` attribute to mandatory standalone inputs and ensure their linked action buttons check `.reportValidity()` before executing logic or making API calls.

## 2026-07-07 - Visual Feedback for Drag and Drop operations
**Learning:** By default, libraries like Sortable.js handle the DOM reordering but provide little out-of-the-box visual feedback during the actual drag operation, which can leave users confused about where an element will drop.
**Action:** Always provide CSS styling for the `sortable-ghost` (or equivalent) class provided by drag-and-drop libraries to visually indicate the drop zone (e.g., using lowered opacity and dashed borders), and update the cursor states (`grab` and `grabbing`) on the drag handles to improve interaction clarity. Ensure these styles are tested in both light and dark modes.
## 2024-05-18 - Scoping interactive styles for dynamic vs static elements
**Learning:** Broad CSS selectors (like `.card-header`) often mix styling for elements intended to be interactive (like a collapsible card header) and elements intended to be static (like a static card header in a controls panel). Applying interactive properties (like `cursor: grab`, `:active`, `:focus-visible`) to a broad class results in misleading affordances for users on static components, which is confusing and an accessibility issue.
**Action:** When styling custom components that mix static and interactive variants, strictly scope interactive CSS properties to functional attributes (like `[data-bs-toggle="collapse"]`) to avoid unintentionally applying affordances to static elements.
