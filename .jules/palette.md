
## 2024-05-26 - Add visual feedback to copy buttons
**Learning:** Clipboard copy actions without immediate, localized visual feedback can leave users unsure if the action succeeded, especially for keyboard/screen-reader users where global toasts might be missed or distracting.
**Action:** When implementing copy-to-clipboard functionality, temporarily change the button's text, visual style (e.g., success state), and ARIA label to provide immediate, localized confirmation before reverting to the original state.
