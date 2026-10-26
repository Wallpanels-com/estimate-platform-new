# Проверки переноса и Builder

Текущий проект BHUPESH и новый Pre-Estimate: [актуальный QA-отчёт](bhupesh-local-qa.md).
Ниже сохранена история предыдущих этапов.

## Cleanup Builder — 22 октября 2026

Работа выполнена только локально. После уточнения пользователя приоритет — desktop;
дальнейшая доработка мобильной версии не проводилась.

### Данные

- Из demo Waterfront residence удалены 12 нулевых Installation detail и одна QA manual
  fixed item ($250). Остались 2 зоны, 3 содержательные позиции, subtotal $12,300.
- Из demo Quick удалены 8 нулевых QA-позиций (LED/electrical и другие незаполненные
  дополнения). Остались 4 позиции, сумма $24,000 не изменилась. Quick formulas не менялись.
- Убраны длинные искусственные заголовки/QA-текст в двух demo, сохранены нормальные
  названия зон, содержательные priced items и фотографии. Остальные записи не удалялись.
- До очистки сохранён snapshot `.local/qa/demo-before-cleanup.json`; точный список
  21 удалённой позиции — `.local/qa/demo-cleanup.json`.
- Нагрузочные строки сохранены в `tests/fixtures/builder-stress.json`. Отдельный opt-in
  скрипт `scripts/builder_stress.py create` создаёт новую `[STRESS TEST]` смету с 60 строками,
  длинным/неразрывным текстом, TBD, 4 фото и пустой зоной. Он отказывается добавлять fixture
  в существующий estimate. `scripts/builder_stress.py trash <id>` принимает только явно
  обозначенную stress-смету. Оба режима допускают только localhost/127.0.0.1.
- После проверки stress-смета перемещена в восстанавливаемую Trash; её отсутствие
  в активном списке подтверждено повторным GET. Fixture остаётся отдельно в tests.
- `scripts/qa_api.py` больше не дополняет обычные demo нагрузочными строками и не принимает
  их ID как аргумент. Для QA используется только отдельный fixture.

### UI и сохранённые возможности

Компактные строки без пустых textarea и постоянных select/reorder/delete-кнопок.
Описание и notes сворачиваются. Полный редактор содержит name, description, section,
calculation type, unit, quantity, rate, manual total, TBD и original rate. Только изменение
количества/ставки запускает существующий API-пересчёт; metadata-only edits передают
сохранённый total, чтобы не сбросить фиксированную доплату. Backend/formulas не менялись.

В `…` находятся manual item/service/AI, действия строки, reorder/duplicate/delete зоны,
replace/remove фото. Add items, Add zone, quantity/rate, Pre/Final и оба экспорта остаются
постоянно доступны. Zone breakdown свёрнут; markup/discount открывается из Summary.
Для пустого scope оставлена одна основная Add items вместо двух одинаковых кнопок.

### Проверено после изменений

- `npm run build`, format check; 5 preservation/pricing tests, 27 Quick parity fixtures;
  45 исходных reference-файлов неизменны.
- Chrome: обычная смета с 2 зонами и 3 позициями; пустой scope; отдельные 60 позиций,
  длинные названия и descriptions; раскрытие/сворачивание; reorder item; duplicate zone;
  полные Manual/Services dialogs, полный item editor и Summary settings.
- Изменение quantity 120 → 121 → 120 обновило строки и Summary ($12,300 → $12,360 → $12,300).
- Полный редактор сохранил LF, quantity 2, rate 125, total 250 и TBD; значения подтверждены
  повторным GET API. На normal Mirror TBD включён/выключен; total $2,600 и grand total
  $12,300 сохранились. Отдельно проверены Tab к contextual action и Escape для закрытия.
- 4 фото загружены через API; все 4 имеют naturalWidth > 0 в Chrome. Viewer и Remove
  confirmation открываются, Cancel сохраняет фото. Add photo открывает native picker.
  Полная автоматизация выбора файла в OS picker по-прежнему не подтверждена.
- Pre/Final переключается с сохранением. Кнопки PDF для обоих типов и XLSX завершили
  запросы и показали success notice; generate/download/passport HTTP 200. API-результаты
  сохранены как `.local/qa/cleanup-pre.pdf`, `cleanup-final.pdf`, `cleanup-passport.xlsx`.
  PDF открываются, по 4 страницы, QA-строк нет; проверена отрисовка страницы зоны.
  XLSX открывается в openpyxl, C3 = Demo Client. Генераторы/шаблоны не менялись.
- Desktop 1440×900, 1280×900, 1280×768 и обычное окно 1512px: overflow отсутствует.
  На 1280×768 обе зоны, Add zone, Grand total и оба export buttons видны одновременно.
  Обычные строки высотой 64–65px, number controls и action triggers — 40px.
  До уточнения пользователя также проверены 390px, длинный контент и Photos/empty state;
  дальнейшие мобильные изменения не выполнялись.
- В свежей проверочной Chrome-вкладке console errors отсутствуют.

Evidence: `.local/qa/cleanup-api-verification.json`, `cleanup-pdf-verification.json`,
`builder-clean-1440.jpg`, `builder-clean-1280.jpg`, `builder-stress-desktop.jpg`.
Системное наличие файла в пользовательской папке Downloads не утверждается; успешные
browser actions, API responses и содержимое экспортов проверены отдельно.

## История первичного переноса — 21 октября 2026

Проверка выполнена локально 21 октября 2026 года. Production/Railway/GitHub не использовались.

## Сборка и контракты

- TypeScript check и Vite build успешны.
- 5 Python tests: исходные хеши pricing/PDF/XLSX/template/models, границы SF-ставок, partial coverage/addons, cabinetry и mirror installation.
- 27 Quick Estimate parity fixtures: все 9 исходных room types при разных размерах/опциях. Новый читаемый TypeScript даёт те же строки и суммы, что прежняя compiled-сборка.
- Все 45 файлов двух скачанных reference-папок остались без изменений.
- npm install/audit после обновления React Router сообщил 0 vulnerabilities. Это проверка npm advisory database на момент установки, не полный security-аудит backend.
- pip check: no broken requirements.

## API → PostgreSQL/storage → response

56 локальных проверок прошли в scripts/qa_api.py (с дополнительным наполнением браузерной QA-сметы). Evidence: .local/qa/api-verification.json и backend.log. API tests создают только QA-labelled записи, результаты помещают в Trash.

| Сценарий                                 | Подтверждение                                                   |
| ---------------------------------------- | --------------------------------------------------------------- |
| Register/login/me/profile                | Успешные HTTP ответы и JWT                                      |
| Estimate create/read/update              | Сохранённые поля, UUID и авто-Zone 1                            |
| Zones create/reorder/duplicate/delete    | Успешный duplicate 201; суммы после удаления корректны          |
| Line Items create/update/reorder         | Сумма $7,200 + $2,500 сразу = $9,700 в estimate и zone          |
| Quantity = 0                             | Стоимость пересчитывается в 0, а не остаётся прежней            |
| Mirror calculation → save                | 20 SF сохраняется как $2,600 с исходной $1,000 installation fee |
| Photo upload/delete                      | Multipart endpoints успешны; файл доступен через storage URL    |
| Price Book read/write                    | Полный JSON сохранён с теми же исходными значениями             |
| Wall/cabinet/mirror calc                 | Ответы существующего rule engine                                |
| PDF Pre/Final                            | generate/download 200, корректный PDF header                    |
| XLSX                                     | HTTP 200, openpyxl открывает workbook, проверено client поле    |
| Duplicate estimate, soft delete, restore | Успешные ответы и сохранение объекта                            |
| AI без ключа                             | Понятный 503; внешние OpenAI-запросы не выполнялись             |

## Реальный Chrome UI

Проверена цепочка пользовательское действие → новый frontend → Vite proxy → перенесённый backend → PostgreSQL/storage → обновлённый UI.

- Вход перенесённой локальной учётной записью, выход и повторный вход.
- Список смет и фильтр суммы: при minimum $10,000 остаётся одна QA Quick-смета $24,000. Поиск/type/дополнительные фильтры используют URL params.
- Создание estimate с длинным title и project/client fields.
- Изменение зоны: длинное имя, 12×10 ft → 120 SF при пустом поле площади.
- Wall calculator: LED + hidden door → 2 позиции, $9,700.
- Manual item: 2×$125 → $250.
- Создание второй зоны Mirror, 20 SF → сохранённые $2,600.
- Итог двух зон в QA-смете: $12,550.
- Pre/Final переключение сохраняется через API, подтверждено aria-pressed состоянием после ответа.
- Фотография загружена через API и отображается в Chrome с naturalWidth > 0; мобильная Photos-панель также проверена.
- Кнопки PDF и XLSX инициировали успешные generate/download/passport запросы; backend вернул 200. Сами файлы API-теста сохранены в .local/qa. Наличие файла в пользовательской папке Downloads отдельно не утверждается.
- Price Book редактирование и Save: ставка возвращена к $50 перед сохранением; фактические исходные цены сохранены.
- Quick Estimate: Living Room 12×10 ft и kitchen 8+4 LF → $14,400 + $9,600 = $24,000, сохранены и открыты в Builder.
- Эта Quick-смета перенесена в Trash и восстановлена через новый UI.
- Автоматическое системное file chooser управление Chrome не завершилось из-за ограничений расширения. Native file picker открывался; POST upload, storage и отображение проверены отдельно. Полная автоматизация desktop file selection не заявляется.

## Responsive / accessibility / дизайн

Builder, список, Price Book, Quick и login проверены на 1440, 1280, 1024, 768 и 390 px. Снимки сохранены в .local/qa, а DOM-метрики — в layout-results.json и page-layout-results.json. На проверенных состояниях document.scrollWidth равен innerWidth, переполнения основных секций нет.

Длинный title, длинное имя зоны и 15 позиций в первой зоне не перекрывают controls. Имена позиций — многострочные editable textarea. Desktop сохраняет три колонки; на tablet/phone есть явные панели Estimate/Photos/Zones. Rails и Summary имеют определённые scroll regions. Мобильные Photos и Zones & summary открываются корректно.

Проверены visible labels/aria-label у видимых controls, keyboard alternatives для reorder, focus-visible, native dialog semantics/Escape, aria-live notices, disabled/loading states. Мобильный Filters overlay помещается в viewport, его длинная форма прокручивается. Console error logs на проверенной Builder-сессии пусты.

После визуальной проверки исправлены: непреднамеренное вертикальное центрирование списка, пустое растянутое поле Base rates рядом с длинным списком addons, однострочные обрезанные имена позиций, скрытая accessible-label AI-кнопки на узкой desktop-ширине, clipping dropdown-фильтров. Для reduced-motion добавлено CSS-правило. Полный screen reader/axe-аудит и реальный мобильный device test не проводились.

## Готовая сборка и перезапуск

Проверен `scripts/dev.py serve-build`: FastAPI обслуживает index.html, hashed assets и deep link /estimates/:id, API/docs/storage продолжают работать, неизвестный /api route возвращает 404, а не SPA HTML. В Chrome на localhost:8010 проверены Sign in и список из трёх активных смет.

После stop/start локальная смета с двумя зонами и subtotal $12,550 сохранилась. В конце возвращён dev-режим: frontend 5190, backend 8010. Общий PostgreSQL при stop не выключается.

## Что не заявляется как проверенное

Реальный OpenAI/voice round-trip без ключа, production deployment, Docker build, внешние PostgreSQL providers, многопользовательская security-изоляция, полноценная автоматизация OS file picker, Excel recalculation engine и все сочетания редких pricing options. Текущие генераторы сохранены, а не объявлены новым Proposal Engine.
