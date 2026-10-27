from copy import deepcopy
from decimal import Decimal
import os,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'apps/backend'))
os.environ.setdefault('DATABASE_URL','postgresql+asyncpg://unused:unused@127.0.0.1:55432/unused')
os.environ.setdefault('SECRET_KEY','unit-tests-only')
from fastapi import HTTPException
from pydantic import ValidationError
from app.schemas.pricebook import CategoryInput,ItemInput,CATEGORY_ICONS
from app.services.pricebook_service import category_change,item_change,quote,categories,legacy_config,revision,validate_legacy
from app.services.pricing_config import DEFAULT_PRICING_CONFIG
from app.services.calculator_registry import definitions,calculate

class PriceBookContracts(unittest.TestCase):
    def test_icon_library_and_saved_category_contract(self):
        self.assertGreaterEqual(len(CATEGORY_ICONS), 75)
        for key in CATEGORY_ICONS:
            self.assertEqual(CategoryInput(name='Category',icon=key).icon,key)
        with self.assertRaises(ValidationError):CategoryInput(name='Category',icon='unknown-icon')
        config,ident=category_change(DEFAULT_PRICING_CONFIG,CategoryInput(name='Lighting',icon='ceiling-light',description='Existing scope'))
        saved=next(c for c in categories(config) if c['id']==ident)
        self.assertEqual(saved['icon'],'ceiling-light')
        self.assertEqual(saved['description'],'Existing scope')

    def setUp(self):
        self.config=deepcopy(DEFAULT_PRICING_CONFIG)
        self.config,self.cid=category_change(self.config,CategoryInput(name='Acoustic work',name_ru='Акустические работы'))
    def test_category_create_rename_and_conflict(self):
        self.assertEqual(legacy_config(self.config),DEFAULT_PRICING_CONFIG)
        cat=next(c for c in categories(self.config) if c['id']==self.cid)
        self.assertIsNone(cat['calculator_id'])
        changed,_=category_change(self.config,CategoryInput(name='Acoustic finishes',expected_version=1),self.cid)
        self.assertEqual(next(c for c in categories(changed) if c['id']==self.cid)['version'],2)
        with self.assertRaises(HTTPException) as error:category_change(changed,CategoryInput(name='Stale',expected_version=1),self.cid)
        self.assertEqual(error.exception.status_code,409)
        with self.assertRaises(HTTPException):category_change(self.config,CategoryInput(name='wall PANELS'))
        with self.assertRaises(HTTPException):category_change(self.config,CategoryInput(name='Walls',archived=True),'wall')
    def test_subcategories_move_archive_restore_and_quote(self):
        config,child=category_change(self.config,CategoryInput(name='Slats',parent_id=self.cid))
        config,grandchild=category_change(config,CategoryInput(name='Oak',parent_id=child))
        config,item=item_change(config,ItemInput(category_id=grandchild,name='Oak panels',unit='SF',unit_price='12.50'))
        snapshot=quote(config,item['id'],Decimal('4'))
        self.assertEqual(snapshot['total_price'],'50.00')
        # Hiding a parent must prevent quoting and restoring active items under it.
        config,_=category_change(config,CategoryInput(name='Acoustic work',archived=True,expected_version=1),self.cid)
        with self.assertRaises(HTTPException):quote(config,item['id'],Decimal('4'))
        with self.assertRaises(HTTPException):item_change(config,ItemInput(category_id=grandchild,name='Invalid',unit_price='12'))
        self.assertEqual(next(c for c in categories(config) if c['id']==grandchild)['archived'],False)
        config,_=category_change(config,CategoryInput(name='Acoustic work',expected_version=2),self.cid)
        self.assertEqual(quote(config,item['id'],Decimal('4')),snapshot)
        # Reparenting a custom subtree retains items and formulas.
        config,_=category_change(config,CategoryInput(name='Slats renamed',parent_id='wall',expected_version=1),child)
        self.assertEqual(next(c for c in categories(config) if c['id']==child)['parent_id'],'wall')
        self.assertEqual(quote(config,item['id'],Decimal('4')),snapshot)
        self.assertEqual(legacy_config(config),DEFAULT_PRICING_CONFIG)

    def test_subcategory_cycles_missing_parent_and_sibling_names(self):
        config,child=category_change(self.config,CategoryInput(name='Oak',parent_id=self.cid))
        for payload,ident in [
            (CategoryInput(name='Acoustic work',parent_id=child),self.cid),
            (CategoryInput(name='Oak',parent_id=child),child),
            (CategoryInput(name='Bad',parent_id='missing'),None),
            (CategoryInput(name='Wall panels',parent_id=child),'wall'),
            (CategoryInput(name='oak',parent_id=self.cid),None),
        ]:
            with self.assertRaises(HTTPException):category_change(config,payload,ident)
        # Same material group name is valid under a different parent.
        config,other=category_change(config,CategoryInput(name='Oak',parent_id='wall'))
        self.assertNotEqual(other,child)
        config,_=category_change(config,CategoryInput(name='Acoustic work',archived=True),self.cid)
        with self.assertRaises(HTTPException):category_change(config,CategoryInput(name='Hidden child',parent_id=child))

    def test_quote_unit_fixed_unpriced_and_snapshot(self):
        config,item=item_change(self.config,ItemInput(category_id=self.cid,name='Acoustic installation',name_ru='Монтаж',description='Scope',unit='SF',unit_price='12.55',parameters=[{'name':'Finish','value':'Oak'}]))
        snapshot=quote(config,item['id'],Decimal('3'))
        self.assertEqual(snapshot['total_price'],'37.65');self.assertEqual(snapshot['name'],'Acoustic installation')
        self.assertEqual(snapshot['description'],'Scope\nFinish: Oak')
        config,_=item_change(config,ItemInput(category_id=self.cid,name='New name',unit_price='25',expected_version=1),item['id'])
        self.assertEqual(snapshot['total_price'],'37.65')
        for mode,rate,total in [('fixed','150','150.00'),('unpriced',None,'0.00')]:
            config,other=item_change(config,ItemInput(category_id=self.cid,name=mode,pricing_mode=mode,unit_price=rate))
            result=quote(config,other['id'],Decimal('7'))
            self.assertEqual(result['total_price'],total)
            self.assertEqual(result['is_tbd'],mode=='unpriced')
            if mode=='fixed':self.assertEqual(result['quantity'],'1')
    def test_archive_hides_quotes_and_keeps_records(self):
        config,item=item_change(self.config,ItemInput(category_id=self.cid,name='Service',unit_price='20'))
        config,_=category_change(config,CategoryInput(name='Acoustic work',archived=True,expected_version=1),self.cid)
        with self.assertRaises(HTTPException):quote(config,item['id'],Decimal('1'))
        config,_=category_change(config,CategoryInput(name='Acoustic work',expected_version=2),self.cid)
        self.assertEqual(quote(config,item['id'],Decimal('1'))['total_price'],'20.00')
        config,_=item_change(config,ItemInput(category_id=self.cid,name='Service',unit_price='20',archived=True,expected_version=1),item['id'])
        with self.assertRaises(HTTPException):quote(config,item['id'],Decimal('1'))
    def test_validation_and_legacy_rules(self):
        for rate in ['-1','NaN','Infinity','1.234','10000000000','1e100']:
            with self.assertRaises(ValidationError):ItemInput(category_id=self.cid,name='Invalid',unit_price=rate)
        with self.assertRaises(ValidationError):ItemInput(category_id=self.cid,name='Missing price')
        bad=deepcopy(DEFAULT_PRICING_CONFIG);del bad['wall']['base_rates']['small']
        with self.assertRaises(HTTPException):validate_legacy(bad)
        validate_legacy(DEFAULT_PRICING_CONFIG)
        self.assertEqual(revision(self.config),revision(DEFAULT_PRICING_CONFIG))
        self.assertEqual([r['id'] for r in definitions()],['wall','cabinet','mirror'])
        self.assertEqual(calculate('wall',self.config,square_footage=100,addons_sf=['led'])['total'],6000)
        self.assertEqual(calculate('cabinet',self.config,linear_footage=2,cabinet_type='kitchen_island')['total'],2400)
        self.assertEqual(calculate('mirror',self.config,square_footage=20)['total'],2600)
