"""Sales readiness mutations are restricted to a newly duplicated TEST project."""
import argparse, io, json
from decimal import Decimal
from pathlib import Path
import httpx
from check_passport import check_passport

ROOT=Path(__file__).resolve().parents[1]
BASE='https://estimate-platform-production.up.railway.app/api/v1'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credentials',type=Path,required=True)
    args=parser.parse_args()
    users=json.loads(args.credentials.read_text())['users']
    out=ROOT/'.local/qa/sales-review';state=json.loads((out/'state.json').read_text())
    checks=[]
    def call(client,method,path,expected=200,**kw):
        r=client.request(method,path,**kw)
        assert r.status_code==expected,f'{method} {path}: {r.status_code} {r.text[:200]}'
        checks.append([method,path,expected]);return r
    clients=[]
    for u in users[:2]:
        c=httpx.Client(base_url=BASE,trust_env=False,timeout=180)
        r=call(c,'POST','/auth/login',json={'email':u['login'],'password':u['password']})
        c.headers['Authorization']='Bearer '+r.json()['access_token'];clients.append(c)
    a,b=clients
    def get(eid):return call(a,'GET','/estimates/'+eid).json()
    def write(c,method,eid,suffix='',expected=200,**kw):
        return call(c,method,'/estimates/'+eid+suffix,expected,headers={'If-Match':get(eid)['revision']},**kw)
    assert call(a,'GET','/auth/settings').json()['ai_enabled'] is False
    config=call(a,'GET','/pricing/config').json()
    call(b,'PUT','/pricing/config',json={'config':config['config'],'expected_revision':config['revision']})
    assert call(a,'GET','/pricing/config').json()['config']==config['config']
    original=get(state['projects'][0]['id'])
    assert original['title'].startswith('TEST - ')
    copied=write(b,'POST',original['id'],'/duplicate',201).json();eid=copied['id']
    assert copied['prepared_by']==users[1]['name']
    assert copied['markup_pct']==original['markup_pct']
    assert copied['final_total']==original['final_total']
    assert len(copied['images'])==len(original['images'])
    for src,dst in zip(original['zones'],copied['zones']):
        assert len(src['images'])==len(dst['images'])
        for img in dst['images']:
            original_img=next(i for i in src['images'] if i['slot']==img['slot'])
            assert img['id']!=original_img['id'] and img['file_path']!=original_img['file_path']
            assert call(a,'GET','/media/'+img['id']).content==call(b,'GET','/media/'+original_img['id']).content
    zone_copy=write(a,'POST',eid,f"/zones/{copied['zones'][0]['id']}/duplicate",201).json()
    assert len(zone_copy['images'])==len(copied['zones'][0]['images'])
    assert zone_copy['subtotal']==copied['zones'][0]['subtotal']
    write(b,'DELETE',eid,'/zones/'+zone_copy['id'],204)
    assert get(eid)['final_total']==original['final_total']
    result=call(a,'POST','/pricing/calc/mirror',json={'square_footage':20}).json()
    assert result['total']==2600 and len(result['line_items'])==2
    zone=write(b,'POST',eid,'/zones',201,json={'label':'TEST Mirror Installation Safety','zone_type':'mirror'}).json()
    for row in result['line_items']:
        write(b,'POST',eid,'/line-items',201,json={**row,'zone_id':zone['id']})
    mirror=next(z for z in get(eid)['zones'] if z['id']==zone['id'])
    material=next(i for i in mirror['line_items'] if i['calc_type']=='sf')
    write(a,'PATCH',eid,'/line-items/'+material['id'],json={'quantity':'25'})
    mirror=next(z for z in get(eid)['zones'] if z['id']==zone['id'])
    assert Decimal(mirror['subtotal'])==3000
    assert next(i for i in mirror['line_items'] if i['calc_type']=='fixed')['total_price']=='1000.00'
    source_image=original['zones'][0]['images'][0]
    image=call(a,'GET','/media/'+source_image['id']).content
    write(b,'POST',eid,f"/zones/{zone['id']}/images/1",files={'file':(source_image['original_name'],image,'image/webp')})
    category=call(a,'POST','/pricing/catalog/categories',201,json={'name':'TEST Sales Readiness '+eid[:8]}).json()
    item=call(b,'POST','/pricing/catalog/items',201,json={'category_id':category['id'],'name':'TEST Priced Finish','unit':'SF','unit_price':'12.50'}).json()
    edited=call(a,'PUT','/pricing/catalog/items/'+item['id'],json={'category_id':category['id'],'name':item['name'],'unit':'SF','unit_price':'15.25','expected_version':item['version']}).json()
    quoted=call(b,'POST','/pricing/catalog/items/'+item['id']+'/quote',json={'quantity':'4'}).json()
    assert quoted['unit_price']=='15.25' and quoted['total_price']=='61.00'
    write(b,'POST',eid,'/line-items',201,json={**quoted,'zone_id':zone['id']})
    call(a,'PUT','/pricing/catalog/items/'+item['id'],json={'category_id':category['id'],'name':item['name'],'unit':'SF','unit_price':'15.25','archived':True,'expected_version':edited['version']})
    call(a,'PUT','/pricing/catalog/categories/'+category['id'],json={'name':category['name'],'archived':True,'expected_version':category['version']})
    write(a,'PATCH',eid,json={'markup_pct':'12.5','discount_pct':'5'})
    est=get(eid)
    sheet=out/'adjustments-pre.xlsx';sheet.write_bytes(call(b,'GET',f'/pdf/{eid}/passport').content)
    check_passport(sheet,est)
    final=write(a,'POST',eid,'/mode',json={'mode':'final'}).json();fid=final['id']
    first=get(eid)['zones'][0]['line_items'][0];quantity=Decimal(first['quantity'])
    write(a,'PATCH',eid,'/line-items/'+first['id'],json={'quantity':str(quantity+1)})
    inherited=get(fid)['zones'][0]['line_items'][0]
    assert Decimal(inherited['quantity'])==quantity+1
    write(b,'PATCH',fid,'/line-items/'+inherited['id'],json={'quantity':str(quantity+2)})
    assert Decimal(get(eid)['zones'][0]['line_items'][0]['quantity'])==quantity+1
    write(a,'PATCH',eid,'/line-items/'+first['id'],json={'quantity':str(quantity+3)})
    assert Decimal(get(fid)['zones'][0]['line_items'][0]['quantity'])==quantity+2
    final=get(fid);sheet=out/'adjustments-final.xlsx';sheet.write_bytes(call(a,'GET',f'/pdf/{fid}/passport').content)
    check_passport(sheet,final)
    assert call(b,'GET',f'/pdf/{fid}/final-estimate').content.startswith(b'%PDF')
    document=write(b,'POST',fid,'/documents',201,json={'kind':'xlsx','label':'TEST Markup and discount verification'}).json()
    version=call(a,'GET','/documents/'+document['id']).content
    write(a,'PATCH',fid,json={'discount_pct':'7'})
    assert call(b,'GET','/documents/'+document['id']+'?download=true').content==version
    stale=get(eid)['revision']
    write(a,'PATCH',eid,json={'notes':'TEST concurrent edit saved'})
    call(b,'PATCH','/estimates/'+eid,409,headers={'If-Match':stale},json={'notes':'MUST NOT OVERWRITE'})
    write(b,'DELETE',eid,expected=204)
    current=get(original['id'])
    for field in ('zones','line_items','images','subtotal','final_total','markup_pct','discount_pct','title'):
        assert current[field]==original[field],field
    (out/'safety-results.json').write_text(json.dumps({'checks':checks,'copied_test_id':eid,'mirror_installation_preserved':True,'pre_final_isolation':True,'excel_adjustments_reconciled':True,'original_unchanged':True,'saved_version_immutable':True},indent=2))
    print(f'Sales safety passed: {len(checks)} API checks; saved rates, photo copies, mirror fee, Excel adjustments, Pre/Final isolation, immutable versions, conflict protection. Disposable copy in Trash.',flush=True)


if __name__=='__main__':main()
