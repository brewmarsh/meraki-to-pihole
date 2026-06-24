## 2025-02-12 - O(N*M) nested loop found in `map_devices`
**Learning:** Found an O(N*M) nested loop in `map_devices` (`app/sync_logic.py`) that matches a client's IP with a domain from a dict of IP to domain mappings.
**Action:** The old function loops over the clients, and for each client it checks if the client IP is in a set of IP addresses. If it is, it loops over all the pihole records to find the domain. By building an inverse dictionary `ip_to_domains` upfront, we can look up the matching domains in O(1) time and eliminate the inner loop.
