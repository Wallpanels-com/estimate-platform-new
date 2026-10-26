# Local dropdown / room-options QA — 25 October 2026

Scope: frontend only. Native form values stay behind shared WallPanels listboxes; editable material/color suggestions retain free entry. `Field` now explicitly associates each label and hint with its control. No new packages.

## Checks completed

- Build/TypeScript and Prettier pass.
- All 27 backend tests, 27 legacy Quick Estimate parity fixtures, PDF source tests and EN/RU tests pass.
- `rule_engine.py` and `pricing_config.py` match the downloaded legacy backend byte for byte. All service and Quick formula hashes match the snapshot taken before this task. All 45 original downloaded files remain unchanged.
- Browser at 1440 and 1280 CSS pixels; EN and RU. Grand total remains $25,830 on the existing QA estimate. No zone, line item, price-book or estimate changes saved during these checks.
- Room-template menu, mouse selection, ArrowDown/Home/End, Escape and Tab exercised. Hidden select excluded from keyboard navigation; Tab from manual calculation type moves directly to quantity.
- Kitchen-island selection retains `cabinet_type=kitchen_island`; 2 LF calculates $2,400. Result name remains English in RU mode.
- Material suggestions filter “Slats” to the two matching materials; choosing Slats MDF applies the existing premium-material key. 100 SF calculates $6,000.
- Color selection invalidates a previous calculation. Arbitrary text “Custom walnut finish” is retained. Escape closes suggestions while the native dialog stays open.
- Manual item selection retains `calc_type=lf`. Measured trigger arrow inset is 15 CSS px including the border.
- Zone type, estimate type/status, and item calculation type menus checked. Cancelling estimate details leaves the saved Pre mode unchanged. Item LF selection updates the existing unit field to LF; the edit was cancelled.
- Living room 12 × 8 ft: $12,480 without fireplace, $17,280 with fireplace, matching the unchanged legacy formula. Fireplace and office panel toggles have their own full-width group, explicit label and descriptive hint. Office desk tier switches correctly.
- Author/sort filter menus checked; choosing Title updates only the sort URL and closes the menu without reopening it. Filters cleared afterwards.
- Services retain the original 10 entries and instructions to enter project-specific prices.
- Menus use the existing native Popover mechanism, stay above modal/scrolling surfaces, flip above when needed and reposition on viewport/ancestor scroll. Keyboard navigation scrolls the list rather than the document.
- No presentation downloaded; export source/generators unchanged. AI/voice and external services were not called.

Evidence: `.local/qa/dropdowns/manual-menu.jpg`. A detailed Russian explanation of all controls and inherited pricing is in `docs/guide-ru.md`.
