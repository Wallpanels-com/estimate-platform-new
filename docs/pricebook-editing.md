# Price Book editing

Every signed-in User can edit the shared Price Book. Categories are flat;
subcategories and parent selection are disabled in both UI and API. The upgrade
preserves active entries as top-level categories and carries inherited archive
state forward, without deleting estimates or changing their copied prices.

Group headers have an Add button. Supported rate groups use their existing
formulas: wall base rates and upgrades, fixed additions, furniture and mirror
types, material upgrades, services, finish groups/options and build-out tiers.
New entries are drafts until Save rates is confirmed. Custom wall base rates are
explicit choices in the wall calculator; automatic area tiers retain their
original thresholds. Groups with a fixed formula offer a separate catalogue item
instead of silently registering an unsupported automatic rule.

Mirrors support Rustic Mirror ($100/SF), Bronze Mirror ($100/SF), Clear Mirror
($80/SF); installation remains the independently saved fixed fee. Shelving Unit
starts at $800/LF. These types and future supported additions are stored in the
existing pricing JSON and appear in calculator selections.

Save rates/category/item requires confirmation; cancel preserves the draft.
Archive is recoverable. Show archived exposes Restore and Delete permanently.
Permanent deletion is restricted on the backend to archived entries, requires the
current entry version and rejects built-in categories. Deleting a category also
removes its catalogue items. Saved estimates and immutable audit history remain.

Old archived Price Book data is removed only through these authenticated APIs
after an explicit owner request and backup. Estimate Trash is a separate feature
and is never part of catalogue cleanup. Backups continue to exclude PDF exports.
