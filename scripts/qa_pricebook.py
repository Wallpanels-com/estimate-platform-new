"""Loopback-only managed Price Book integration checks. Never downloads exports."""
from pathlib import Path
from decimal import Decimal
import argparse,hashlib,json,httpx
from qa_credentials import qa_credentials
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'.local/qa/pricebook';OUT.mkdir(parents=True,exist_ok=True)
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('phase',choices=['prepare','verify','cleanup']);phase=parser.parse_args().phase
c=httpx.Client(base_url='http://127.0.0.1:8010/api/v1',timeout=30,trust_env=False)
email,password=qa_credentials();response=c.post('/auth/login',json={'email':email,'password':password});response.raise_for_status();c.headers['Authorization']='Bearer '+response.json()['access_token']
checks=[]
def call(method,path,status=200,**kwargs):
 r=c.request(method,path,**kwargs);assert r.status_code==status,f'{method} {path}: {r.status_code} {r.text[:400]}'
 checks.append([method,path,r.status_code]);return r.json() if r.content else None
def body(entry):return {k:v for k,v in entry.items() if k not in ('id','version','builtin','calculator_id') }|{'expected_version':entry['version']}
def core(config):return {k:v for k,v in config.items() if k!='_catalog_v1'}
statefile=OUT/'state.json'
if phase=='prepare':
 cfg=call('GET','/pricing/config');book=call('GET','/pricing/catalog');cat=next(x for x in book['categories'] if x['name']=='QA — Custom Finishes')
 old={e['id']:call('GET','/estimates/'+e['id']) for e in call('GET','/estimates') if not (e.get('title') or '').startswith('QA Price Book')}
 item=next(x for x in book['items'] if x['category_id']==cat['id']);oldversion=item['version']
 item=call('PUT','/pricing/catalog/items/'+item['id'],json=body(item)|{'unit_price':'15.00'})
 call('PUT','/pricing/catalog/items/'+item['id'],409,json=body(item)|{'expected_version':oldversion})
 call('POST','/pricing/catalog/items',422,json={'category_id':cat['id'],'name':'Invalid','unit_price':'-1'})
 fixed=call('POST','/pricing/catalog/items',201,json={'category_id':cat['id'],'name':'QA Custom material allowance','name_ru':'QA Материал с фиксированной стоимостью','description':'Local QA example.','kind':'material','pricing_mode':'fixed','unit_price':'125.00'})
 unpriced=call('POST','/pricing/catalog/items',201,json={'category_id':cat['id'],'name':'QA Site finishing service','name_ru':'QA Услуга с ценой после осмотра','kind':'service','pricing_mode':'unpriced'})
 beforebook=call('GET','/pricing/catalog')
 saved=call('PUT','/pricing/config',json={'config':cfg['config'],'expected_revision':cfg['revision']})
 assert call('GET','/pricing/catalog')==beforebook,'Saving stale legacy config must retain all catalog entries'
 call('PUT','/pricing/config',409,json={'config':cfg['config'],'expected_revision':'obsolete'})
 call('POST','/pricing/config/reset');assert call('GET','/pricing/catalog')==beforebook,'Reset cannot erase catalog'
 call('PUT','/pricing/config',json={'config':cfg['config']})
 assert core(call('GET','/pricing/config')['config'])==core(cfg['config'])
 for kind,payload,total in [('wall',{'square_footage':100,'addons_sf':['led']},6000),('cabinet',{'linear_footage':2,'cabinet_type':'kitchen_island'},2400),('mirror',{'square_footage':20},2600)]:
  assert call('POST','/pricing/calc/'+kind,json=payload)['total']==total
 assert [x['id'] for x in call('GET','/pricing/calculators')['calculators']]==['wall','cabinet','mirror']
 est=call('POST','/estimates',201,json={'type':'pre','title':'QA Price Book — local integration only','client_name':'QA Price Book','prepared_by':'Local QA'})
 q=call('POST','/pricing/catalog/items/'+fixed['id']+'/quote',json={'quantity':'4'});assert Decimal(q['total_price'])==125 and q['quantity']=='1'
 line=call('POST',f'/estimates/{est["id"]}/line-items',201,json=q|{'zone_id':est['zones'][0]['id']})
 q=call('POST','/pricing/catalog/items/'+unpriced['id']+'/quote',json={'quantity':'2'});assert q['is_tbd'] and q['unit_price'] is None
 call('POST',f'/estimates/{est["id"]}/line-items',201,json=q|{'zone_id':est['zones'][0]['id']})
 call('PUT','/pricing/catalog/items/'+fixed['id'],json=body(fixed)|{'unit_price':'150.00'})
 reread=call('GET','/estimates/'+est['id']);assert next(i for i in reread['line_items'] if i['id']==line['id'])['total_price']=='125.00','Saved estimate must retain copied price'
 archived=call('PUT','/pricing/catalog/items/'+unpriced['id'],json=body(unpriced)|{'archived':True})
 call('POST','/pricing/catalog/items/'+unpriced['id']+'/quote',409,json={'quantity':'1'})
 call('PUT','/pricing/catalog/items/'+unpriced['id'],json=body(archived)|{'archived':False})
 state={'category_id':cat['id'],'item_id':item['id'],'estimate_id':est['id'],'old_estimates':old,'original_rates':core(cfg['config']),'prepared_book':call('GET','/pricing/catalog')}
 statefile.write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n')
elif phase=='verify':
 state=json.loads(statefile.read_text());assert call('GET','/pricing/catalog')==state['prepared_book'],'Catalog must survive restart'
 assert core(call('GET','/pricing/config')['config'])==state['original_rates']
 for ident,snapshot in state['old_estimates'].items():assert call('GET','/estimates/'+ident)==snapshot,'Existing estimate changed'
 est=call('GET','/estimates/'+state['estimate_id']);assert Decimal(est['subtotal'])>=125
 print('Persistence after application restart and existing estimates verified.')
else:
 state=json.loads(statefile.read_text());book=call('GET','/pricing/catalog');cat=next(x for x in book['categories'] if x['id']==state['category_id'])
 assert cat['name']=='QA — Custom Finishes (verified)','UI category rename was not saved'
 item=next(x for x in book['items'] if x['id']==state['item_id']);assert Decimal(item['unit_price'])==16
 est=call('GET','/estimates/'+state['estimate_id']);line=next(x for x in est['line_items'] if x['name']=='QA Acoustic finishing installation')
 assert Decimal(line['quantity'])==3 and Decimal(line['unit_price'])==16 and Decimal(line['total_price'])==48
 assert Decimal(est['subtotal'])==173 and 'Finish: Oak' in line['description']
 for rate in ['1.234','10000000000','1e100']:
  call('POST','/pricing/catalog/items',422,json={'category_id':cat['id'],'name':'Invalid precision or size','unit_price':rate})
 call('POST','/pricing/catalog/items/'+item['id']+'/quote',422,json={'quantity':'1.234'})
 call('PUT','/pricing/catalog/categories/'+cat['id'],json=body(cat)|{'archived':True})
 for item in book['items']:
  if item['category_id']==cat['id']:call('POST','/pricing/catalog/items/'+item['id']+'/quote',409,json={'quantity':'1'})
 call('DELETE','/estimates/'+state['estimate_id'],204)
 for ident,snapshot in state['old_estimates'].items():assert call('GET','/estimates/'+ident)==snapshot
 print('QA category archived, QA estimate moved to Trash. Existing estimates unchanged.')
(OUT/f'{phase}-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
print(f'{len(checks)} local Price Book checks passed ({phase}).')
