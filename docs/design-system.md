# WallPanels workspace design

Audience: estimators and project managers working with long construction estimates.

Palette: ink #242522, paper #ffffff, workspace #f5f5f2, bronze #9c7843,
muted text #64665f, border #dedfd8. Bronze is reserved for selected and primary
controls. No decorative gradients, promotional hero, dashboard card grid or charts.

Type: system sans (Segoe UI / SF Pro) for a native, legible workspace. Heading 24–32,
body 14–16, labels 12–13; tabular numbers for money. The skill's portfolio/hero and
Cinzel recommendation was rejected as unsuitable for an estimate editing tool.

Desktop Builder: photo rail 240px | flexible estimate minmax(0,1fr) | zones/summary 264px.
At 1280px rails become 208px and 236px. Below 1100px use explicit workspace tabs
(Estimate / Photos / Zones) instead of compressing three columns. At 768px line items
become stacked rows. Existing responsive behavior is retained; this cleanup focuses on desktop.

Spacing scale 4, 8, 12, 16, 24, 32. Controls 40px desktop and at least 44px on coarse
pointers. Shared Field, Button, Modal, PageHeader, EmptyState and notices. Visible
focus; native dialog focus management; status aria-live; no hover-only functions.

QA widths: 1440, 1280, 1024, 768, 390. Verify empty, loading, error, long text and
large estimates. Desktop and mobile must retain the same real API functionality.

## Builder restraint rules

- A work row shows name, optional two-line description, quantity + unit, rate and total.
  Quantity/rate stay editable; the name or total opens the complete item editor.
- One contextual action trigger per item/zone/photo. Move, duplicate, delete, type,
  section and TBD remain available; destructive operations still use confirmation.
- Blank descriptions occupy no space. Long descriptions and zone notes expand on demand.
- Section subtotal is in its heading; zone subtotal is at the end of its scope.
- Photo rail shows actual images and one Add photo control for the next free slot.
  All four slots, replacement, removal, viewer, validation and export inclusion remain.
- Add items is the main scope action; manual items, services and AI are in More scope actions.
- Summary keeps Grand total and PDF/XLSX in view. Zone breakdown is collapsed by default;
  markup/discount opens from the Summary heading. Every visible field/action control is 40px.
- Native popovers use the top layer so scroll regions cannot clip their actions. Keyboard
  Tab/Escape and light dismiss work without hover-only controls.
