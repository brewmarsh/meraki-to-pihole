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

## 2024-05-14 - Scoping Interactive Visual Affordances
**Learning:** Applying interactive CSS properties (like `cursor: grab`, `:active`, or `:focus-visible`) to broad structural classes (like `.card-header`) often leads to static elements receiving misleading visual affordances, confusing users about what is actually interactive.
**Action:** Always scope interactive visual affordances in CSS to functional HTML attributes (e.g., `[data-bs-toggle="collapse"]` or `[role="button"]`) rather than structural classes, ensuring only genuinely interactive variants of a component look interactive.

## 2024-07-12 - Accessible Visual Indicators for Required Form Fields
**Learning:** When using standard `required` HTML attributes on form fields, users—and especially screen reader users—need clear indication *before* submission that the field is mandatory. A red asterisk is a common visual convention, but screen readers may mispronounce or ignore it if not tagged correctly.
**Action:** Always wrap visual indicators like asterisks with `aria-hidden="true"` and supplement them with explicit `<span class="visually-hidden"> (required)</span>` text within the `<label>` to ensure both sighted and screen-reader users understand the requirement.

## 2026-07-28 - Custom Modal Overlay Close Mechanisms and Accessibility
**Learning:** When building custom modal overlays without native `<dialog>` or framework components (like Bootstrap `.modal`), always implement explicit event listeners for the `Escape` key and background (backdrop) clicks, and include standard ARIA attributes (`role="dialog"`, `aria-modal="true"`, and `aria-labelledby`) to ensure proper accessibility and screen reader support. Additionally, ensure event listeners correctly account for conditional rendering (like Jinja `{% if %}` blocks) to prevent `TypeError` exceptions on elements that might not exist in the DOM.
**Action:** Always add standard ARIA attributes and robust close handlers (Escape, click outside) for custom modal implementations, ensuring these scripts check for element existence if the HTML is conditionally rendered.

## 2026-07-26 - Accessible Scrollable Regions
**Learning:** Elements with scrollable overflow (like `<pre class="log-box">`) are not natively focusable by default, meaning keyboard-only users cannot scroll their content using arrow keys.
**Action:** Always add `tabindex="0"` to visually scrollable regions and include a visible `:focus-visible` outline for sighted keyboard users to ensure they are fully accessible and usable.

## 2024-08-04 - Skip to main content links
**Learning:** When implementing a 'Skip to main content' link for keyboard accessibility, it must be placed at the top of the body using Bootstrap's 'visually-hidden-focusable' class and ensure it targets a focusable '<main>' container with 'tabindex="-1"' and 'outline: none;'.
**Action:** Always include a 'Skip to main content' link that targets a focusable main container when modifying layout templates, to enable keyboard users to bypass repetitive navigation elements.
