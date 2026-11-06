"""Staff import retains Main and source provenance without importing other sheets."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/backend'))
from io import BytesIO
from datetime import datetime
import unittest
from openpyxl import Workbook
from app.services.staff_import import parse_main, initial_reporting


def workbook():
    w=Workbook();s=w.active;s.title='Main'
    s.append(['Name','Status','Start','End','Role','Phone','Department'])
    s.append(['Kravchenko Ihor','Active',datetime(2024,1,3),None,'Co-founder','+15550100000','Administration'])
    s.append(['Operations lead','Active',None,None,'Chief Operating Officer (COO)',None,'Administration'])
    s.append(['Sales lead','Active',None,None,'Director',None,'Sales'])
    s.append(['Sales employee','Paused',None,None,'Sales manager',None,'Sales'])
    s['M5']='Documents';s['M5'].hyperlink='https://example.com/document';s['O5']='Private additional details'
    w.create_sheet('Do not import').append(['SHOULD NOT BE IMPORTED'])
    b=BytesIO();w.save(b);return b.getvalue()


class StaffTests(unittest.TestCase):
    def test_main_and_all_cells(self):
        rows=parse_main(workbook());self.assertEqual(len(rows),4)
        self.assertEqual(rows[0]['fields']['C'],'2024-01-03')
        self.assertEqual(rows[3]['links']['M'],'https://example.com/document')
        self.assertEqual(rows[3]['fields']['O'],'Private additional details')
        self.assertEqual(rows[3]['source']['row'],5)
        self.assertTrue(all(r['source']['sheet']=='Main' for r in rows))

    def test_initial_editable_relationships_keep_source(self):
        rows=parse_main(workbook());parents=initial_reporting(rows)
        self.assertEqual(rows[0]['title'],'CEO')
        self.assertEqual(rows[0]['name'],'Igor Kravchenko')
        self.assertEqual(rows[0]['source']['values']['E'],'Co-founder')
        self.assertEqual(rows[0]['source']['values']['A'],'Kravchenko Ihor')
        self.assertIsNone(parents[rows[0]['source_key']])
        self.assertEqual(parents[rows[2]['source_key']],rows[1]['source_key'])
        self.assertEqual(parents[rows[3]['source_key']],rows[2]['source_key'])

    def test_missing_main_or_invalid_status_is_atomic(self):
        w=Workbook();b=BytesIO();w.save(b)
        with self.assertRaisesRegex(ValueError,'Main'):parse_main(b.getvalue())
        w.active.title='Main';w.active.append(['Name','Status']);w.active.append(['Example','Unknown']);b=BytesIO();w.save(b)
        with self.assertRaisesRegex(ValueError,'unknown status'):parse_main(b.getvalue())

    def test_source_key_unchanged_by_initial_reporting(self):
        rows=parse_main(workbook());key=rows[0]['source_key'];initial_reporting(rows)
        self.assertEqual(key,parse_main(workbook())[0]['source_key'])

class StaffSourceRetentionTests(unittest.TestCase):
    def test_same_names_are_distinct_rows_and_mail_links_survive(self):
        w=Workbook();s=w.active;s.title='Main';s.append(['Name','Status'])
        s.append(['Same Name','Active']);s.append(['Same Name','Inactive'])
        s['K2']='mail@example.com';s['K2'].hyperlink='mailto:mail@example.com'
        b=BytesIO();w.save(b);rows=parse_main(b.getvalue())
        self.assertEqual(len(rows),2)
        self.assertNotEqual(rows[0]['source_key'],rows[1]['source_key'])
        self.assertEqual(rows[0]['links']['K'],'mailto:mail@example.com')
