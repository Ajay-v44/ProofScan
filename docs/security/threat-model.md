# Threat model

| Threat | Implemented control or outstanding risk |
| --- | --- |
| Old scan or replay | Tickets expire after 15 minutes and bind to the current scan, platform and seller session. The database transaction consumes each ticket once. A modified collector can still attach old readings to a fresh ticket. |
| Modified desktop or mobile client, fake telemetry | A desktop response has collector-reported assurance. A server signature protects the report contents. Hardware attestation remains a separate integration. |
| Stolen guest link | Random 256-bit secret, server-side hash, 48-hour expiry, scope restriction, HttpOnly cookie and operator revocation. Keep the original guest link private until delivery to the intended seller. |
| Report tampering and admin abuse | RFC 8785 canonicalization and Ed25519 signing, append-only tables, separate operator allowlist, audit entry and irreversible invalidation. Password-confirmed account deletion can remove signed records owned by that account. It preserves existing operator audit entries. A database owner can change database controls. |
| Storage URL leakage | Images are retrieved through a scoped guest or owner endpoint and expire. The current PostgreSQL configuration does not use signed cloud URLs. |
| Malicious image or model prompt injection | Image inputs are capped, decoded as JPEG and re-encoded to remove metadata. Listing text is treated as untrusted and the model result has a strict schema and requires buyer review. The inference adapter has no platform tools. |
| Service abuse or excessive scans | Bounded request inputs, short-lived tickets, authorization checks and paged lists. Use HTTPS and perimeter rate limits for any shared deployment. |
| Sensitive collection | The Windows collector requests named CIM fields, excludes system and component serial numbers, and does not scan personal files. Public verification exposes cryptographic metadata and omits hardware and listing details. |

Handoff photos and condition notes document the owner's observations. They do not establish device identity or independently confirm damage. An invitation records acknowledgment by the holder of that link.

Avoid logging request bodies, fragment tokens, cookie headers, exceptions containing connection strings, and generated credentials. Test output and Playwright traces can contain test scan data. Keep them local.
