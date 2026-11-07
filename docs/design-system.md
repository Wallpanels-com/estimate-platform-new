# WallPanels workspace design

Audience: estimators and project managers working with long construction estimates.

Palette: ink #242522, paper #ffffff, workspace #f5f5f2, bronze #9c7843,
muted text #64665f, border #dedfd8. Bronze is reserved for selected and primary
controls. No decorative gradients, promotional hero, dashboard card grid or charts.

Type: self-hosted **Montserrat Variable** (`@fontsource-variable/montserrat`, SIL OFL-1.1).
EN/RU/UK glyphs and actual variable weights are loaded from the application's own hashed WOFF2 assets; there are no Google Fonts/CDN requests. The shared `--font-ui`, `--text-*`, `--weight-*`, and `--leading-*` tokens live in `styles.css`.

| Role | Size | Weight | Leading |
| --- | --- | --- | --- |
| Page title | 30px | 600 | 1.3 |
| Dialog title | 22px | 600 | 1.35 |
| Section title | 20px | 600 | 1.3 |
| Card/group title | 16px | 600 | 1.3 |
| Body and values | 14px | 400 | 1.55 |
| Controls/navigation | 13px | 500 | 1.4 |
| Captions/supporting text | 12px | 400–500 | 1.6 |
| Grand total | 26px | 700 | inherited |

Compact table/chart/Builder labels retain their component density and shared geometry; the same font family applies everywhere, with tabular figures for monetary amounts. Avoid light weights and arbitrary 550 weights. Heading tracking is modestly negative, body text stays untracked. Long headings wrap without colliding with actions. PDF/presentation generators and company slide assets retain their separate approved Arial typography; this font change is only for the web interface.

Desktop Builder: photo rail 240px | flexible estimate minmax(0,1fr) | zones/summary 264px.
At 1280px rails become 208px and 236px. Below 1100px use explicit workspace tabs
(Estimate / Photos / Zones) instead of compressing three columns. At 768px line items
become stacked rows. Existing responsive behavior is retained; this cleanup focuses on desktop.

Spacing scale 4, 8, 12, 16, 24, 32. Controls 40px desktop and at least 44px on coarse
pointers. Shared Field, Button, Modal, PageHeader, EmptyState and notices. Visible
focus; native dialog focus management; status aria-live; no hover-only functions.

QA for current work: desktop 1512 and 1280px, EN/RU, empty/loading/error states, long text and large estimates. Mobile/tablet redesign is deferred until the owner requests it.

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

## Restraint and interaction motion

Owner direction: avoid generic AI-shaped dashboards. Use WallPanels content, Montserrat hierarchy and the established workspace grid. Do not add decorative KPI cards, repeated icon tiles, marketing subtitles, invented metrics, gratuitous gradients or looping effects to utility pages. HR Staff status counts are compact filters, aligned to the table and toolbar. Team spaces retains the owner's selected reference style. Review against [anti-slop](https://github.com/miqdadbadjuber/anti-slop) as a supplementary checklist, not as a detector or runtime dependency.

Native scrolling stays in charge; CSS smooth scroll applies to anchors and programmatic in-page movement. Route changes reset instantly to avoid sweeping through the previous page. No wheel interception or perpetual scroll animation loop is installed. Dialogs enter in 180 ms and reverse the movement on dismissal in 150 ms, using transform/opacity. Wrap conditional modal components in `ModalPresence`; parent state still owns dirty-close decisions and persistence. Presence retains the dialog only for the exit, blocks duplicate interactions, then releases native focus. Reopening cancels the pending exit. Reduced motion removes the delay and nonessential effects. Menus and control colors use short transitions; chart filtering preserves the canvas instance.
