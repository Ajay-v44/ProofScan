# API integration

The API exposes [OpenAPI](http://127.0.0.1:8000/docs). Client wire types live in `packages/api-client`.

| Operation | Route groups |
| --- | --- |
| Buyer session | `/api/v1/auth/register`, `/login`, `/session`, `/logout` |
| Requests and updates | `/api/v1/verifications`, `/api/v1/notifications` |
| Guest session | `/api/v1/guest/{verification_id}` with `/exchange`, `/consent`, `/scan`, `/submit` and `/decision` |
| Buyer report | `/api/v1/verifications/{verification_id}/report` |
| Exterior photos | Guest `/photos` upload with `X-Scan-Challenge`, and authenticated buyer or guest photo reads |
| Handoffs | `/api/v1/handoffs` with `/start`, `/photos`, `/record`, `/activate`, `/invite`, `/accept`, `/report`, and `/close` |
| Listing suggestions | `/api/v1/claims/suggest` when Moonshot is configured |
| Public report check | `/api/v1/reports/{report_id}/verify` |
| Operator | `/api/v1/admin/overview`, `/search/{id}`, `/audit`, verification revocation and report invalidation |

Buyer register and login set the session cookie. An authenticated Supabase JWT can also be supplied as a Bearer token when the API is in Supabase mode. The guest link uses a URL fragment, which the page exchanges through a POST for a scoped cookie. The scan ticket contains a separate one-time challenge.

Errors use a JSON `detail` field. Responses use 401 for missing user authentication, 403 for denied privileges, 404 for unavailable resources, 409 for invalid transitions or challenges and 422 for invalid fields.
