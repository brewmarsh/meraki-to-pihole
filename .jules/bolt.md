## 2025-02-12 - O(N*M) nested loop found in `map_devices`
**Learning:** Found an O(N*M) nested loop in `map_devices` (`app/sync_logic.py`) that matches a client's IP with a domain from a dict of IP to domain mappings.
**Action:** The old function loops over the clients, and for each client it checks if the client IP is in a set of IP addresses. If it is, it loops over all the pihole records to find the domain. By building an inverse dictionary `ip_to_domains` upfront, we can look up the matching domains in O(1) time and eliminate the inner loop.

## 2025-02-13 - O(N*M) nested loop found in `_map_devices` endpoint
**Learning:** Found an O(N*M) nested loop in `_map_devices` (`app/app.py`) that maps Meraki clients to Pi-hole records. This caused slow API responses for endpoints like `/mappings` and `/stream`.
**Action:** Replaced the inner loop with an O(1) dictionary lookup by pre-computing `ip_to_domains`. This brought a synthetic test of 5000 clients and 2000 records from ~0.624s down to ~0.016s.
## 2025-01-26 - Prevent N+1 queries in loop
**Learning:** Found an N+1 query problem in loop fetching Pi-hole custom DNS records when processing each Meraki client.
**Action:** When working with API or DB clients, verify if functions fetching records inside loops can accept a pre-fetched records dict as an optional arg.
## 2025-06-27 - Repeated overhead per request in Middleware
**Learning:** Middleware functions that execute on every request can introduce significant latency overhead if they repeatedly parse unchanging strings or configurations (e.g., parsing an environment variable into `ip_network` objects for every single HTTP request). Also learned that Starlette's `TestClient` defaults `request.client.host` to `"testclient"`, which throws a `ValueError` if passed to `ip_address()`.
**Action:** When working on middleware, check if any variables are static across the app's lifecycle and pre-compute/cache them within the class instance. Use checks on the raw string before re-parsing, and gracefully handle `TestClient` exceptions when reading host IPs.
## 2025-08-16 - Synchronous API fetching in loop replaced by Multithreading
**Learning:** Found an N+1 query problem where the list of relevant Meraki devices is looped over to fetch fixed IP assignments sequentially. Since each fetch involves a slow HTTP API call to the Meraki Dashboard, processing many devices took a significantly long time.
**Action:** Replaced the sequential looping over devices with a `concurrent.futures.ThreadPoolExecutor` to execute the HTTP requests concurrently. For large sets of devices, fetching in parallel drastically reduces synchronization wait time and overall latency.
## 2025-10-24 - O(N*M) nested loop found in `sync_pihole_dns`
**Learning:** Found an O(N*M) nested loop in `sync_pihole_dns` (`app/sync_logic.py`) that checks if a mapping line exists in a list of previous mappings read from `changelog.log`. Checking membership in a list takes O(N) time and runs for every client mapped, leading to O(N*M) time complexity.
**Action:** The old function checks `if mapping_line not in previous_mappings:` where `previous_mappings` is a list. By converting `previous_mappings` to a set (`previous_mappings_set = set(previous_mappings)`), we can look up the mapped lines in O(1) time and eliminate the O(N) inner loop. Also ensure to add the newly written line to the set (`previous_mappings_set.add(mapping_line)`) to prevent duplicate mapping writes on the same run.

## 2025-10-25 - Prevent N+1 API calls in SSE streams
**Learning:** Making live external API calls (e.g. `get_mappings_data`) inside a Server-Sent Events (SSE) `while True` loop can cause an N+1 query problem per connected client, leading to excessive API requests, rate limiting, and thread blocking.
**Action:** Always read data from a background-updated local cache (e.g. `cache.json` updated by a separate daemon) rather than making direct, live API requests inside the stream loop to prevent N+1 issues in SSE streams.

## 2025-10-26 - Static inner helper functions in SSE streams
**Learning:** Defining static inner helper functions (like `read_sync_log` and `read_changelog`) inside a Server-Sent Events (SSE) generator function creates unnecessary function re-definition overhead for every single SSE connection, using excess memory and CPU.
**Action:** When a helper function inside an endpoint scope does not depend on local closure variables (like the request object), define it at the module level to avoid re-defining it repeatedly per connected client.
## 2024-07-12 - Redundant Backend Polling in SSE Handlers
**Learning:** In frontend applications listening to Server-Sent Events (SSE), it is a performance anti-pattern to trigger separate HTTP polling requests (e.g., `fetch()`) to check for a specific state or error if the data required to determine that state is already included in the SSE payload itself.
**Action:** Always verify if the necessary data is already available in the SSE message stream (e.g., checking `data.log.includes(...)`) to eliminate redundant HTTP requests, reduce server load, and lower memory footprint by removing unnecessary API endpoints.

## 2025-10-27 - Prevent heavy disk I/O on every request
**Learning:** When reading from a background-synced JSON file (like `cache.json`) to prevent N+1 live API calls, directly parsing the file on every API request or SSE tick incurs heavy disk I/O and JSON deserialization overhead, becoming a new bottleneck.
**Action:** Layer the disk cache read beneath an in-memory TTL cache (e.g., `_mappings_cache`), and wrap the disk read in a `try...except (FileNotFoundError, json.JSONDecodeError)` block to provide a safe fallback in case the background daemon is currently writing to the file or hasn't created it yet.
## 2025-10-28 - Caching Configuration Parsing
**Learning:** Functions that parse environment variables and construct configuration objects can introduce redundant overhead when called repeatedly in hot loops (like SSE streams). Bypassing them with direct `os.getenv()` calls is an anti-pattern as it breaks centralized configuration and mocked tests.
**Action:** Use `@functools.lru_cache(maxsize=1)` on the central configuration loading function (e.g., `load_app_config_from_env`) to safely cache the parsed results and eliminate redundant processing overhead without fracturing configuration management.
## 2025-10-29 - Prevent N+1 API calls when fanning out
**Learning:** Found an N+1 query problem where the list of devices fetched from the Meraki Dashboard was fanned out directly to a thread pool to perform concurrent API calls. When a `meraki_network_ids` filter is provided in configuration, performing the filtering inside the thread or skipping results after fetching incurs an unnecessary external HTTP request overhead per device.
**Action:** Always filter data collections (e.g., filtering devices by network ID) *before* fanning them out to worker pools like `ThreadPoolExecutor` to avoid unnecessary external HTTP requests and prevent N+1 API call problems.
