# Что перенесено и что изменилось

## Сохранность reference

Обе исходные скачанные папки использовались только во время первичного локального
переноса. Исторические SHA-256 сохранены в `reference-checksums.json`, а текущие
regression tests проверяют критические перенесённые контракты внутри этого
репозитория. Штатные команды больше не зависят от папок рядом с проектом. Runtime
secrets, node_modules и старый compiled JS в проект не включаются.

Старая локальная база и старое storage также сохранены. Новый проект использует отдельный database name и свою копию storage. Локальные ports отличаются от reference-сервера.

## Backend

Перенесены все исходные modules/routes, models, schemas, requirements, Dockerfile backend, Alembic scaffold, HTML и XLSX templates. Сохранены Estimates, Zones, Line Items, auth, фото/audio/storage, pricing endpoints, AI endpoints, PDF/XLSX downloads.

На этапе первичного переноса побайтно сохранены: rule_engine.py, pricing_config.py, pdf_service.py, passport_service.py, project_passport_template.xlsx, оба HTML-шаблона, ORM-модели. Это контролируют tests.

Минимальные исправления в новой копии:

1. load_estimate использует populate_existing при повторной загрузке: recalc_totals получает актуальную коллекцию, а не stale line_items из той же сессии.
2. PATCH строки пересчитывает qty/rate и при нуле, не используя truthiness.
3. При create явный total_price сохраняется. Это необходимо, чтобы существующий calc_mirror не терял фиксированные $1,000 при сохранении в SF-строку.
4. Duplicate zone больше не обращается к отсутствующим panel_name/panel_color/panel_coverage_pct. Копирует original_unit_price/TBD и обновляет коллекцию перед пересчётом.
5. OPENAI_API_KEY необязателен для запуска; AI-клиент создаётся при вызове, при отсутствующем ключе возвращается 503 с понятной причиной. Модели AI и промпт сохранены.
6. Settings игнорирует несвязанные dev-переменные в общем .env.
7. FRONTEND_DIST добавляет необязательную static SPA-раздачу после API routes.

Ставки и схема БД не изменялись. Крупное переустройство бизнес-логики, ownership, audit, filesystem cleanup и migration framework не выполнялось.

## Frontend

Оригинал — готовая восстановленная сборка без React src/package.json/source maps. Он не редактировался массово и не включён в новый runtime. Написаны поддерживаемые React/TypeScript modules с типами существующего API, same-origin proxy, Query cache и обычным CSS.

Восстановлены login/register/onboarding, список/поиск/type filters, create/duplicate/delete/restore, Estimate Builder, Pre/Final, зоны/порядок/копирование, editable line items/sections/TBD, фото, API-calculator/manual/services, AI input, Quick templates, Price Book и PDF/XLSX download.

Кнопки reorder заменяют прежний drag-and-drop и работают с клавиатуры. В корзине восстановлены restore и permanent delete с явным подтверждением. Список поддерживает поиск, тип, автора, даты обновления, диапазон суммы и сортировку; фильтры сохранены в URL.

Quick-формулы сохранены в читаемом quickEstimate.ts. 27 fixtures из прежней сборки сравнивают все 9 room types при 0/12/20 ft и наборах опций. Серверный quick-config по-прежнему не управляет всеми legacy Quick rates: этот конфликт не устранялся изменением pricing.

## UI

Общая тёмная навигация, белое рабочее полотно и сдержанные бронзовые состояния WallPanels. Список смет — регистр строк, не сетка dashboard-карточек. Общие tokens controls/spacing/borders, табличные цифры, единые формы/модальные окна, видимые focus, loading/error/empty states, подтверждения удаления.

Builder: стабильные rails слева/справа, гибкий центр; длинные имена зон переносятся, общий title доступен через details/title. На tablet/mobile панели переключаются явно. На phone позиции становятся вертикальными, длинные названия — textarea. Экспорты отделены от действий над строками.

Skills проверены: frontend-design, ui-ux-pro-max, layout-consistency-guard, web-design-guidelines; применены React best practices и full-story verification. Уже установленных навыков хватило; новые сторонние skills/plugins не устанавливались. Из рекомендации UI/UX поиска отвергнуты portfolio hero и display-fonts: они не подходят для плотного estimate workspace.

## Что ещё требует работы

- Полная browser automation загрузки из OS file picker ограничена настройками Chrome extension; POST upload и отображение фото в Chrome проверены отдельно.
- Настоящий OpenAI key отсутствует; реальная транскрипция/анализ не выполнялись.
- Постоянные user roles/ownership, закрытый storage, security review, audit/versioning и управляемые migrations нужны до выхода из local-only режима.
- Семантика final_total/markup/discount/PDF/XLSX требует отдельного согласования. Генераторы намеренно сохранены.
- История/физическая очистка файлов и полное копирование фото при duplicate estimate — прежние ограничения.
- Final Proposal реализован отдельным renderer и включает общую титульную страницу,
  zone slides, Investment Summary и 13 корпоративных страниц. Custom slide editor
  остаётся отдельной будущей функцией.
- Dockerfile подготовлен, но контейнерный build на этом Mac не проверен, Docker здесь не установлен. Проверен native Mac dev и FastAPI serving готовой frontend-сборки.

## BHUPESH follow-up — 22 October 2026

The new Pre-Estimate renderer is separate from the byte-preserved legacy Final
service. Passport retains its mechanism/template, with TBD output, safe percentages
and full recalculation on open. Both download filename paths drop the leading
5. for every client. Current behavior and verification: [BHUPESH QA](bhupesh-local-qa.md).
