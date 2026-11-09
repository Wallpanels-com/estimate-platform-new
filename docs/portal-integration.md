# WALLPANELS OS integration

Estimate and HR keep their original backend, business data, files and workflows. Both the standalone UI and embedded UI call the same API. No record copy or background synchronization is involved.

With `PORTAL_AUTH_ENABLED=true`, credentials and current module grants are verified against `PORTAL_BASE_URL` using `PORTAL_BRIDGE_SECRET`. The corresponding OS variable is `ESTIMATE_BRIDGE_SECRET`. Keep that shared secret server-side. Requests are HMAC authenticated and time bounded. An unavailable identity provider fails closed.

A portal iframe uses a 60-second single-use sign-in code delivered with strict origin/source validation. Code exchange happens server to server. Embedded tokens are in memory, separate from the standalone token; they never enter URLs. The OS controls outer navigation. The native module retains forms, autosave, concurrency checks, uploads, media and PDF/export routes, and uses a viewport-sized frame so dialogs stay visible. Language messages affect the UI, not original documents or PDF language.

Existing local tokens require a fresh login after enabling central identity. Standalone login accepts the same OS username/password. Archived users and removed grants are denied on their next API request. Legacy Estimate user rows and associated records are preserved. Only the verified portal owner maps to the existing configured access-manager UUID; other identities receive stable UUIDs without linking by email. Account/password/grant management is centralized in the OS.

Verification: `npm run build`, `npm run test:pdf-source`, `node scripts/test-portal-session.mjs`, and backend `test_portal_identity.py`, `test_page_access.py`, `test_estimate_creation.py`. JIT provisioning and repeated login were exercised on isolated async SQLite. No production estimate/HR records are created or modified for QA.
