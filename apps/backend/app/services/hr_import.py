"""Bounded, read-only XLSX import. Contact metadata never determines suitability."""
from io import BytesIO
from zipfile import ZipFile, BadZipFile
from hashlib import sha256
import re
from openpyxl import load_workbook

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 5000

def cell(value):
    text = '' if value is None else str(value).strip()
    if len(text)>4000:raise ValueError('A cell exceeds 4,000 characters. Shorten it before importing.')
    return text

def contact_flags(phone, email):
    flags = []
    if re.sub(r'[^\d+]', '', phone).startswith('+7'):
        flags.append('phone_plus7')
    if '@' in email and email.rsplit('@',1)[1].lower().endswith('.ru'):
        flags.append('email_ru')
    return flags

def parse_workbook(data):
    if len(data) > MAX_BYTES:
        raise ValueError('XLSX file must be smaller than 10 MB.')
    try:
        with ZipFile(BytesIO(data)) as z:
            if len(z.infolist())>2000 or sum(x.file_size for x in z.infolist())>80*1024*1024:
                raise ValueError('The workbook is too large after unpacking.')
        w = load_workbook(BytesIO(data), read_only=True, data_only=True, keep_links=False)
        sheets=[]
        total=0
        for sheet in w:
            it=iter(sheet.values)
            header=next(it,None)
            if not header: continue
            if len(header)>100: raise ValueError('Maximum 100 columns per sheet.')
            columns=[cell(x) or f'Column {i+1}' for i,x in enumerate(header)]
            if len(set(columns))!=len(columns): raise ValueError('Column names must be unique.')
            rows=[]
            for r in it:
                if not any(v is not None and str(v).strip() for v in r): continue
                total+=1
                if total>MAX_ROWS: raise ValueError('Maximum 5,000 non-empty rows per import.')
                rows.append({k:cell(v) for k,v in zip(columns,r)})
            if rows: sheets.append({'name':sheet.title,'columns':columns,'rows':rows})
        w.close()
        if not sheets: raise ValueError('No candidate rows found in this workbook.')
        return {'sheets':sheets}
    except (BadZipFile, KeyError, OSError) as e:
        raise ValueError('Cannot read this file. Upload a valid .xlsx workbook.') from e

def suggest_mapping(columns):
    def find(words):
        normalized={c.lower().replace('_',' '):c for c in columns}
        for word in words:
            if word in normalized:return normalized[word]
        return next((c for c in columns if any(w in c.lower().replace('_',' ') for w in words if w not in ('name',))), '')
    return {'name':find(['полное имя','имя','full name','name']),
            'email':find(['эл. адрес','email','e-mail']), 'phone':find(['оставьте, пожалуйста, ваш номер телефона','оставьте ваш контактный номер телефона','номер телефона','контактный номер','phone'])}

def prepare_rows(rows, mapping):
    valid=[]; invalid=0; test=0
    for row in rows:
        name=cell(row.get(mapping.get('name','')))
        email=cell(row.get(mapping.get('email',''))).lower()
        phone=cell(row.get(mapping.get('phone','')))
        if any('<test lead:' in v.lower() for v in row.values()): test+=1;continue
        if not name or not (email or phone): invalid+=1;continue
        # Per-vacancy contact identity; imported IDs remain in the original answers.
        identity=email or re.sub(r'\D','',phone)
        valid.append({'name':name[:240],'email':email[:320],'phone':phone[:100], 'answers':row,
                      'fingerprint':sha256(identity.encode()).hexdigest()})
    return valid, {'invalid':invalid,'test_rows':test}
