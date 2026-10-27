"""Create/recheck four explicitly TEST Pre-estimates on the new corporate app.

Uses current saved Price Book rates and user-provided photographs. Credentials,
downloads and fixture progress are private local inputs/outputs, never Git data.
"""
import argparse
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import re
import sys

import httpx
from openpyxl import load_workbook
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'apps/backend'), str(ROOT/'scripts')]
from check_passport import check_passport
from app.services.final_estimate_service import load_company_slides, page_signature

BASE = 'https://estimate-platform-production.up.railway.app'
PLANS = [
    ('Olivia Bennett', '184 Harbor Drive', 'Bennett Residence', [1,3,2,5]),
    ('James Morgan', '72 Palm Grove Court', 'Morgan Residence', [3,5,2,7,1]),
    ('Emma Sullivan', '315 Magnolia Avenue', 'Sullivan Residence', [1,2,3,4,5,7,2,1,10,3]),
    ('Daniel Anderson', '608 Ocean Crest Lane', 'Anderson Residence', [2,3,5,7,12,1,2,3,4,5,7,2]),
]
ZONES = [
    ('Living Room Feature Wall','wall'), ('Dining Room Wall','wall'),
    ('Entry Mirror','mirror'), ('Kitchen Cabinetry','cabinet'),
    ('Primary Bedroom Accent Wall','wall'), ('Hallway Slat Panels','wall'),
    ('Home Office Cabinetry','cabinet'), ('Bathroom Vanity','cabinet'),
    ('Guest Bedroom Wall','wall'), ('Staircase Wall','wall'),
    ('Media Room Cabinetry','cabinet'), ('Foyer Mirror','mirror'),
]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=['create','verify'])
    p.add_argument('--credentials',type=Path,required=True)
    p.add_argument('--photos',type=Path,required=True)
    args=p.parse_args()
    out=ROOT/'.local/qa/sales-review';out.mkdir(parents=True,exist_ok=True)
    statefile=out/'state.json'
    state=json.loads(statefile.read_text()) if statefile.exists() else {'projects':[]}
    employees=json.loads(args.credentials.read_text())['users']
    clients=[]; revisions={}; checks=[]
    def call(c,method,path,expected=200,**kwargs):
        result=c.request(method,path,**kwargs)
        assert result.status_code==expected, f'{method} {path}: {result.status_code} {result.text[:220]}'
        if result.headers.get('X-Estimate-ID'):
            revisions[result.headers['X-Estimate-ID']]=result.headers['X-Estimate-Revision']
        checks.append([method,path,expected])
        return result
    for employee in employees[:4]:
        c=httpx.Client(base_url=BASE+'/api/v1',trust_env=False,timeout=240)
        token=call(c,'POST','/auth/login',json={'email':employee['login'],'password':employee['password']}).json()['access_token']
        c.headers['Authorization']='Bearer '+token;clients.append(c)
    def get(eid):
        value=call(clients[0],'GET','/estimates/'+eid).json()
        revisions[eid]=value['revision'];return value
    def write(c,method,eid,suffix='',expected=200,**kwargs):
        if eid not in revisions:get(eid)
        return call(c,method,'/estimates/'+eid+suffix,expected,headers={'If-Match':revisions[eid]},**kwargs)
    def save():
        statefile.write_text(json.dumps(state,indent=2,ensure_ascii=False));statefile.chmod(0o600)
    config=call(clients[0],'GET','/pricing/config').json()['config']
    photos=sorted(x for x in args.photos.iterdir() if x.suffix.lower() in {'.webp','.jpg','.jpeg','.png'})
    assert photos
    if args.phase=='create':
        for index,(client,address,residence,counts) in enumerate(PLANS):
            c=clients[index]
            if len(state['projects'])<=index:
                title=f'TEST - {residence} - {address}'
                est=call(c,'POST','/estimates',201,json={'type':'pre','title':title,'client_name':client,'project_name':address,'estimate_date':'2026-10-27','notes':'Internal review sample. Rates are taken from the saved Price Book.'}).json()
                state['projects'].append({'id':est['id'],'title':title,'counts':counts,'zones':[]});save()
            project=state['projects'][index];eid=project['id']
            for n,count in enumerate(counts):
                label,kind=ZONES[n]
                est=get(eid)
                if len(project['zones'])<=n:
                    if n==0:
                        zid=est['zones'][0]['id']
                    else:
                        zid=write(c,'POST',eid,'/zones',201,json={'label':label,'zone_type':kind,'sort_order':n}).json()['id']
                    project['zones'].append({'id':zid});save()
                zid=project['zones'][n]['id']
                sf=Decimal(90+n*13+index*11);lf=Decimal(6+n+index)
                write(c,'PATCH',eid,'/zones/'+zid,json={'label':label,'zone_type':kind,'sort_order':n,'square_footage':str(sf) if kind!='cabinet' else None,'linear_footage':str(lf) if kind=='cabinet' else None})
                options={'square_footage':float(sf)} if kind=='wall' else {'square_footage':float(12+n+index)} if kind=='mirror' else {'linear_footage':float(lf),'cabinet_type':'tv_stand' if n==6 else 'kitchen_island'}
                result=call(c,'POST','/pricing/calc/'+kind,json=options).json()
                rows=result['line_items']
                # Compatibility while the corrected mirror adapter rolls out.
                if kind=='mirror' and len(rows)==1:
                    base=dict(rows[0]);material=Decimal(str(base['quantity']))*Decimal(str(base['unit_price']))
                    fee=Decimal(str(base['total_price']))-material;base['total_price']=float(material)
                    rows=[base,{'section':'Mirrors','name':'Mirror Delivery & Installation','calc_type':'fixed','quantity':1,'unit':'ea','unit_price':float(fee),'total_price':float(fee)}]
                features=list(config['wall']['addons_sf'].values())
                fixed=list(config['wall']['addons_fixed'].values())
                extras=0
                while len(rows)<count:
                    if extras<len(features):
                        rate=features[extras];qty=Decimal(10+3*n+extras+index)
                        rows.append({'section':rows[0]['section'],'name':rate['label'],'description':'Measured accent detail','calc_type':'sf','unit':'SF','quantity':str(qty),'unit_price':str(rate['price']),'total_price':str(qty*Decimal(str(rate['price'])))})
                    else:
                        rate=fixed[(extras-len(features))%len(fixed)]
                        rows.append({'section':rows[0]['section'],'name':rate['label'],'description':'Custom architectural feature','calc_type':'fixed','unit':'ea','quantity':1,'unit_price':rate['price'],'total_price':rate['price']})
                    extras+=1
                zone=next(z for z in get(eid)['zones'] if z['id']==zid)
                for order,row in enumerate(rows):
                    if not any(i['sort_order']==order for i in zone['line_items']):
                        write(c,'POST',eid,'/line-items',201,json={**row,'zone_id':zid,'sort_order':order})
                image_count=1+(n+index)%4
                for slot in range(1,image_count+1):
                    zone=next(z for z in get(eid)['zones'] if z['id']==zid)
                    if any(img['slot']==slot for img in zone['images']):continue
                    source=photos[(n*3+index+slot-1)%len(photos)];data=source.read_bytes()
                    mime='image/webp' if source.suffix.lower()=='.webp' else 'image/png' if source.suffix.lower()=='.png' else 'image/jpeg'
                    write(c,'POST',eid,f'/zones/{zid}/images/{slot}',files={'file':(source.name,data,mime)})
                project['zones'][n].update(label=label,items=len(rows),photos=image_count);save()
                print(f'{residence}: zone {n+1}/{len(counts)}, {len(rows)} items, {image_count} photos',flush=True)
            project['snapshot']=get(eid);save()
        state['creation_checks']=checks;save()
        print('Four Pre-estimates created. Ready for export verification.',flush=True)
        return
    company=load_company_slides()
    for index,project in enumerate(state['projects']):
        c=clients[index];eid=project['id'];est=get(eid)
        assert len(est['zones'])==len(project['counts'])
        assert [len(z['line_items']) for z in est['zones']]==project['counts']
        raw=sum((Decimal(i['total_price']) for i in est['line_items']),Decimal(0))
        assert raw==Decimal(est['subtotal'])==Decimal(est['final_total'])
        for image in est['images']:
            body=call(c,'GET','/media/'+image['id']).content
            source=args.photos/image['original_name']
            assert hashlib.sha256(body).digest()==hashlib.sha256(source.read_bytes()).digest()
        pre=call(c,'GET',f'/pdf/{eid}/pre-estimate').content
        assert pre==call(clients[(index+1)%4],'GET',f'/pdf/{eid}/pre-estimate?download=true').content
        pre_path=out/f'{index+1}-pre.pdf';pre_path.write_bytes(pre)
        pre_reader=PdfReader(io.BytesIO(pre));text=' '.join(p.extract_text() for p in pre_reader.pages)
        for zone in est['zones']:assert zone['label'].lower() in re.sub(r'\s+',' ',text).lower()
        sheet=call(c,'GET',f'/pdf/{eid}/passport').content
        xlsx_path=out/f'{index+1}-pre.xlsx';xlsx_path.write_bytes(sheet)
        passport=check_passport(xlsx_path,est)
        for kind in ('pdf','xlsx'):
            label='TEST review - Pre '+kind.upper()
            existing=call(c,'GET',f'/estimates/{eid}/documents').json()
            if not any(d['label']==label for d in existing):write(c,'POST',eid,'/documents',201,json={'kind':kind,'label':label})
        final=write(c,'POST',eid,'/mode',json={'mode':'final'}).json();fid=final['id']
        assert len(final['zones'])==len(project['counts'])
        for zone in final['zones']:
            if len(zone['images'])>1:
                write(c,'PUT',fid,f"/zones/{zone['id']}/presentation-photo",json={'slot':2});break
        final=get(fid)
        final_bytes=call(c,'GET',f'/pdf/{fid}/final-estimate').content
        assert final_bytes==call(clients[(index+1)%4],'GET',f'/pdf/{fid}/final-estimate?download=true').content
        final_path=out/f'{index+1}-final.pdf';final_path.write_bytes(final_bytes)
        reader=PdfReader(io.BytesIO(final_bytes))
        assert [page_signature(page) for page in reader.pages[-13:]]==company.signatures
        summaries=[page for page in reader.pages[:-13] if 'Investment summary' in page.extract_text()]
        sizes=[]
        for page in summaries:
            text=re.sub(r'\s+',' ',page.extract_text()).lower()
            sizes.append(sum(z['label'].lower() in text for z in final['zones']))
        if len(project['counts'])==12:assert sizes==[6,6],sizes
        assert sum(sizes)==len(final['zones']),sizes
        final_xlsx=out/f'{index+1}-final.xlsx';final_xlsx.write_bytes(call(c,'GET',f'/pdf/{fid}/passport').content)
        check_passport(final_xlsx,final)
        existing=call(c,'GET',f'/estimates/{fid}/documents').json()
        if not any(d['label']=='TEST review - Final PDF' for d in existing):
            write(c,'POST',fid,'/documents',201,json={'kind':'pdf','label':'TEST review - Final PDF'})
        write(c,'POST',fid,'/mode',json={'mode':'pre'})
        project.update(final_id=fid,pre_pages=len(pre_reader.pages),final_pages=len(reader.pages),summary_distribution=sizes,passport=passport,verified=True)
        save()
        print(f"Verified {project['title']}: {len(est['zones'])} zones, {len(est['line_items'])} items, Pre {len(pre_reader.pages)} pages, Final {len(reader.pages)} pages; summary {sizes}; total ${raw:,.2f}",flush=True)
    state['verification_checks']=checks;save()
    print(f'Export verification complete: {len(checks)} requests. All four projects remain in Pre-estimate mode.',flush=True)


if __name__=='__main__':main()
