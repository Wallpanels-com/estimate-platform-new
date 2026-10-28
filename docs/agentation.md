# Owner-only visual feedback

Agentation 3.1.2 is installed as a frontend dev dependency and included in the
production build intentionally. `/auth/me` grants `agentation_enabled` only to
the active user whose immutable UUID matches backend `AGENTATION_USER_ID`.
The default is disabled. Display names, logins and the shared User role never
grant this capability. Other accounts do not mount or download the lazy toolbar.
Signing out or switching accounts unmounts it. This flag adds no estimate,
Price Book or user-management privileges and no public feedback API.

The toolbar connects to the owner's local MCP server at `http://localhost:4747`.
The server must run on the same computer as the browser. Codex's Agentation
plugin is already available on the owner's Mac. No external/public annotation
service, remote tunnel or Railway storage is created. If local sync is
unavailable, feedback remains in the browser and can be copied into the chat.
A browser may request permission to connect to a local service. The default MCP
server permits development origins only. Direct sync from the corporate Railway
site requires the MCP process to be started with
`AGENTATION_CORS_ORIGINS=https://estimate-platform-production.up.railway.app`.
The current local process rejects that origin (HTTP 403); copy/paste feedback
works independently. No global MCP configuration or other sessions were changed.

Open the bottom-right Agentation button, select an element, enter the requested
change, and add the note. Ask Codex to apply the notes, then commit/push them.
The wrapper exposes only the current session ID in `data-agentation-session`
for scoped agent verification; agents should not enumerate unrelated sessions.
Annotations are not an autonomous push trigger and do not execute code.

Verification: `node scripts/test-agentation-ui.mjs`,
`.venv/bin/python -m unittest discover -s tests -p test_agentation_access.py -v`,
and `npm run build`. Test real `/auth/me` for the owner and another employee
after deploying; only the owner response should enable Agentation.
