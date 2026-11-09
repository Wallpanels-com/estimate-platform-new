"""Bounded, read-only XLSX parsing and explicit application-column selection.
No AI calls, formulas, macros or external workbook links are executed.
"""
from io import BytesIO
from zipfile import ZipFile, BadZipFile
from hashlib import sha256
from itertools import islice, chain
import re
import unicodedata
from openpyxl import load_workbook

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 5000
MAX_COLUMNS = 100


def cell(value):
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = '' if value is None else str(value).strip()
    if len(text) > 4000:
        raise ValueError('A cell exceeds 4,000 characters. Shorten it before importing.')
    return text


def normalized(value):
    text = unicodedata.normalize('NFKC', str(value)).casefold().replace('_', ' ')
    return re.sub(r'\s+', ' ', re.sub(r"[^\w\s@]+", ' ', text)).strip()


ALIASES = {
    'name': ['full name', 'fullname', 'contact name', 'candidate name', 'полное имя', 'повне ім я', 'имя и фамилия', 'прізвище ім я', 'прізвище та ім я', 'ім я та прізвище', 'піб', 'фио', 'first name', 'firstname', 'ім я', 'імя', 'имя', 'name'],
    'last_name': ['last name', 'lastname', 'surname', 'family name', 'фамилия', 'прізвище'],
    'email': ['email', 'e mail', 'email address', 'ел адреса', 'эл адрес', 'електронна пошта', 'електронна адреса', 'электронная почта', 'пошта', 'почта'],
    'phone': ['phone number', 'phone', 'mobile number', 'mobile', 'telephone', 'номер телефону', 'номер телефона', 'контактний номер', 'контактный номер', 'телефон'],
    'telegram': ['telegram username', 'telegram', 'telegram handle', 'телеграм', 'tg username'],
}
TECHNICAL = {
    'id', 'lead id', 'created time', 'created at', 'updated time', 'updated at',
    'lead status', 'priority', 'platform', 'is organic', 'organic', 'source id',
    'ad id', 'ad name', 'adset id', 'adset name', 'ad set id', 'ad set name',
    'campaign id', 'campaign name', 'form id', 'form name', 'tracking id',
    'импортировано', 'дата создания', 'дата створення',
}


def technical_column(column):
    text = normalized(column)
    return text in TECHNICAL or bool(re.match(r'^(utm |tracking |fbclid$|gclid$|column \d+$)', text))


def suggest_mapping(columns, rows=None):
    labels = {column: normalized(column) for column in columns}
    def find(role):
        for alias in ALIASES[role]:
            for column, label in labels.items():
                if label == alias and not technical_column(column):
                    return column
        # Short tokens such as name must never match ad_name or a question about software names.
        for column, label in labels.items():
            if technical_column(column):
                continue
            if any(len(alias) >= 5 and re.search(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', label) for alias in ALIASES[role] if alias not in ('full name', 'first name', 'last name')):
                return column
        return ''
    mapping = {key: find(key) for key in ALIASES}
    # A full-name column already includes the surname. Keep the separate
    # surname available for manual mapping without appending it twice by default.
    if labels.get(mapping['name']) not in ('first name', 'firstname', 'ім я', 'імя', 'имя'):
        mapping['last_name'] = ''
    # Unknown email/phone headers can be inferred from their actual cell formats;
    # never treat a numeric lead/ad ID as a telephone number.
    sample = (rows or [])[:20]
    for role in ('email', 'phone'):
        if mapping[role] or not sample:
            continue
        for column in columns:
            if column in mapping.values() or technical_column(column):
                continue
            values = [r.get(column, '').strip() for r in sample if r.get(column, '').strip()]
            pattern = r'(?:mailto:)?[^\s@]+@[^\s@]+\.[^\s@]+' if role == 'email' else r'(?:p:)?(?:\+|00)[\d ()-]{7,22}'
            if values and sum(bool(re.fullmatch(pattern, v, re.I)) for v in values) / len(values) >= .8:
                mapping[role] = column
                break
    return mapping


def suggested_questions(columns, mapping, rows=None):
    mapped = {v for v in mapping.values() if v}
    return [c for c in columns if c not in mapped and not technical_column(c)
            and (not rows or any(str(row.get(c, '')).strip() for row in rows))]


def parse_workbook(data):
    if len(data) > MAX_BYTES:
        raise ValueError('XLSX file must be smaller than 10 MB.')
    workbook = None
    try:
        with ZipFile(BytesIO(data)) as z:
            if len(z.infolist()) > 2000 or sum(x.file_size for x in z.infolist()) > 80 * 1024 * 1024:
                raise ValueError('The workbook is too large after unpacking.')
        workbook = load_workbook(BytesIO(data), read_only=True, data_only=True, keep_links=False)
        sheets, total = [], 0
        for sheet in workbook:
            iterator = iter(sheet.values)
            leading = list(islice(iterator, 20))
            nonempty = [(i, row) for i, row in enumerate(leading) if any(v is not None and str(v).strip() for v in row)]
            if not nonempty:
                continue
            def header_score(entry):
                labels = [cell(x) for x in entry[1] if x is not None]
                m = suggest_mapping(labels)
                return sum(bool(m[k]) for k in ('name', 'email', 'phone', 'telegram'))
            index, header = max(nonempty, key=header_score)
            raw_rows = []
            for physical, row in enumerate(chain(leading[index + 1:], iterator)):
                if physical > 50000:
                    raise ValueError('The worksheet contains too many empty rows. Remove unused rows and try again.')
                if not any(v is not None and str(v).strip() for v in row):
                    continue
                total += 1
                if total > MAX_ROWS:
                    raise ValueError('Maximum 5,000 non-empty rows per import.')
                raw_rows.append(row)
            if not raw_rows:
                continue
            # Drop empty formatting columns; preserve populated columns without a header.
            used = sorted({i for row in [header, *raw_rows] for i, v in enumerate(row) if v is not None and str(v).strip()})
            if used and used[-1] >= MAX_COLUMNS:
                raise ValueError('Maximum 100 columns per sheet.')
            columns, used_names = [], set()
            for i in used:
                original = cell(header[i] if i < len(header) else None) or f'Column {i + 1}'
                name, suffix = original, 2
                while name in used_names:
                    name = f'{original} ({suffix})'
                    suffix += 1
                used_names.add(name)
                columns.append(name)
            rows = [{name: cell(row[i] if i < len(row) else None) for name, i in zip(columns, used)} for row in raw_rows]
            sheets.append({'name': sheet.title, 'columns': columns, 'rows': rows, 'header_row': index + 1})
        if not sheets:
            raise ValueError('No candidate rows found in this workbook.')
        return {'sheets': sheets}
    except (BadZipFile, KeyError, OSError) as error:
        raise ValueError('Cannot read this file. Upload a valid .xlsx workbook.') from error
    finally:
        if workbook is not None:
            workbook.close()


def contact_flags(phone, email):
    flags = []
    if re.sub(r'[^\d+]', '', phone).startswith('+7'):
        flags.append('phone_plus7')
    if '@' in email and email.rsplit('@', 1)[1].lower().endswith('.ru'):
        flags.append('email_ru')
    return flags


def row_keys(row):
    keys = {row['fingerprint']} if row.get('fingerprint') else set()
    if row.get('email'):
        keys.add('email:' + row['email'].strip().casefold())
    digits = re.sub(r'\D', '', row.get('phone') or '')
    if len(digits) >= 7:
        keys.add('phone:' + (digits[2:] if digits.startswith('00') else digits))
    if row.get('telegram_username'):
        keys.add('telegram:' + row['telegram_username'].casefold())
    return keys


def prepare_rows(rows, mapping, answer_columns=None):
    from app.services.telegram_contacts import normalize_username
    valid, invalid, test = [], 0, 0
    for row in rows:
        if any('<test lead:' in v.lower() for v in row.values()):
            test += 1
            continue
        name = cell(row.get(mapping.get('name', '')))
        last = cell(row.get(mapping.get('last_name', '')))
        if last and mapping.get('last_name') != mapping.get('name'):
            name = f'{name} {last}'.strip()
        email = re.sub(r'^(?:mailto:|e:)', '', cell(row.get(mapping.get('email', ''))), flags=re.I).strip().lower()
        phone = re.sub(r'^p:', '', cell(row.get(mapping.get('phone', ''))), flags=re.I).strip()
        handle = None
        if mapping.get('telegram'):
            try:
                handle = normalize_username(cell(row.get(mapping['telegram'])))
            except ValueError:
                pass
        if not name or not (email or phone or handle):
            invalid += 1
            continue
        identity = email or re.sub(r'\D', '', phone) or (handle or phone).casefold()
        item = {'name': name[:240], 'email': email[:320], 'phone': phone[:100],
                'answers': dict(row) if answer_columns is None else {k: row.get(k, '') for k in answer_columns if row.get(k, '').strip()},
                'fingerprint': sha256(identity.encode()).hexdigest()}
        if handle:
            item['telegram_username'] = handle
        valid.append(item)
    return valid, {'invalid': invalid, 'test_rows': test}
