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
## 2025-10-25 - Redundant API Polling in SSE Streams
**Learning:** Found a redundant HTTP GET request to `/check-pihole-error` being made every time an SSE message was received on the frontend. This created unnecessary network traffic and backend server load, effectively negating the benefits of using an SSE stream for pushing updates.
**Action:** When a frontend uses an SSE stream to receive data, check if any supplemental API calls made upon message receipt can be eliminated by including the necessary state directly in the SSE payload or by parsing the existing payload locally.
