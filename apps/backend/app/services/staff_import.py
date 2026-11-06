"""Read only Main; retain original cells and document targets without external IO."""
from io import BytesIO
from hashlib import sha256
from datetime import date, datetime
from zipfile import ZipFile, BadZipFile
from urllib.parse import urlparse
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from app.services.hr_import import MAX_BYTES

COLUMNS = {
    'A': ('Name', 'ФИО'), 'B': ('Status', 'Статус'),
    'C': ('Start date', 'Дата выхода'), 'D': ('End date', 'Дата окончания'),
    'E': ('Position', 'Должность'), 'F': ('Phone / contact', 'Телефон / контакт'),
    'G': ('Department', 'Отдел'), 'H': ('Location', 'Местоположение'),
    'I': ('Employment', 'Занятость'), 'J': ('Working hours · Kyiv / Miami', 'Рабочее время · Киев / Майами'),
    'K': ('Email', 'Email'), 'L': ('Date of birth', 'Дата рождения'),
    'M': ('Documents', 'Документы'), 'N': ('Additional information · N', 'Дополнительные сведения · N'),
    'O': ('Additional information · O', 'Дополнительные сведения · O'),
    'P': ('Additional information · P', 'Дополнительные сведения · P'),
}


def safe_link(value):
    if not isinstance(value, str) or len(value) > 4000 or any(c in value for c in ('\r', '\n')):
        return False
    parsed = urlparse(value)
    return (parsed.scheme in ('http', 'https') and bool(parsed.netloc)) or (parsed.scheme == 'mailto' and '@' in parsed.path)


def text(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    value = '' if value is None else str(value)
    if len(value) > 20000:
        raise ValueError('A staff cell exceeds 20,000 characters.')
    return value


def parse_main(data):
    if len(data) > MAX_BYTES:
        raise ValueError('XLSX file must be smaller than 10 MB.')
    try:
        with ZipFile(BytesIO(data)) as z:
            if len(z.infolist()) > 2000 or sum(x.file_size for x in z.infolist()) > 80 * 1024 * 1024:
                raise ValueError('The workbook is too large after unpacking.')
        book = load_workbook(BytesIO(data), read_only=False, data_only=True, keep_links=False)
        try:
            if 'Main' not in book.sheetnames:
                raise ValueError('The workbook must contain a Main worksheet.')
            sheet = book['Main']
            if sheet.max_row > 10000 or sheet.max_column > 100:
                raise ValueError('Main exceeds the supported worksheet size.')
            headers = {get_column_letter(c.column): text(c.value) for c in sheet[1]}
            result = []
            for row in sheet.iter_rows(min_row=2):
                if not any(c.value is not None or c.hyperlink for c in row):
                    continue
                values = {get_column_letter(c.column): text(c.value) for c in row if c.value is not None or c.hyperlink}
                if not values.get('A', '').strip():
                    raise ValueError(f'Main row {row[0].row} has data but no employee name.')
                status = values.get('B', '').strip().lower()
                if status not in ('active', 'inactive', 'paused'):
                    raise ValueError(f'Main row {row[0].row} has an unknown status.')
                links = {get_column_letter(c.column): c.hyperlink.target for c in row if c.hyperlink and safe_link(c.hyperlink.target)}
                # Stable identity across repeat uploads; never overwrite later edits.
                identity = str(row[0].row) + ':' + values['A'].strip().casefold()
                result.append({'source_key': sha256(('Main:' + identity).encode()).hexdigest(),
                    'name': values['A'].strip(), 'status': status, 'title': values.get('E', '').strip(),
                    'department': values.get('G', '').strip(), 'fields': values, 'links': links,
                    'source': {'sheet': 'Main', 'row': row[0].row, 'headers': headers, 'values': values,
                               'sha256': sha256(data).hexdigest()}})
            if not result or len(result) > 1000:
                raise ValueError('Main must contain between 1 and 1,000 employees.')
            return result
        finally:
            book.close()
    except (BadZipFile, KeyError, OSError) as e:
        raise ValueError('Cannot read this file. Upload a valid .xlsx workbook.') from e


def initial_reporting(rows):
    """Owner-requested starting structure, NOT reporting lines from the workbook."""
    ceo = next((r for r in rows if 'kravchenko' in r['name'].lower() and any(n in r['name'].lower() for n in ('ihor', 'igor'))), None)
    if not ceo:
        return {}
    ceo['title'] = 'CEO'
    ceo['name'] = 'Igor Kravchenko'
    active = [r for r in rows if r['status'] == 'active' and r is not ceo]
    def leader(department, keywords):
        return next((r for keyword in keywords for r in active if r['department'] == department and keyword in r['title'].lower()), None)
    admin = leader('Administration', ['chief operating officer', 'director of strategic', 'director']) or ceo
    heads = {
        'HR': leader('HR', ['hr director', 'hr manager']),
        'Marketing': leader('Marketing', ['head of marketing', 'director']),
        'Sales': leader('Sales', ['director', 'team lead']),
        'Design': leader('Design', ['head of design']),
        'Finance': leader('Finance', ['head accountant', 'finance & accounting manager']),
        'Production': leader('Production', ['head of construction', 'project manager (senior)']),
    }
    managers = {}
    for r in rows:
        if r is ceo:
            managers[r['source_key']] = None
        elif r['department'] == 'Administration':
            managers[r['source_key']] = ceo['source_key']
        else:
            head = heads.get(r['department'])
            parent = admin if head is None or head is r else head
            managers[r['source_key']] = parent['source_key']
    return managers
