"""Runs only inside audit_workflows' disposable local database."""
from io import BytesIO
from openpyxl import Workbook

async def check_hr(call, client, tokens):
    from app.services.page_access import LEGACY_PAGES
    client.headers['Authorization']='Bearer '+tokens[1]
    me=(await call('GET','/auth/me')).json()
    assert me['page_access']==list(LEGACY_PAGES)
    await call('GET','/hr/vacancies',403)
    await call('POST','/hr/vacancies',403,json={'name':'Forbidden'})
    client.headers['Authorization']='Bearer '+tokens[0]
    v=(await call('POST','/hr/vacancies',201,json={'name':'Recruitment audit','description':'Professional requirements'})).json();vid=v['id']
    w=Workbook();s=w.active;s.title='Candidates'
    s.append(['ad_name','полное_имя','эл._адрес','phone','сколько_лет_вы_работаете_в_маркетинге?','какой_у_вас_уровень_английского?'])
    for row in [('Ad','First','first@example.com','+380123456789','более_8_лет','c1–c2_(продвинутый)'),('Ad','Second','second@example.ru','+71234567890','менее_1_года','a1–a2_(начальный)'),('Ad','First','first@example.com','','',''),('Ad','<test lead: dummy data>','test@example.com','','',''),('Ad','','missing@example.com','','','')]:s.append(row)
    data=BytesIO();w.save(data)
    async def stage():return (await call('POST',f'/hr/vacancies/{vid}/imports',201,files={'file':('Candidates.xlsx',data.getvalue(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})).json()
    await call('POST',f'/hr/vacancies/{vid}/imports',422,files={'file':('broken.xlsx',b'invalid','application/octet-stream')})
    batch=await stage();bid=batch['id'];body={'sheet':'Candidates','mapping':batch['sheets'][0]['mapping']}
    assert body['mapping']['name']=='полное_имя'
    await call('POST',f'/hr/imports/{bid}/preview',422,json={'sheet':'Candidates','mapping':{'name':'missing'}})
    p=(await call('POST',f'/hr/imports/{bid}/preview',json=body)).json()
    assert (p['added'],p['duplicates'],p['invalid'],p['test_rows'])==(2,1,1,1)
    assert (await call('GET',f'/hr/vacancies/{vid}/candidates')).json()['total']==0
    result=(await call('POST',f'/hr/imports/{bid}/confirm',json=body)).json()
    assert result['added']==2
    assert (await call('POST',f'/hr/imports/{bid}/confirm',json=body)).json()==result
    rows=(await call('GET',f'/hr/vacancies/{vid}/candidates')).json()['items']
    assert [r['score'] for r in rows]==[100,0]
    low=rows[1];assert low['contact_flags']==['phone_plus7','email_ru']
    update={k:low[k] for k in ('version','status','priority','location','location_verified','notes')}
    update.update(priority=True,notes='Reviewed on professional criteria',location='Confirmed location',location_verified=True,status='interview')
    saved=(await call('PATCH',f"/hr/candidates/{low['id']}",json=update)).json();assert saved['version']==2
    await call('PATCH',f"/hr/candidates/{low['id']}",409,json=update)
    rows=(await call('GET',f'/hr/vacancies/{vid}/candidates')).json()['items'];assert rows[0]['id']==low['id'] and rows[0]['notes']==update['notes']
    hist=(await call('GET',f"/hr/candidates/{low['id']}/history")).json();assert any('notes' in h['fields'] for h in hist)
    assert (await call('GET',f'/hr/vacancies/{vid}/candidates?q=First')).json()['total']==1
    batch2=await stage();result=(await call('POST',f"/hr/imports/{batch2['id']}/confirm",json=body)).json();assert result['added']==0 and result['duplicates']==3
    v=(await call('PATCH',f'/hr/vacancies/{vid}',json={'name':'Updated vacancy','description':'Requirements','archived':True,'expected_updated_at':v['updated_at']})).json()
    await call('POST',f'/hr/vacancies/{vid}/imports',409,files={'file':('Candidates.xlsx',data.getvalue(),'application/octet-stream')})
    await call('PATCH',f'/hr/vacancies/{vid}',json={'name':v['name'],'description':v['description'],'archived':False,'expected_updated_at':v['updated_at']})
    # Page sizes, non-overlapping slices and stale/out-of-range page clamping.
    w2=Workbook();ws=w2.active;ws.append(['name','email','phone'])
    for i in range(63):ws.append([f'Paging {i}',f'page{i}@example.com',''])
    buf=BytesIO();w2.save(buf)
    b=(await call('POST',f'/hr/vacancies/{vid}/imports',201,files={'file':('Paging.xlsx',buf.getvalue(),'application/octet-stream')})).json()
    await call('POST',f"/hr/imports/{b['id']}/confirm",json={'sheet':b['sheets'][0]['name'],'mapping':b['sheets'][0]['mapping']})
    slices=[]
    for number,expected in [(1,20),(2,20),(4,5)]:
        result=(await call('GET',f'/hr/vacancies/{vid}/candidates?page_size=20&page={number}')).json()
        assert len(result['items'])==expected and result['page']==number
        slices.append({r['id'] for r in result['items']})
    assert not slices[0].intersection(slices[1])
    for size,expected in [(50,50),(100,65)]:
        result=(await call('GET',f'/hr/vacancies/{vid}/candidates?page_size={size}')).json()
        assert len(result['items'])==expected and result['page_size']==size
    assert (await call('GET',f'/hr/vacancies/{vid}/candidates?page_size=20&page=999')).json()['page']==4
    await call('GET',f'/hr/vacancies/{vid}/candidates?page_size=21',422)
    # Quick actions change one field only and preserve hiring stage, notes and priority.
    target=(await call('GET',f'/hr/vacancies/{vid}/candidates?q=First')).json()['items'][0]
    quick=f"/hr/candidates/{target['id']}/quick"
    starred=(await call('PATCH',quick,json={'version':target['version'],'priority':True})).json()
    assert starred['priority'] and starred['status']==target['status'] and starred['notes']==target['notes']
    await call('PATCH',quick,409,json={'version':target['version'],'hidden':True})
    await call('PATCH',quick,422,json={'version':starred['version'],'hidden':True,'priority':False})
    hidden=(await call('PATCH',quick,json={'version':starred['version'],'hidden':True})).json()
    assert hidden['hidden'] and hidden['priority'] and hidden['status']==target['status']
    assert (await call('GET',f'/hr/vacancies/{vid}/candidates?q=First')).json()['total']==0
    hidden_list=(await call('GET',f'/hr/vacancies/{vid}/candidates?q=First&hidden=true')).json()
    assert hidden_list['total']==1 and hidden_list['items'][0]['id']==target['id']
    body={k:hidden[k] for k in ('version','status','priority','location','location_verified','notes')}
    body['notes']='Note added while hidden'
    edited=(await call('PATCH',f"/hr/candidates/{target['id']}",json=body)).json()
    assert edited['hidden'] and edited['status']==target['status']
    restored=(await call('PATCH',quick,json={'version':edited['version'],'hidden':False})).json()
    assert not restored['hidden'] and restored['priority'] and restored['notes']==body['notes'] and restored['status']==target['status']
    assert (await call('GET',f'/hr/vacancies/{vid}/candidates?q=First')).json()['total']==1
    profile_body={k:restored[k] for k in ('version','status','priority','location','location_verified','notes')}
    profile_body['telegram_username']='https://t.me/example_user'
    profile=(await call('PATCH',f"/hr/candidates/{target['id']}",json=profile_body)).json()
    assert profile['telegram_username']=='example_user'
    await call('PATCH',f"/hr/candidates/{target['id']}",422,json={**profile_body,'version':profile['version'],'telegram_username':'https://evil.example/profile'})
    legacy={k:profile[k] for k in ('version','status','priority','location','location_verified','notes')}
    legacy['notes']='Legacy client still preserves saved Telegram handle'
    profile=(await call('PATCH',f"/hr/candidates/{target['id']}",json=legacy)).json()
    assert profile['telegram_username']=='example_user'
    read=(await call('GET',f'/hr/vacancies/{vid}/candidates?q=First')).json()['items'][0]
    assert read['telegram_username']=='example_user'
    cleared=(await call('PATCH',f"/hr/candidates/{target['id']}",json={**legacy,'version':profile['version'],'telegram_username':None})).json()
    assert cleared['telegram_username'] is None and cleared['notes']==legacy['notes']
    client.headers['Authorization']='Bearer '+tokens[1]
    await call('GET',f'/hr/vacancies/{vid}/candidates',403)
    await call('PATCH',f"/hr/candidates/{low['id']}",403,json={**update,'version':2})
    await call('PATCH',quick,403,json={'version':restored['version'],'hidden':True})
    client.headers['Authorization']='Bearer '+tokens[0]
