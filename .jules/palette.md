## 2024-05-24 - Skip to Content Links Need Focus Outlines Disabled

**Learning:** When adding a "Skip to main content" link that targets a container (like `<main>`) and programmatic focus is shifted there, it creates an unsightly focus ring on the entire container if `tabindex="-1"` is used alone. Setting `style="outline: none;"` is required alongside `tabindex="-1"` so the programmatic focus can shift without a jarring visual artifact.

**Action:** Always pair `tabindex="-1"` with `style="outline: none;"` on the target container when implementing skip links.
