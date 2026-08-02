🚨 Severity: HIGH
💡 Vulnerability: Infinite recursion vulnerability causing Denial of Service (DoS). When the Pi-hole API repeatedly returns a 403 Forbidden status (e.g., due to revoked credentials), `_api_request` recursively calls itself without limit, crashing the app with a RecursionError.
🎯 Impact: An attacker or a simple misconfiguration could trigger a crash of the entire sync process, rendering it incapable of performing any mapping duties until manually restarted.
🔧 Fix: Added a `_retry=True` flag to the `_api_request` method in `app/clients/pihole_client.py`. If a 403 is received, it only retries once (`_retry=False`), safely bailing out and preventing infinite recursion.
✅ Verification: Ran `pytest` suite and manually verified with a mock that a 403 triggers a safe exit without raising `RecursionError`.
