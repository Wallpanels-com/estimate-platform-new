# Presentation notes — Dmitry-only trial

The owner approved a production trial on 2026-11-18, not a shared rollout.
`presentation_notes.available` uses the existing immutable access-manager owner
check. `auth/me.presentation_notes_enabled`, the PATCH route, and PDF rendering
all enforce that gate. Other accounts retain their existing PDF output.

Each Pre/Final zone has a Presentation notes editor with editable suggestions,
free text, multiple rows and a text preview. Up to 20 notes of 1,000 characters
are persisted under `pdf_layout.zone_presentation_notes_trial`. Generic layout
updates preserve that reserved key. The dedicated PATCH participates in existing
revision conflict checks and row locking. Saving an empty list clears notes.

Notes render after priced scope, without a price or calculation, regardless of
the calculation visibility switch. They do not participate in pricing, tax,
ranges, or XLSX. Both brands and Pre/Final PDF paths use the gated immutable view;
preview/download share the PDF source. Long notes use measured wrapping and
continuation pages. The trial also includes item descriptions in Final scope
rows; Pre already supports them. Existing zero-price items are not auto-converted.

Duplication remaps zone IDs. A linked Final inherits Pre notes until its own notes
are explicitly edited (including clearing the list). Explicit Final notes protect
a removed source zone from automatic removal. No schema migration is needed.

Validation: test_presentation_notes (owner route gate, validation, real database
branch inheritance/override/reload, both brands/modes/calculation settings,
long-note geometry and other-account byte equivalence); 31 branch/range/display/
delivery/photo regression tests; frontend build, i18n, PDF-source and repo checks.
Browser QA uses mocked requests, verifies presets/free typing, keyboard selection,
conflict preservation, save/reopen/delete and owner gating at 1512, 1280, 1024,
768 and 390 px. Rendered PDF and browser screenshots were visually inspected.
No customer estimates were edited for verification.

A future shared rollout must explicitly update the backend access policy and
review the owner-only Final-description behavior. Do not enable globally until
Dmitry approves the trial.
