# Interface language: EN / RU

The language switch is available on the sign-in screen, in the main navigation, and in the estimate builder header. English is the default. The choice is stored in `wallpanels.ui-language` in this browser and survives navigation/reloads; storage events synchronize other tabs. If storage is unavailable, switching still works for the current session.

`LanguageProvider` updates visible labels and the document language without remounting pages. Buttons expose their selected state with `aria-pressed`. Source labels remain English; Russian translations live in `apps/frontend/src/lib/ru.json`. Dynamic labels use numbered placeholders so customer text is never interpreted as a translation template. Russian item/estimate counts use plural rules.

The setting applies only to interface labels, forms, menus, notifications and built-in catalog option labels. Customer-entered names, descriptions, catalog values, saved section keys, enum values, prices, units and API payloads retain their original values. Existing estimate content is not automatically translated. Generated English scope names remain English even when the calculator UI is Russian.

Presentation language is independent from the interface. No language argument or header is added to PDF requests. The preview/download loader, cache identity, English filenames and every backend presentation/PDF/XLSX generator are unchanged. Pre and Final continue using their existing respective routes.

## Local validation (2026-10-25)

- `npm run build`, `npm run format:check`, `npm run test:i18n`, `npm run test:pdf-source`, and all 27 existing backend tests passed.
- EN/RU translation fallback, persistence, blocked storage, placeholders and Russian plural forms tested.
- API enum/value/defaultValue attributes, default section grouping and builder tab identifiers checked independently from translated labels.
- PDF fake-transport tests run with Russian UI selected; English routes/filenames and shared preview/download bytes preserved. No presentation downloaded.
- Presentation generator SHA-256 checks match the pre-change local snapshot. PDF loader source matches the snapshot byte for byte.
- Browser: Builder labels, forms, navigation, page reload and both switch states checked. Unsaved Quick Estimate project input survives EN → RU switching. Desktop layout checked at 1280 CSS pixels.
