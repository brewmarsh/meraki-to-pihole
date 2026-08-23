🚨 Severity: HIGH

💡 Vulnerability: The application relies on an IP whitelist middleware (`IPWhitelistMiddleware`) as its primary security mechanism for sensitive operations. However, this offers no protection against Cross-Site Request Forgery (CSRF). Malicious websites could trick an authenticated user's browser (or a user on the whitelisted network) into making unauthorized, state-changing `POST` requests to endpoints like `/update-meraki` or `/update-interval` since the user's browser implicitly possesses the allowed IP.

🎯 Impact: An attacker could force unauthorized operations, potentially modifying system configurations or triggering unnecessary sync tasks, compromising the integrity of the application.

🔧 Fix:
- Introduced a `CSRFMiddleware` that intercepts `POST`, `PUT`, `DELETE`, and `PATCH` requests and verifies the presence of the `X-Requested-With: XMLHttpRequest` header. Browsers inherently prevent simple cross-origin forms from including this custom header without a CORS preflight, effectively preventing CSRF.
- Explicitly positioned `CSRFMiddleware` appropriately in the middleware stack so it runs before core request handling.
- Updated all frontend `fetch()` API calls in `index.html` to include the `X-Requested-With: XMLHttpRequest` header to ensure legitimate requests succeed.
- Updated all automated tests (`TestClient.post`) to append the header to pass the new middleware checks.

✅ Verification:
- `poetry run pytest` verifies that tests successfully simulate AJAX requests and pass the CSRF check, and that `test_update_interval`, `test_clear_log`, and `test_validation` pass.
