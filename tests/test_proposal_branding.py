"""Approved title, selected cover media and Arial; existing quote data stays intact."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'apps/backend'),str(ROOT/'tests')]
from pypdf import PdfReader
from PIL import Image
from test_final_layout import estimate, zone
from app.services import final_estimate_layout as final
from app.services import proposal_style as style
from app.services import pre_estimate_v2 as pre
from datetime import date
from types import SimpleNamespace as O

class Branding(unittest.TestCase):
    def test_fixed_pre_title_is_the_exact_uploaded_image(self):
        with TemporaryDirectory() as directory:
            est=estimate([zone(count=1)]);est.prepared_by='Employee';est.estimate_date=date(2026,10,31)
            for item in est.line_items:item.calc_type='sf';item.unit='SF';item.zone_id=est.zones[0].id
            before=deepcopy(est)
            path=Path(directory)/'pre.pdf';pre.generate_pre_estimate(est,path)
            pages=PdfReader(path).pages
            first=pages[0]
            self.assertIn("Project Overview", pages[1].extract_text())
            import re
            for page in pages:
                text=page.extract_text()
                self.assertNotIn("Prepared by", text)
                self.assertIsNone(re.search(r"^\d{2} / \d{2}$", text, re.MULTILINE))
            with Image.open(style.PRE_TITLE) as source:
                embedded=first.images[0].image.convert('RGB')
                self.assertEqual(embedded.tobytes(),source.convert('RGB').tobytes())
            self.assertEqual(first.extract_text().strip(),'')
            self.assertEqual(est,before)

    def test_final_cover_uses_selected_T_photo_without_changing_zone_selection(self):
        with TemporaryDirectory() as directory:
            folder=Path(directory)
            for name,color in [('one','red'),('two','blue')]:Image.new('RGB',(80,120),color).save(folder/f'{name}.png')
            photos=[O(id=name,slot=n,file_path=str(folder/f'{name}.png')) for n,name in enumerate(('one','two'),1)]
            est=estimate([zone(count=1,images=photos)]);est.cover_image_id='two';est.pdf_layout={'final_zone_photos':{str(est.zones[0].id):1}}
            before=deepcopy(est);path=folder/'final.pdf';final.generate_final_client(est,path)
            first=PdfReader(path).pages[0]
            small=next(i.image for i in first.images if i.image.size==(80,120))
            self.assertEqual(small.convert('RGB').getpixel((0,0)),(0,0,255))
            self.assertEqual(est,before)
            reader=PdfReader(path)
            names={str(f.get_object().get('/BaseFont')) for p in reader.pages for f in p['/Resources'].get('/Font',{}).get_object().values()}
            self.assertTrue(any('Arial' in name for name in names))
            self.assertFalse(any('Montserrat' in name for name in names))
