# ADR 0002: Opaque server-managed sessions

Status: accepted, 2026-09-16.

Browser authentication uses a host-only secure HttpOnly cookie containing an
opaque random token. Native clients can request the same token through bearer
transport. The database stores only its SHA-256 digest.

This allows immediate revocation, session inventory, idle expiry, and password-
reset invalidation without JWT refresh and revocation machinery. Cookie writes
also require an HMAC-derived CSRF token and an exact Origin. The cost is one indexed
session lookup per authenticated request, which is appropriate for v1 traffic.
