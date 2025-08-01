# AGENTS.md

This file contains instructions for AI agents working on this codebase.

## Code Quality

This project uses `ruff` for linting and formatting to ensure code quality and consistency. `ruff` is configured to replace the functionality of tools like `flake8` and `black`.

All code should be checked with `ruff` before committing.

### Pre-commit Hooks

The easiest way to ensure compliance is to use the pre-commit hooks provided in this repository. The hooks will automatically run `ruff` on any changed files before a commit is made.

To set up the pre-commit hooks, follow these steps:

1.  Install `pre-commit` if you haven't already:
    ```bash
    pip install pre-commit
    ```
2.  Install the git hooks:
    ```bash
    pre-commit install
    ```

After installation, the hooks will run automatically on `git commit`. You can also run them manually on all files:

```bash
pre-commit run --all-files
```
