# Report signing

ProofScan canonicalizes the versioned report JSON with RFC 8785, hashes it using SHA-256 and signs the 32-byte digest with Ed25519. The signature uses unpadded base64url. Storage of the signature and transition to buyer-visible state are atomic.

The buyer endpoint returns the payload and signature. The public verify endpoint recalculates the digest, checks the Ed25519 signature with the registered public key and checks invalidation. It returns the status and cryptographic metadata. Independent verification of an exported payload requires a trusted public key for the report's key ID.

When rotating a signing key, configure a new `REPORT_KEY_ID` and `REPORT_PRIVATE_KEY`, and put the old public key into the JSON map `REPORT_TRUSTED_KEYS`. Keep the private key server-side.
