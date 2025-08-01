# AGENTS.md

This file contains instructions for AI agents working on this codebase.

## 1. Project Overview

This project is a Flask application that syncs Meraki clients to a Pi-hole instance. It provides a web interface for viewing the sync status and history.

## 2. Development Setup

### Dependencies
*   **Backend:** `pip install -r requirements.txt` (or `poetry install`)

### Building and Running
*   **Build:** `docker-compose build`
*   **Run:** `docker-compose up --build -d`

## 3. Project Structure and Key Directories

*   `app/`: The root directory for the Flask application.
*   `app/clients/`: Contains clients for interacting with Meraki and Pi-hole APIs.
*   `app/static/`: Contains static assets such as CSS.
*   `app/templates/`: Contains Flask templates for the web application.
*   `tests/`: Contains tests for the application.
*   `scripts/`: Contains shell scripts for various tasks.
*   `terraform/`: Contains terraform configuration for infrastructure.

## 4. Build, Test, and Deployment Commands

*   **To install dependencies:** `poetry install`
*   **To run the application:** `poetry run python app/app.py`
*   **Run Tests:** `poetry run pytest`
*   All new features must be accompanied by unit tests.
*   Run the entire test suite before submitting code to ensure that no regressions have been introduced.

## 5. Debugging

*   **API Issues:** Check the application logs for errors. The logs are printed to standard output when running the application directly, or can be viewed with `docker-compose logs -f`.
*   **Docker Container Issues:** Use `docker-compose logs [service_name]` to retrieve logs.
*   **Docker Build Failures:** If a Docker build fails, consider rebuilding with more verbose output to inspect layers.

## 6. Coding Standards

### General
*   This project uses `ruff` for linting and formatting to ensure code quality and consistency. `ruff` is configured to replace the functionality of tools like `flake8` and `black`.
*   All code should be checked with `ruff` before committing.
*   The easiest way to ensure compliance is to use the pre-commit hooks provided in this repository. The hooks will automatically run `ruff` on any changed files before a commit is made.
*   Avoid using magic strings or numbers in the code. Define constants where appropriate.

### Pre-commit Hooks Setup
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

### Docstrings
*   All public functions and classes must have comprehensive docstrings using the Google Python Style Guide format.

## 7. Logging

*   The application uses the `logging` module to log messages.
*   Logging messages should be informative and include context, such as the function name and relevant variables.

## 8. Environment Variables

*   The application requires several environment variables to be set. These are defined in `.env.example`. Copy this file to `.env` and fill in the required values.

## 9. Input/Output Conventions

*   **API Responses:** API responses should be in JSON format.
*   **Commit Messages:** Commit messages should follow the conventional commit format.

## 10. Closed Loop Documentation

*   Agents must update any documentation as they make changes to code. This includes updating this `AGENTS.md` file when a new development or debugging technique is found, updating `REQUIREMENTS.md` when requirements are implemented, new bugs are found or new features are identified, and updating `README.md` when something from the design is updated.

## 11. Dependency Management

*   This project uses `poetry` to manage dependencies. The dependencies are listed in `pyproject.toml`.
*   Keep dependencies up-to-date. Consider using a tool like `dependabot` to automate this process.
