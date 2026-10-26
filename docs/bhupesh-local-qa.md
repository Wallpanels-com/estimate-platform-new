# BHUPESH — локальная проверка, 22 октября 2026

Позднее по отдельной просьбе пользователя добавлена [QA-смета с 10 зонами и разными фото](pdf-media-qa.md). Утверждение ниже об одном проекте относится к исходной проверке; BHUPESH сохранён без изменений.

Открыть: http://localhost:5190/estimates/6e7ecce2-2475-4562-82a7-dddbf2144a64

В обычном списке Estimates один проект: BHUPESH - Final Estimate.
Client BHUPESH; type Final; prepared by Kit; date 2026-10-22; markup/discount 0%.
Project name/address, contacts, budget и остальные неизвестные поля не заполнялись.

| Зона | Позиций | Сумма |
|---|---:|---:|
| B Laundry | 3 | $17,750 |
| B Walk in Closet | 5 | $19,850 |
| B BEDROOM NO. 1 | 4 | $28,400 |
| Staircase walls | 2 | $23,300 |
| B Hallway | 1 | Pricing pending |
| Расчётная база | 15 | **$89,300** |

Closet: General $18,850 + Mirrors $1,000. Delivery & Installation — фиксированные
$1,000, quantity/unit/rate не указаны и оставлены пустыми. Staircase LED сохранён как
Manual: quantity 100, rate $35, total $3,500; неуказанная единица не выдумана.
Hallway: Wall 1, 18 ft W x 10 ft H, is_tbd=true, unit_price=null, total=0;
площадь 180 SF не превращается в выдуманную стоимость. Дополнительных услуг нет.

## Backup и происхождение данных

До изменений выполнены pg_dump локальной базы и копирование всего storage:
`.local/backups/before-bhupesh-20261022T145600Z/`.

В активном списке были только три известные demo-сметы из предыдущих локальных QA.
Они перенесены в восстанавливаемую Trash. Неизвестных активных записей не было;
отдельная QA-база не понадобилась. Корпоративные/удалённые базы не использовались.
Исходные скачанные репозитории не изменены.

Полный ввод: `tests/fixtures/bhupesh.json`. Скрипт `scripts/prepare_bhupesh.py`
создаёт записи через существующие localhost API и отказывается перезаписывать
BHUPESH или работать при наличии неизвестных активных проектов. Генераторы не
содержат данных BHUPESH: они читают текущий Estimate и его связанные модели.

## Предоставленный план

Использован ровно предоставленный PNG 829×372, без изменения пикселей:
`tests/fixtures/bhupesh-reference.png`. Этот общий reference прикреплён к каждой
зоне в slot 1, что прямо разрешено запросом. Это пример плана, а не пять разных
оригинальных фотографий. В PDF он подписан Project reference. Отдельных оригинальных
BHUPESH-планов в прежнем локальном storage не было; прежние картинки были QA.

Preview, PDF и thumbnails используют contain: соотношение сторон сохраняется,
изображение не растягивается и не обрезается. Галерея на 2–4 изображения выбирает
композицию по их пропорциям. Для отсутствующих изображений есть отдельный текстовый
layout без upload-placeholder. Во время QA новые фотографии не генерировались.

## Новый Pre-Estimate

`app/services/pre_estimate_service.py` — отдельный ReportLab/Pillow renderer:
1152×648 pt (16:9), встроенные локальные Montserrat Regular/Medium/Bold, белый фон,
графит и сдержанный бронзовый акцент. Отдельного logo SVG/PNG в репозиториях нет;
использован typographic wordmark WALLPANELS.COM / By VERONA HOME из существующего
генератора, без квадратной UI-иконки.

В BHUPESH 8 слайдов: cover, overview, пять зон, investment summary. Base $89,300;
диапазон 90–115% применён один раз: $80,370–$102,695. Предварительная стоимость явно
отделена от договора/invoice. Hallway показывает Pricing pending вместо большого $0.

Пагинация измеряет текст, переносит длинные слова и добавляет continuation slides.
Генератор работает с 1/5/10 и более зонами; длинные client/zone/section/item names
полностью переносятся. Шрифт описаний не уменьшается для помещения контента.

`GET /api/v1/pdf/:id/pre-estimate` создаёт preview без изменения Estimate.type,
updated_at, цен или полей. `?download=true` задаёт attachment. Временный PDF удаляется
после ответа. Preview в Builder получает PDF по авторизованному запросу и показывает
его в native PDF viewer; Download Pre-Estimate PDF использует тот же Blob.

Старый `pdf_service.py` и Final PDF не переписывались. Corporate Final Proposal /
company slides не реализовывались — это отдельный будущий этап.

## Project Passport

Сохранены openpyxl, исходный template, BRIEF INFORMATION, DETAILED PROJECT ESTIMATE,
все колонки, merges, стили, cost-поля, Planned/Fact/Variance, формулы и ссылки.
Изменения ограничены TBD-ячейкой для неоценённых строк, IFERROR для процентов при
нулевой базе и fullCalcOnLoad/forceFullCalc. Шаблон не переименован и не изменён.

Для BHUPESH subtotal-ячейки I23/I30/I36/I40/I43 дают $89,300 в I44; M5 и J58
ссылаются на актуальную grand-total ячейку. При 10 зонах/100 строках ссылки и весь
внутренний cost-блок также сохраняются. Неизвестные Material Code/контакты/cost inputs
пустые. Значения не подставляются из тестовых констант при экспорте.

Имя для всех клиентов: Project passport - Wallpanels - <Client>.xlsx, без «5.»
и в Content-Disposition backend, и в frontend download.

## Выполненные проверки

- После перезапуска локального backend/frontend все 15 позиций, quantity, rate,
  totals, описания, sections, date, prepared_by и type совпали с вводом пользователя.
- Обычный список содержит ровно BHUPESH. Все subtotal и Grand Total совпадают между
  API, Builder и экспортами с учётом Pre-range.
- API exports не изменили saved Final Estimate или Price Book; сравнивался весь
  JSON до/после. Для пяти фото проверен SHA256 исходного файла.
- 10 Python tests: source/pricing contracts, template preservation, динамические
  formulas, расширение таблицы, длинный scope, contain для 1–4 фото, no-photo PDF.
- 27 прежних Quick parity fixtures проходят; 45 reference-файлов не изменены.
- TypeScript/Vite build и frontend format check проходят.
- XLSX открыт и отрисован совместимым artifact-tool engine. После recalculation:
  [17750, 19850, 28400, 23300, 0] → 89300. Ошибок формул не найдено.
- Пробные planned cost 200 / fact 250 дали planned profit 89100 / fact profit 89050,
  затем inputs восстановлены в памяти. При нулевой базе percentage formulas дают 0.
  Исходный XLSX не переписывался этим движком: сохранены native template features.
- Все 8 страниц настоящего PDF визуально проверены. 16:9 у каждой страницы, изображения
  имеют полный исходный размер 829×372, весь фактически набранный текст — Montserrat.
- Проверены отдельные PDF без фото (8 страниц), с 1 зоной (4), с 10 зонами (15),
  длинным scope (17), полностью pending зоной (4), markup/discount (4). Выхода текста
  за страницу нет. PDF без фото проверен визуально; $0 у pending-only не показывается.
- Legacy Final PDF генерируется отдельно в прежнем landscape Letter и с базой $89,300.
- Chrome на обычном desktop и 1280×800: preview/dialog/footer помещаются без horizontal overflow; один проект в списке, все пять зон, TBD Hallway, Final сохранён, Preview
  открывается настоящим 8-страничным PDF, кнопки Final PDF / XLSX завершают запросы.

Evidence: `.local/qa/bhupesh/api-verification.json`, `pdf-verification.json`,
`xlsx-recalculation.json`, page PNGs и Chrome screenshots.

## Как пользоваться

Открыть BHUPESH. В правом Summary:

1. Project passport (XLSX) — скачать актуальный Excel.
2. Preview Pre-Estimate — открыть документ, затем Download Pre-Estimate PDF.
3. Download Final PDF — прежний Final export.

После согласованного изменения Preview/Download зависят от выбранного режима:
Pre-estimate открывает новый Pre PDF, Final — сохранённый Final renderer.
Сайт оставлен на localhost:5190,
API на localhost:8010. Ничего не commit/push/deploy.

Ограничения проверки: Excel/LibreOffice как desktop-приложения не запускались;
проверены openpyxl и compatible recalculation/render engine. Excel запрошен полный
пересчёт при открытии. Для примера используется один общий пользовательский план;
для разных планов зон можно заменить slot 1 через существующий Photos UI.
