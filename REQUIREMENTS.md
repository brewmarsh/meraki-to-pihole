# Requirements Document: Meraki Pi-hole DNS Sync

## 1. Functional Requirements

### 1.1. Core Functionality

*   **Meraki Client Synchronization:** The system shall synchronize client information from the Meraki API to a Pi-hole instance.
*   **Fixed IP Assignment:** The synchronization shall be limited to Meraki clients with Fixed IP Assignments (DHCP Reservations).
*   **Custom DNS Records:** The system shall create custom DNS records in Pi-hole for the identified Meraki clients.
*   **Configurable Interval:** The synchronization process shall run at a configurable interval.

### 1.2. Configuration

*   **Environment Variables:** All configuration shall be managed via environment variables.
*   **Meraki API Key:** The system shall require a Meraki API key for authentication.
*   **Meraki Organization ID:** The system shall require a Meraki Organization ID to identify the target organization.
*   **Pi-hole API URL:** The system shall require the URL of the Pi-hole API endpoint.
*   **Pi-hole API Key:** The system shall support authentication with a Pi-hole API key.
*   **Hostname Suffix:** The system shall use a configurable hostname suffix for the DNS records.
*   **Network IDs:** The system shall allow specifying a list of Meraki Network IDs to sync. If not provided, all networks in the organization will be queried.
*   **Client Timespan:** The system shall allow configuring the timespan for fetching Meraki clients.
*   **Configuration Validation:** Use Pydantic to manage and validate application settings from environment variables.

### 1.3. Web UI

*   **View Mappings:** The Web UI shall display the current custom DNS mappings in Pi-hole.
*   **Force Sync:** The Web UI shall provide a button to manually trigger a synchronization.
*   **View Logs:** The Web UI shall display the application logs in real-time.
*   **Update Sync Interval:** The Web UI shall allow updating the sync interval on the fly.
*   **Clear Logs:** The Web UI shall provide a button to clear the log file.
*   **Framework:** The Web UI shall be built with FastAPI. (Completed)

### 1.4. API

*   **Health Check Endpoint:** Add a dedicated health check endpoint that can be used by monitoring services to verify the application's status.

## 2. Non-Functional Requirements

### 2.1. Reliability

*   **Error Handling:** The system shall handle API errors gracefully and log them appropriately.
*   **Retry Mechanism:** The system shall implement a retry mechanism for transient API errors.
*   **Idempotency:** The synchronization process shall be idempotent, meaning that multiple runs with the same input will produce the same result.
*   **User-Friendly Error Pages:** Create custom, user-friendly error pages for common HTTP errors (e.g., 404 Not Found, 500 Internal Server Error).
*   **Centralized Error Handling:** Implement centralized error handling middleware in FastAPI to ensure consistent error responses.

### 2.2. Quality

*   **Code Quality:** The code shall be well-structured, documented, and maintainable.
*   **Testing:** The system shall have a comprehensive suite of unit tests to ensure correctness.
*   **Logging:** The system shall provide detailed logs for debugging and monitoring purposes.
*   **Structured Logging:** Implement structured logging (e.g., in JSON format) to make logs more easily searchable and machine-readable.
*   **Security:** The system shall securely handle API keys and other sensitive information.
*   **Code Style:** The codebase shall adhere to the PEP 8 style guide for Python code.
*   **Static Analysis:** The CI/CD pipeline shall enforce code quality standards through automated linting and static analysis using tools like `ruff`, `bandit`, and `mypy`.
*   **Strict Type Checking:** Enforce strict type checking across the entire codebase using `mypy` to catch type-related errors before runtime.

### 2.3. Performance

*   **Efficient API Usage:** The system shall use the Meraki and Pi-hole APIs efficiently to minimize the number of requests.
*   **Scalability:** The system shall be able to handle a large number of Meraki clients and networks.
*   **Concurrency:** The application shall be able to handle a high volume of concurrent connections without significant degradation in performance.

### 2.4. Usability and Look & Feel

*   **Web UI Design:** The Web UI shall have a clean, modern, and intuitive design that is easy for users to navigate.
*   **Clarity:** The Web UI shall provide a clear and concise overview of the system's status and data.

### 2.5. Security

*   **Input Validation:** Rigorously validate and sanitize all user-supplied data to prevent injection attacks.
*   **Secure Headers:** Implement security headers like `X-Content-Type-Options`, `X-Frame-Options`, and `Strict-Transport-Security`.
*   **Content Security Policy (CSP):** Implement a strict CSP to mitigate XSS and other injection attacks.
*   **Rate Limiting:** Apply rate limiting to API endpoints to prevent abuse and denial-of-service attacks.
*   **Container Security:** Ensure the Docker container runs as a non-root user to reduce the potential impact of a container breakout vulnerability.

## 3. Build, CI/CD, and Deployment

*   **Containerization:** The application shall be containerized using Docker. (Completed)
*   **Multi-stage Docker Builds:** Implemented multi-stage Docker builds to reduce the size of the final image. (Completed)
*   **Dockerfile Linting:** Add a step to the CI/CD pipeline to lint the `Dockerfile` for best practices and potential security issues (e.g., using `hadolint`).
*   **Local Development:** The project shall provide a `docker-compose.yml` file for easy local development and testing. (Completed)
*   **Dependency Management:** Switched to Poetry for dependency management to ensure reproducible builds. (Completed)
*   **Code Quality:** The project shall use pre-commit hooks to enforce code quality standards.
*   **Linting and Static Analysis:** The project shall use `ruff` for linting and code formatting.
*   **CI/CD Pipeline:** Implemented a CI/CD pipeline using GitHub Actions to automate testing. (Completed)
*   **Semantic Versioning:** Automated semantic versioning based on commit messages using a GitHub Action. (Completed)
*   **Automated Releases:** Set up an automated release process to publish new versions to a package repository (e.g., PyPI) and/or a container registry (e.g., Docker Hub).
*   **Release Notes Generation:** Automate the generation of release notes from commit messages.
*   **Security Scanning:** Integrated Trivy into the CI/CD pipeline to scan for vulnerabilities. (Completed)
*   **Dependency Vulnerability Scanning:** Automatically scan dependencies for known vulnerabilities (e.g., using `pip-audit` or GitHub's Dependabot).
*   **Test Coverage Reporting:** Integrate a tool like `codecov` or `coveralls` to track test coverage over time and enforce a minimum coverage threshold.
*   **Infrastructure as Code:** Used Terraform to manage the deployment infrastructure. (Completed)

## 4. Documentation

*   **API Documentation:** Automatically generate interactive API documentation using FastAPI's built-in support for OpenAPI (Swagger UI and ReDoc).
*   **Architectural Overview:** Create a document that provides a high-level overview of the application's architecture.
*   **Deployment Guide:** Write a comprehensive guide that details the steps for deploying the application to a production environment.
*   **Contribution Guidelines:** Establish clear guidelines for contributing to the project, including code style, commit message formats, and the pull request process.
