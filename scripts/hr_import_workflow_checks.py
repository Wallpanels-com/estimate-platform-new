"""Multi-sheet import checks in audit_workflows' disposable local schema only."""
from io import BytesIO
from openpyxl import Workbook

async def check_hr_import(call, client, tokens):
    client.headers['Authorization']='Bearer '+tokens[0]
    vacancy=(await call('POST','/hr/vacancies',201,json={'name':'Synthetic multi-sheet import'})).json()['id']
    original=(await call('POST',f'/hr/vacancies/{vacancy}/candidates',201,json={'name':'Existing manual','email':'manual@example.com','notes':'Keep note','status':'interview'})).json()
    workbook=Workbook();one=workbook.active;one.title='Українська'
    one.append(['id','ad_name','first_name','email','phone_number','Досвід?','Програми?'])
    for row in [('01','Ad','Alpha','alpha@example.com','p:+380671111111','5 years','CAD'),('02','Ad','Shared','shared@example.com','+380672222222','3 years','CAD'),('03','Ad','Manual','manual@example.com','','2 years','CAD'),('04','Ad','<test lead: fake>','test@example.com','','',''),('05','Ad','No contact','','','','')]:one.append(row)
    two=workbook.create_sheet('Русская');two.append(['campaign_id','имя','email','номер_телефона','Опыт?','Программы?'])
    for row in [('12','Shared again','other@example.com','+380 67 222 22 22','3 years','CAD'),('13','Beta','beta@example.com','','2 years','Other'),('14','Alpha again','','00380671111111','5 years','CAD')]:two.append(row)
    data=BytesIO();workbook.save(data)
    async def stage():return (await call('POST',f'/hr/vacancies/{vacancy}/imports',201,files={'file':('Synthetic.xlsx',data.getvalue(),'application/octet-stream')})).json()
    staged=await stage();assert len(staged['sheets'])==2
    selections=[]
    for s in staged['sheets']:
        assert len(s['answer_columns'])==2 and not set(s['answer_columns'])&set(s['technical_columns'])
        selections.append({'sheet':s['name'],'mapping':s['mapping'],'answer_columns':s['answer_columns'][:1]})
    path='/hr/imports/'+staged['id']
    await call('POST',path+'/preview',422,json={'sheets':[selections[0],selections[0]]})
    await call('POST',path+'/preview',422,json={'sheets':[]})
    await call('POST',path+'/preview',422,json={'sheets':selections,'sheet':'Українська'})
    bad={**selections[0],'answer_columns':['missing']}
    await call('POST',path+'/preview',422,json={'sheets':[bad]})
    duplicate_roles={**selections[0],'mapping':{**selections[0]['mapping'],'email':selections[0]['mapping']['name']}}
    await call('POST',path+'/preview',422,json={'sheets':[duplicate_roles]})
    single=(await call('POST',path+'/preview',json={'sheets':[selections[0]]})).json()
    assert (single['added'],single['duplicates'],single['invalid'],single['test_rows'])==(2,1,1,1)
    preview=(await call('POST',path+'/preview',json={'sheets':selections})).json()
    assert (preview['added'],preview['duplicates'],preview['invalid'],preview['test_rows'])==(3,3,1,1)
    assert len(preview['sheets'])==2
    assert (await call('GET',f'/hr/vacancies/{vacancy}/candidates')).json()['total']==1
    result=(await call('POST',path+'/confirm',json={'sheets':selections})).json();assert result['added']==3
    assert (await call('POST',path+'/confirm',json={'sheets':selections})).json()==result
    imported=(await call('GET',f'/hr/vacancies/{vacancy}/candidates')).json()['items'];assert len(imported)==4
    assert next(c for c in imported if c['id']==original['id'])==original
    for c in imported:
        if c['id']==original['id']:continue
        assert len(c['answers'])==1
        assert set(c['answers']).issubset({'Досвід?','Опыт?'})
        assert c['status']=='new' and not c['priority']
    again=await stage()
    assert (await call('POST',f'/hr/imports/{again["id"]}/confirm',json={'sheets':selections})).json()['added']==0
    # All questions can be unchecked without losing the candidate contacts.
    empty=await stage();s=empty['sheets'][1]
    check=(await call('POST',f'/hr/imports/{empty["id"]}/preview',json={'sheets':[{'sheet':s['name'],'mapping':s['mapping'],'answer_columns':[]}]})).json()
    assert check['added']==0 and check['duplicates']==3
