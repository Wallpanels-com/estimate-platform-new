"""Owner-only batch entry: real API checks in audit_workflows' disposable schema."""
import asyncio
from copy import deepcopy
from decimal import Decimal
import uuid

async def check_manual_batch(call, c, tokens):
    c.headers.pop('If-Match', None)
    c.headers['Authorization'] = 'Bearer ' + tokens[0]
    est = (await call('POST', '/estimates', 201, json={'type':'pre','title':'Isolated batch test','client_name':'Fixture'})).json()
    path = '/estimates/' + est['id']
    payload = {'request_id':str(uuid.uuid4()),'zone_id':est['zones'][0]['id'], 'rows':[
        {'name':'Kitchen cabinets','section':'Kitchen','quantity':'17.60','unit':'LF','unit_price':'1200','total_price':'21120'},
        {'name':'Glass doors','section':'Kitchen','total_price':'1500'},
        {'name':'Shelves with LED','section':'Bar','total_price':'600'},
    ]}
    original_revision = est['revision']
    c.headers['If-Match'] = original_revision
    c.headers['Authorization'] = 'Bearer ' + tokens[1]
    await call('POST', path+'/manual-batch',403,json=payload)
    c.headers['Authorization'] = 'Bearer ' + tokens[0]
    invalid = deepcopy(payload); invalid['rows'][1]['total_price'] = '-1'
    await call('POST', path+'/manual-batch',422,json=invalid)
    invalid = deepcopy(payload); invalid['rows'][0]['total_price'] = '10'
    await call('POST', path+'/manual-batch',422,json=invalid)
    invalid = deepcopy(payload); invalid['rows'][0]['quantity'] = None
    await call('POST', path+'/manual-batch',422,json=invalid)
    foreign = deepcopy(payload); foreign['zone_id'] = str(uuid.uuid4())
    await call('POST', path+'/manual-batch',404,json=foreign)
    clean=(await call('GET',path)).json()
    assert clean['line_items'] == [] and clean['revision'] == original_revision
    results=await asyncio.gather(*[c.post(path+'/manual-batch',json=payload) for _ in range(2)])
    assert [r.status_code for r in results] == [200,200], [(r.status_code,r.text[:200]) for r in results]
    latest=(await call('GET',path)).json()
    assert len(latest['line_items'])==3
    assert Decimal(latest['subtotal'])==23220
    ordered=sorted(latest['line_items'],key=lambda i:i['sort_order'])
    assert [r['name'] for r in ordered] == [r['name'] for r in payload['rows']]
    assert ordered[0]['unit']=='LF' and Decimal(ordered[0]['quantity'])==Decimal('17.6')
    # Old revision may replay an identical committed request, but cannot add another one.
    await call('POST',path+'/manual-batch',json=payload)
    changed=deepcopy(payload);changed['rows'][1]['total_price']='1600'
    await call('POST',path+'/manual-batch',409,json=changed)
    changed['request_id']=str(uuid.uuid4())
    await call('POST',path+'/manual-batch',409,json=changed)
    c.headers['If-Match']=latest['revision']
    manual=deepcopy(payload);manual['request_id']=str(uuid.uuid4());manual['rows']=manual['rows'][:1]
    manual['rows'][0].update(total_price='21000',accept_total=True)
    saved=(await call('POST',path+'/manual-batch',json=manual)).json()
    assert len(saved['line_items'])==4 and Decimal(saved['subtotal'])==44220
    # Final branch uses the same batch contract, without changing source Pre data.
    c.headers['If-Match']=saved['revision']
    final=(await call('POST',path+'/mode',json={'mode':'final'})).json()
    fp='/estimates/'+final['id'];c.headers['If-Match']=final['revision']
    final_payload={'request_id':str(uuid.uuid4()),'zone_id':final['zones'][0]['id'],'rows':[{'name':'Final-only item','total_price':'25'}]}
    final=(await call('POST',fp+'/manual-batch',json=final_payload)).json()
    assert Decimal(final['subtotal'])==44245
    pre=(await call('GET',path)).json();assert Decimal(pre['subtotal'])==44220
    c.headers.pop('If-Match',None)
