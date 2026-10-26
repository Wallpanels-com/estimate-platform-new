"""Opt-in local layout fixture. Always creates a separate, clearly labelled estimate.
Usage: .venv/bin/python scripts/builder_stress.py create
       .venv/bin/python scripts/builder_stress.py trash <id>
Never pass a normal demo id; existing estimates cannot receive fixture items.
"""
import argparse,json,os
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from qa_credentials import qa_credentials
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['create','trash']);p.add_argument('id',nargs='?');args=p.parse_args()
base=os.environ.get('LOCAL_QA_BASE_URL','http://127.0.0.1:8010')
if urlsplit(base).hostname not in ('localhost','127.0.0.1'):p.error('Only loopback servers are supported.')
c=httpx.Client(base_url=base+'/api/v1',trust_env=False,timeout=60)
email,password=qa_credentials();r=c.post('/auth/login',json={'email':email,'password':password});r.raise_for_status();c.headers['Authorization']='Bearer '+r.json()['access_token']
def call(method,path,**kw):
    r=c.request(method,path,**kw);r.raise_for_status();return r.json() if r.content else None
fixture=json.loads((ROOT/'tests/fixtures/builder-stress.json').read_text())
if args.action=='trash':
    if not args.id:p.error('Supply the stress estimate id.')
    e=call('GET','/estimates/'+args.id)
    if not (e.get('title') or '').startswith('[STRESS TEST]'):p.error('Refusing to modify an ordinary estimate.')
    call('DELETE','/estimates/'+args.id);print('Stress fixture moved to Trash (recoverable).')
else:
    if args.id:p.error('Create always makes a new isolated fixture; no existing id is accepted.')
    e=call('POST','/estimates',json={'title':fixture['title'],'client_name':'STRESS TEST — disposable local fixture','description':fixture['description'],'type':'pre'})
    eid=e['id'];zid=e['zones'][0]['id']
    call('PATCH',f'/estimates/{eid}/zones/{zid}',json={'label':'Long zone name — full-height oak feature wall with concealed doors, integrated lighting and custom installation details','square_footage':120,'wall_width_ft':12,'wall_height_ft':10,'notes':'Long zone notes for responsive layout verification. '*12})
    for i in range(60):
        item={**fixture['items'][i%len(fixture['items'])],'zone_id':zid,'sort_order':i,'name':f'{i+1:02} · '+fixture['items'][i%len(fixture['items'])]['name'],'description':('Long description with surface preparation, panel alignment, concealed fixings and final finishing. '*10 if i%3==0 else fixture['items'][i%len(fixture['items'])]['description'])}
        if i==1:item['name']='VeryLongUnbrokenItemNameForOverflowVerification'*5
        if i==2:item['is_tbd']=True
        call('POST',f'/estimates/{eid}/line-items',json=item)
    second=call('POST',f'/estimates/{eid}/zones',json={'zone_type':'mirror','label':'Empty zone — photo and empty scope checks','square_footage':20})
    photo=ROOT/'.local/qa/upload-photo.jpg'
    if photo.exists():
        for slot in range(1,5):call('POST',f'/estimates/{eid}/zones/{zid}/images/{slot}',files={'file':(f'stress-photo-{slot}.jpg',photo.read_bytes(),'image/jpeg')})
    (ROOT/'.local/qa/builder-stress-id.txt').write_text(eid)
    print(json.dumps({'id':eid,'url':f'http://localhost:5190/estimates/{eid}','items':60,'empty_zone':second['id']},indent=2))
