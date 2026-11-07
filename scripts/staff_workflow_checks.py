"""Shared HR staff API checks in the audit's disposable local schema."""
from io import BytesIO
from unittest.mock import patch
from PIL import Image
from openpyxl import Workbook


async def check_staff(call, client, tokens):
    w=Workbook();s=w.active;s.title='Main'
    s.append(['Name','Status','Start','End','Role','Phone','Department'])
    s.append(['Kravchenko Ihor','Active',None,None,'Co-founder',None,'Administration'])
    s.append(['Test operations','Active',None,None,'Chief Operating Officer (COO)',None,'Administration'])
    s.append(['Test sales lead','Active',None,None,'Director',None,'Sales'])
    s.append(['Test employee','Paused',None,None,'Sales manager',None,'Sales'])
    s['F2']='@synthetic_staff'
    s['M5']='Documents';s['M5'].hyperlink='https://example.com/document'
    s['O5']='Synthetic private note'
    w.create_sheet('Ignored').append(['No import'])
    b=BytesIO();w.save(b)
    file={'file':('staff.xlsx',b.getvalue(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
    client.headers['Authorization']='Bearer '+tokens[0]
    with patch('app.services.staff_avatars.fetch_avatar',return_value=None) as automatic:
        assert (await call('POST','/hr/staff/import',201,files=file)).json()['added']==4
        assert automatic.call_count==1, 'Active employee import automatically fetches a public avatar'
    assert (await call('POST','/hr/staff/import',201,files=file)).json()=={'added':0,'duplicates':4,'sheet':'Main'}
    rows=(await call('GET','/hr/staff')).json()['items'];assert len(rows)==4
    ceo=next(r for r in rows if r['title']=='CEO');emp=next(r for r in rows if r['status']=='paused')
    assert emp['links']['M']=='https://example.com/document'
    assert emp['fields']['O']=='Synthetic private note'
    def body(row):return {k:row[k] for k in ('version','name','title','department','status','manager_id','fields','links')}
    # No HR grant means no directory, profile, import, history or chart access.
    target=(await call('GET','/auth/me',headers={'Authorization':'Bearer '+tokens[1]})).json()
    access_path=f'/users/{target["id"]}/access'
    original=(await call('GET',access_path)).json()
    client.headers['Authorization']='Bearer '+tokens[1]
    await call('GET','/hr/staff',403)
    await call('GET','/hr/staff/chart',403)
    await call('PATCH',f'/hr/staff/{emp["id"]}',403,json=body(emp))
    await call('POST','/hr/staff/import',403,files=file)
    await call('GET',f'/hr/staff/{emp["id"]}/history',403)
    await call('GET',f'/hr/staff/{ceo["id"]}/avatar',403)
    await call('POST','/hr/staff/avatars/sync',403)
    client.headers['Authorization']='Bearer '+tokens[0]
    await call('PUT',access_path,json={'pages':['hr'],'expected_updated_at':original['updated_at']})
    client.headers['Authorization']='Bearer '+tokens[1]
    assert len((await call('GET','/hr/staff')).json()['items'])==4
    await call('GET',f'/hr/staff/{emp["id"]}/history')
    await call('GET',f'/hr/staff/{ceo["id"]}/avatar',204)
    avatar=BytesIO();Image.new('RGB',(40,40),'#aaa').save(avatar,'PNG');photo=avatar.getvalue()
    with patch('app.services.staff_avatars.fetch_avatar',return_value=(photo,'image/png')) as fetch:
        synced=(await call('POST','/hr/staff/avatars/sync')).json()['items']
        assert len(synced)==3 and fetch.call_count==1
    with patch('app.services.staff_avatars.fetch_avatar',side_effect=AssertionError('No Telegram calls on reads')):
        assert (await call('GET',f'/hr/staff/{ceo["id"]}/avatar')).content==photo
        shown=next(p for p in (await call('GET','/hr/staff')).json()['items'] if p['id']==ceo['id'])
        assert shown['avatar_url'].startswith(f'/api/v1/hr/staff/{ceo["id"]}/avatar?v=')
        assert all(shown[k]==ceo[k] for k in ('name','fields','links','version','updated_by'))
    cycle=body(ceo)|{'manager_id':emp['id']}
    await call('PATCH',f'/hr/staff/{ceo["id"]}',422,json=cycle)
    await call('PATCH',f'/hr/staff/{emp["id"]}',422,json=body(emp)|{'manager_id':emp['id']})
    await call('PATCH',f'/hr/staff/{emp["id"]}',422,json=body(emp)|{'links':{'M':'javascript:alert(1)'}})
    edited=(await call('PATCH',f'/hr/staff/{emp["id"]}',json=body(emp)|{'status':'active','title':'Updated role','manager_id':ceo['id']})).json()
    assert edited['version']==2 and edited['manager_id']==ceo['id']
    assert edited['updated_by']==target['name']
    await call('PATCH',f'/hr/staff/{emp["id"]}',409,json=body(emp))
    # A new GET/database session and repeat upload retain edits and original links.
    await call('POST','/hr/staff/import',201,files=file)
    fresh=next(r for r in (await call('GET','/hr/staff')).json()['items'] if r['id']==emp['id'])
    assert fresh['status']=='active' and fresh['title']=='Updated role' and fresh['fields']['O']=='Synthetic private note'
    assert (await call('GET',f'/hr/staff/{emp["id"]}/history')).json()
    # The chart stores collaboration separately and changes managers atomically.
    chart=(await call('GET','/hr/staff/chart')).json();assert chart['version']==0
    # A different HR employee may read and edit the shared chart too.
    await call('GET','/hr/staff/chart')
    rows=(await call('GET','/hr/staff')).json()['items'];emp=next(p for p in rows if p['id']==emp['id'])
    others=[p for p in rows if p['id'] not in (emp['id'],ceo['id'])]
    body={'version':0,'changes':[{'id':emp['id'],'version':emp['version'],'manager_id':others[0]['id']}],
          'extra_edges':[{'source':emp['id'],'target':ceo['id']}],
          'orders':{'teams':[p['id'] for p in reversed(rows)]}}
    saved=(await call('PUT','/hr/staff/chart',json=body)).json();assert saved['version']==1
    assert (await call('GET','/hr/staff/chart')).json()==saved
    employee=next(p for p in (await call('GET','/hr/staff')).json()['items'] if p['id']==emp['id'])
    assert employee['manager_id']==others[0]['id'] and employee['version']==emp['version']+1
    assert all(employee[k]==emp[k] for k in ('name','title','department','status','fields','links'))
    await call('PUT','/hr/staff/chart',409,json=body)
    await call('PUT','/hr/staff/chart',409,json={**body,'version':1})
    await call('PUT','/hr/staff/chart',422,json={'version':1,'changes':[{'id':ceo['id'],'version':ceo['version'],'manager_id':employee['id']}]})
    await call('PUT','/hr/staff/chart',422,json={'version':1,'extra_edges':[{'source':emp['id'],'target':emp['id']}]})
    await call('PUT','/hr/staff/chart',422,json={'version':1,'extra_edges':[{'source':emp['id'],'target':ceo['id']}]*2})
    await call('PUT','/hr/staff/chart',422,json={'version':1,'orders':{'teams':[emp['id']]*2}})
    # Invalid saves have no partial effect on either graph or employee records.
    assert (await call('GET','/hr/staff/chart')).json()==saved
    assert next(p for p in (await call('GET','/hr/staff')).json()['items'] if p['id']==emp['id'])==employee
    removed=(await call('PUT','/hr/staff/chart',json={'version':1,'changes':[{'id':employee['id'],'version':employee['version'],'manager_id':None}],'extra_edges':[],'orders':saved['orders']})).json()
    assert removed['version']==2 and removed['extra_edges']==[]
    employee=next(p for p in (await call('GET','/hr/staff')).json()['items'] if p['id']==emp['id']);assert employee['manager_id'] is None

    # Revocation applies to every staff endpoint without changing any directory data.
    client.headers['Authorization']='Bearer '+tokens[0]
    access=(await call('GET',access_path)).json()
    await call('PUT',access_path,json={'pages':original['pages'],'expected_updated_at':access['updated_at']})
    client.headers['Authorization']='Bearer '+tokens[1]
    await call('GET','/hr/staff',403)
    await call('GET','/hr/staff/chart',403)
    await call('PUT','/hr/staff/chart',403,json={'version':2})
    client.headers['Authorization']='Bearer '+tokens[0]
