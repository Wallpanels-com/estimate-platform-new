# Price Book editing

Every signed-in User can edit the shared Price Book.

- Add category creates a top-level catalogue category. Add subcategory creates a
  nested category under the selected one. Edit category changes EN/RU names,
  icon and parent for custom categories; descendants and items stay attached.
- Add/edit item manages names, descriptions, category, item kind, pricing method,
  unit, rate, default quantity and specifications. The same editor is used when
  creating an item from Estimate Builder.
- Save rates, Save category and Save item open a confirmation before any write.
  Cancel returns to the unchanged draft. Backend conflicts/errors remain visible.
- Archive and Restore require confirmation. Archiving a category hides its whole
  subtree from new selections and the quote API without deleting its records.
  Show archived makes recovery available. Child archive flags are preserved, so
  restoring a parent does not revive independently archived children or items.
- Existing estimates retain their copied names/prices. Formula parameters and
  supported calculator types stay separate from custom catalogue categories.
  Required built-in calculator categories remain at the top level and cannot be
  archived; their display names/icons and existing rate fields remain editable.
- Categories use a nullable parent ID inside the existing catalogue JSON;
  no database schema migration is required. Backend validation prevents cycles,
  invalid parents and duplicate names within the same parent. Category/item
  versions and the pricing revision continue to reject stale saves.

Checkpoint before this change: `f2eb032` (source archive also stored in ignored
local backups). Roll back application code through Git/Railway; do not restore
the database over employee edits. New parent IDs are additive catalogue metadata.

Validation: backend suite 104 tests passed, one optional fixture skipped;
EN/RU actual-component tests cover rate/category/subcategory/item confirmations,
cancel-without-write and draft retention, stale version tokens and archive actions.
Production build passed. Desktop UI was inspected in the Codex browser; personal
Chrome was not used. `scripts/qa_pricebook_editing.py` performs a cross-account
live check on newly created TEST entries only and archives those entries afterwards.
