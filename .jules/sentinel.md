## 2024-06-26 - IP Whitelist Middleware IP Spoofing
**Vulnerability:** The application was manually parsing the `X-Forwarded-For` header to determine client IP in `IPWhitelistMiddleware`.
**Learning:** This is a dangerous pattern, as an attacker can easily inject arbitrary spoofed IP addresses into this HTTP header. A single spoofed header like `X-Forwarded-For: 127.0.0.1` completely bypassed IP whitelist restrictions.
**Prevention:** Always rely on the ASGI/WSGI web server (e.g. uvicorn with `--proxy-headers` flag enabled) to safely handle and parse incoming proxy forwarded-for headers instead of writing application logic.
