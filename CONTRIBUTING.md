# Contributing to Meraki-to-Pihole

Thank you for contributing! This document provides the guidelines for setting up your development environment and submitting changes.

**Please also read the `AGENTS.md` file** for rules on branch naming, commit messages, and general coding standards that apply to all repositories in this organization.

## Development Setup

This project uses [Poetry](https://python-poetry.org/) for dependency and environment management.

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/brewmarsh/meraki-to-pihole.git](https://github.com/brewmarsh/meraki-to-pihole.git)
    cd meraki-to-pihole
    ```
2.  **Install Poetry:**
    ```bash
    pip install poetry
    ```
3.  **Install Pre-commit:**
    We use `pre-commit` to ensure code quality before every commit.
    ```bash
    pip install pre-commit
    pre-commit install
    ```
4.  **Install Dependencies:**
    This command will create a virtual environment and install all required packages.
    ```bash
    poetry install
    ```

## Code Style & Quality

This project uses **Ruff** for all linting and formatting (replacing Black, Flake8, and isort).

The `pre-commit` hooks will run these checks automatically on any changed files. You can also run them manually:

* **Check for all issues (lint + format):**
    ```bash
    poetry run ruff check .
    ```
* **Fix all auto-fixable issues (lint + format):**
    ```bash
    poetry run ruff check . --fix
    ```
* **Just format code:**
    ```bash
    poetry run ruff format .
    ```

## Running Tests

You can run the full test suite using `pytest`:

```bash
poetry run pytest
````

## Pull Request Process

1.  Create a feature branch following the naming conventions in `AGENTS.md` (e.g., `feature/my-new-feature`).
2.  Make your changes and add tests.
3.  Ensure all tests pass (`poetry run pytest`).
4.  Ensure your code is formatted and linted (`poetry run ruff check . --fix`).
5.  Commit your changes using the Conventional Commits format (see `AGENTS.md`).
6.  Submit a Pull Request to the `main` branch.

<!-- end list -->

```
```
