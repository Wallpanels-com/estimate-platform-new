# Presentation notes — shared release

Dmitry approved the shared rollout on 2026-11-18 after testing the owner trial.
Active accounts with Estimates access can use the editor and render the notes.
Portal sessions require the estimating module or no module, plus the estimates
page grant; owner status is no longer required. `auth/me.presentation_notes_enabled`,
the PATCH route and PDF rendering enforce the same boundary. HR-only, Quick-only
and inactive accounts remain excluded. Existing saved notes are preserved.

Each Pre/Final zone has a Presentation notes editor with editable suggestions,
free text, multiple rows and a text preview. Up to 20 notes of 1,000 characters
are persisted under `pdf_layout.zone_presentation_notes_trial`. Generic layout
updates preserve that reserved key. The dedicated PATCH participates in existing
revision conflict checks and row locking. Saving an empty list clears notes.

Notes render after priced scope, without a price or calculation, regardless of
the calculation visibility switch. They do not participate in pricing, tax,
ranges, or XLSX. Both brands and Pre/Final PDF paths use the gated immutable view;
preview/download share the PDF source. Long notes use measured wrapping and
continuation pages. The shared release also includes item descriptions in Final scope
rows; Pre already supports them. Existing zero-price items are not auto-converted.

Duplication remaps zone IDs. A linked Final inherits Pre notes until its own notes
are explicitly edited (including clearing the list). Explicit Final notes protect
a removed source zone from automatic removal. No schema migration is needed.

Validation: test_presentation_notes covers shared employee access, restricted and
inactive accounts, portal modules/grants, validation, real database inheritance,
override/reload and both brands/modes/calculation settings. It verifies measured
long-note geometry, identical owner/employee PDFs and excluded-account isolation.
Branch/range/delivery regressions and frontend build/i18n/PDF-source checks cover
existing behavior. No customer estimates are modified for verification.

The UI and layout are unchanged from the approved trial: presets, free text,
keyboard selection, conflict preservation, save/reopen/delete and responsive
layouts were previously verified at 1512, 1280, 1024, 768 and 390 px.
