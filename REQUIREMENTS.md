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

### 1.3. Web UI

*   **View Mappings:** The Web UI shall display the current custom DNS mappings in Pi-hole.
*   **Force Sync:** The Web UI shall provide a button to manually trigger a synchronization.
*   **View Logs:** The Web UI shall display the application logs in real-time.
*   **Update Sync Interval:** The Web UI shall allow updating the sync interval on the fly.
*   **Clear Logs:** The Web UI shall provide a button to clear the log file.

## 2. Non-Functional Requirements

### 2.1. Reliability

*   **Error Handling:** The system shall handle API errors gracefully and log them appropriately.
*   **Retry Mechanism:** The system shall implement a retry mechanism for transient API errors.
*   **Idempotency:** The synchronization process shall be idempotent, meaning that multiple runs with the same input will produce the same result.

### 2.2. Quality

*   **Code Quality:** The code shall be well-structured, documented, and maintainable.
*   **Testing:** The system shall have a comprehensive suite of unit tests to ensure correctness.
*   **Logging:** The system shall provide detailed logs for debugging and monitoring purposes.
*   **Security:** The system shall securely handle API keys and other sensitive information.

### 2.3. Performance

*   **Efficient API Usage:** The system shall use the Meraki and Pi-hole APIs efficiently to minimize the number of requests.
*   **Scalability:** The system shall be able to handle a large number of Meraki clients and networks.

## 3. Build and CI/CD

*   **Containerization:** The application shall be containerized using Docker.
*   **Local Development:** The project shall provide a `docker-compose.yml` file for easy local development and testing.
*   **Code Quality:** The project shall use pre-commit hooks to enforce code quality standards.
*   **Linting and Static Analysis:** The project shall use `ruff` for linting and code formatting.

## 4. Completed

*   **CI/CD Pipeline:** Implemented a CI/CD pipeline using GitHub Actions to automate testing.
*   **Semantic Versioning:** Automated semantic versioning based on commit messages using a GitHub Action.
*   **Dependency Management:** Switched to Poetry for dependency management to ensure reproducible builds.
*   **Multi-stage Docker Builds:** Implemented multi-stage Docker builds to reduce the size of the final image.
*   **Security Scanning:** Integrated Trivy into the CI/CD pipeline to scan for vulnerabilities.
*   **Infrastructure as Code:** Used Terraform to manage the deployment infrastructure.
