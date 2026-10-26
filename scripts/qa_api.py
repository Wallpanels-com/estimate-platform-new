"""Repeatable local integration checks. Creates only QA-labelled disposable records."""
from pathlib import Path
from urllib.parse import urlsplit
import argparse,io,json,os,httpx
from openpyxl import load_workbook
from qa_credentials import qa_credentials
argparse.ArgumentParser(description=__doc__).parse_args()
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'.local/qa';OUT.mkdir(parents=True,exist_ok=True)
base=os.environ.get('LOCAL_QA_BASE_URL','http://127.0.0.1:8010')
if urlsplit(base).hostname not in ('localhost','127.0.0.1'):raise SystemExit('QA only supports loopback servers.')
c=httpx.Client(base_url=base+'/api/v1',timeout=60,trust_env=False);checks=[]
def call(method,path,status=200,**kw):
    r=c.request(method,path,**kw);checks.append({'method':method,'path':path,'status':r.status_code,'expected':status})
    assert r.status_code==status,f'{method} {path}: {r.status_code} {r.text[:300]}'
    return r
email,password=qa_credentials(create_disposable=True)
r=c.post('/auth/login',json={'email':email,'password':password})
if r.status_code==401:r=call('POST','/auth/register',201,json={'email':email,'password':password,'name':'Local QA'})
r.raise_for_status();c.headers['Authorization']='Bearer '+r.json()['access_token']
call('GET','/auth/me');call('PATCH','/auth/me',json={'onboarding_completed':True})
original=call('GET','/pricing/config').json()['config']
assert call('PUT','/pricing/config',json={'config':original}).json()['config']==original
call('GET','/pricing/schema');call('GET','/pricing/quick-config')
wall=call('POST','/pricing/calc/wall',json={'square_footage':120,'addons_sf':['led'],'addons_fixed':[{'key':'hidden_door','qty':1}]}).json();assert wall['total']==9700
call('POST','/pricing/calc/cabinet',json={'linear_footage':8,'cabinet_type':'tv_stand','addons_lf':['led_lighting']})
mirror=call('POST','/pricing/calc/mirror',json={'square_footage':20}).json();assert mirror['total']==2600
est=call('POST','/estimates',201,json={'type':'pre','title':'QA API regression - panels and mirror','client_name':'QA API Client','prepared_by':'Local QA','estimate_date':'2026-10-21'}).json();eid=est['id'];zid=est['zones'][0]['id']
call('PATCH',f'/estimates/{eid}/zones/{zid}',json={'label':'Feature wall','wall_width_ft':12,'wall_height_ft':10,'square_footage':120})
items=[]
for i,item in enumerate(wall['line_items']):items.append(call('POST',f'/estimates/{eid}/line-items',201,json={**item,'zone_id':zid,'sort_order':i}).json())
est=call('GET',f'/estimates/{eid}').json();assert float(est['subtotal'])==9700 and float(est['zones'][0]['subtotal'])==9700
call('PATCH',f'/estimates/{eid}/line-items/{items[0]["id"]}',json={'quantity':0});assert float(call('GET',f'/estimates/{eid}').json()['subtotal'])==2500
call('PATCH',f'/estimates/{eid}/line-items/{items[0]["id"]}',json={'quantity':120})
call('POST',f'/estimates/{eid}/line-items/reorder',204,json={'ordered_ids':[i['id'] for i in reversed(items)]})
second=call('POST',f'/estimates/{eid}/zones',201,json={'zone_type':'mirror','label':'Mirror','square_footage':20}).json()
m=call('POST',f'/estimates/{eid}/line-items',201,json={**mirror['line_items'][0],'zone_id':second['id']}).json();assert float(m['total_price'])==2600
assert float(call('GET',f'/estimates/{eid}').json()['subtotal'])==12300
if not (OUT/'upload-photo.jpg').exists():
    from PIL import Image
    Image.new('RGB',(800,600),'#d8c9ae').save(OUT/'upload-photo.jpg')
photo=(OUT/'upload-photo.jpg').read_bytes()
call('POST',f'/estimates/{eid}/zones/{zid}/images/1',files={'file':('qa-photo.jpg',photo,'image/jpeg')})
copy=call('POST',f'/estimates/{eid}/zones/{zid}/duplicate',201).json();assert len(copy['line_items'])==2
call('DELETE',f'/estimates/{eid}/zones/{copy["id"]}',204)
assert float(call('GET',f'/estimates/{eid}').json()['subtotal'])==12300
call('POST',f'/estimates/{eid}/zones/reorder',json=[second['id'],zid])
for typ in ['pre','final']:
    call('PATCH',f'/estimates/{eid}',json={'type':typ,'markup_pct':10,'discount_pct':5})
    call('POST',f'/pdf/{eid}/generate');r=call('GET',f'/pdf/{eid}/download');assert r.content.startswith(b'%PDF');(OUT/f'api-{typ}.pdf').write_bytes(r.content)
r=call('GET',f'/pdf/{eid}/passport');(OUT/'api-passport.xlsx').write_bytes(r.content)
w=load_workbook(io.BytesIO(r.content));assert w.active['C3'].value=='QA API Client'
call('DELETE',f'/estimates/{eid}/zones/{zid}/images/1',204)
# AI errors are explicit without contacting OpenAI when there is no key.
call('POST','/voice/extract',503,json={'estimate_id':eid,'zone_id':zid,'text':'12 by 10 foot wall'})
copy=call('POST',f'/estimates/{eid}/duplicate',201).json()
call('DELETE',f'/estimates/{copy["id"]}',204);call('GET','/estimates/trash');call('POST',f'/estimates/{copy["id"]}/restore');call('DELETE',f'/estimates/{copy["id"]}',204)
call('DELETE',f'/estimates/{eid}',204)
# Stress layouts use scripts/builder_stress.py; never mutate an existing demo.
(OUT/'api-verification.json').write_text(json.dumps({'base':base,'checks':checks,'passed':len(checks)},indent=2))
print(f'{len(checks)} local API checks passed. Artifacts: .local/qa')
