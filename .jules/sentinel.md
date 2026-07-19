## 2026-07-04 - Fix Thread Starvation DoS in Server-Sent Events
**Vulnerability:** The `/stream` endpoint used a synchronous generator with `time.sleep()` in a FastAPI `StreamingResponse`. This blocks a worker thread for the duration of the connection (which is infinite in SSE). Multiple concurrent connections could easily exhaust the thread pool, leading to a Denial of Service (DoS) where the server can no longer handle any requests.
**Learning:** In FastAPI, yielding from a synchronous generator blocking operations like `time.sleep` in `StreamingResponse` will block the worker threads that FastAPI relies on to handle requests. It is essential to use an asynchronous generator (`async def`) when maintaining long-lived connections like Server-Sent Events (SSE).
**Prevention:** Always use asynchronous generators (`async def`) for `StreamingResponse` when yielding events over time. Use `await asyncio.sleep()` instead of `time.sleep()`, and offload any synchronous blocking I/O (like file reading or network requests) to a separate thread using `await asyncio.to_thread()`.
## 2026-07-05 - Fix Memory Exhaustion DoS in Log API Endpoints
**Vulnerability:** The application read entire, unboundedly growing log files (`sync.log`, `history.log`, `changelog.log`) fully into memory using `Path.read_text()` and `f.readlines()` on API endpoints (`/stream`, `/history`, `/check-pihole-error`). Over time, this allows an attacker (or normal load) to trigger memory exhaustion and a Denial of Service (DoS).
**Learning:** Using `Path.read_text()` or `f.readlines()` is dangerous for log files or any file that grows continuously over the lifecycle of the application.
**Prevention:** Instead of reading the whole file, use `collections.deque(f, maxlen=1000)` to read a bounded number of recent lines when exposing log data through APIs, ensuring fixed memory consumption regardless of file size.
## 2025-02-27 - Fix IPWhitelistMiddleware Proxy Bypass
**Vulnerability:** IP whitelist bypass behind reverse proxies due to relying solely on `request.client.host`.
**Learning:** Depending on the client's host directly in environments using reverse proxies allows attackers to spoof the client IP and bypass IP whitelisting restrictions.
**Prevention:** Use standard forwarding headers (`X-Forwarded-For` or `X-Real-IP`) to extract the client IP, or handle client IP logic robustly according to reverse proxy configuration.
## 2026-07-10 - Fix IPWhitelistMiddleware Test Backdoor
**Vulnerability:** A hardcoded `client_ip_str == "testclient"` check was left in production middleware, allowing any attacker to bypass IP whitelisting by passing headers like `X-Forwarded-For: testclient` which would then be authorized as `127.0.0.1`.
**Learning:** Testing shortcuts left in production code create critical security vulnerabilities, particularly when combined with proxy header trusting where the client string can be fully spoofed.
**Prevention:** Never leave backdoor strings for testing in production security logic. In FastAPI testing, use the `client` argument in `TestClient(app, client=('127.0.0.1', 12345))` to properly mock the request client IP instead.
## 2026-07-19 - Fix Rate Limiting IP Spoofing Bypass
**Vulnerability:** The application used `slowapi`'s default `get_remote_address` for rate limiting, which trusts the `X-Forwarded-For` header and extracts the leftmost IP. When deployed behind a reverse proxy, attackers could spoof their IP by sending a custom `X-Forwarded-For` header, allowing them to bypass rate limiting completely.
**Learning:** Default rate limiting configurations (like `get_remote_address`) are often unsafe behind reverse proxies because they blindly trust proxy headers and take the leftmost IP which is user-controlled.
**Prevention:** Implement a custom `key_func` for the Limiter that securely extracts the rightmost IP appended by the trusted proxy and explicitly validates whether `TRUST_REVERSE_PROXY` is enabled.
