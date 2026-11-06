"""Authenticated workflow audit in a disposable loopback schema and temporary files."""
import asyncio
from contextlib import asynccontextmanager
from io import BytesIO
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from urllib.parse import urlsplit
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'apps/backend'))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')
import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from fastapi import Request
from PIL import Image
from pypdf import PdfReader
from openpyxl import load_workbook
from app.main import app
from app.core.database import Base,get_db
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User

async def main():
    url=settings.DATABASE_URL
    if urlsplit(url.replace('postgresql+asyncpg:','postgresql:')).hostname not in ('localhost','127.0.0.1','::1'):
        raise SystemExit('Only loopback PostgreSQL is allowed.')
    schema='audit_'+uuid.uuid4().hex
    admin=create_async_engine(url)
    async with admin.begin() as conn:await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine=create_async_engine(url,connect_args={'server_settings':{'search_path':schema}})
    sessions=async_sessionmaker(engine,expire_on_commit=False)
    checks=[]; timings={}
    temporary=tempfile.TemporaryDirectory(prefix='wallpanels-audit-')
    previous_storage=settings.STORAGE_PATH; settings.STORAGE_PATH=temporary.name
    previous_owner=settings.ACCESS_MANAGER_USER_ID
    async def database(request: Request):
        async with sessions() as db:
            request.state.estimate_session=db
            db.info['expected_revision']=request.headers.get('If-Match')
            db.info['write_request']=request.method not in ('GET','HEAD','OPTIONS')
            try:yield db;await db.commit()
            except Exception:await db.rollback();raise
    app.dependency_overrides[get_db]=database
    try:
        async with engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)
        password=uuid.uuid4().hex
        async with sessions() as db:
            for login in ('audit.one','audit.two'):
                db.add(User(email=login,name=login.title(),password_hash=get_password_hash(password),role='user',onboarding_completed=True))
            await db.commit()
        async with sessions() as db:
            settings.ACCESS_MANAGER_USER_ID=(await db.execute(text("SELECT id FROM users WHERE email='audit.one'"))).scalar_one()
            access_target=(await db.execute(text("SELECT id FROM users WHERE email='audit.two'"))).scalar_one()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://audit.local/api/v1',timeout=120) as c:
            async def call(method,path,expected=200,**kwargs):
                r=await c.request(method,path,**kwargs)
                assert r.status_code==expected,(method,path,r.status_code,r.text[:200])
                checks.append(f'{method} {path}: {expected}')
                return r
            await call('GET','/auth/me',403)
            await call('POST','/auth/login',401,json={'email':'audit.one','password':'incorrect'})
            tokens=[]
            for login in ('audit.one','audit.two'):
                tokens.append((await call('POST','/auth/login',json={'email':login,'password':password})).json()['access_token'])
            c.headers['Authorization']='Bearer '+tokens[0]
            await call('GET','/auth/me')
            from hr_workflow_checks import check_hr
            await check_hr(call,c,tokens)
            from staff_workflow_checks import check_staff
            await check_staff(call,c,tokens)
            est=(await call('POST','/estimates',201,json={'type':'pre','title':'Isolated workflow audit','client_name':'Local fixture'})).json()
            eid=est['id']; zid=est['zones'][0]['id']; path=f'/estimates/{eid}'
            revision=est['revision']
            c.headers['If-Match']=revision
            await call('PATCH',path,json={'project_name':'Saved by employee one'})
            # A second session with the same stale revision must be rejected.
            c.headers['Authorization']='Bearer '+tokens[1]
            await call('PATCH',path,409,json={'project_name':'Stale overwrite'})
            async def refresh():
                latest=(await call('GET',path)).json();c.headers['If-Match']=latest['revision'];return latest
            latest=await refresh();assert latest['project_name']=='Saved by employee one'
            await call('PATCH',path,json={'project_name':'Saved by employee two'})
            latest=await refresh()
            simultaneous=await asyncio.gather(*[
                c.patch(path,headers={'Authorization':'Bearer '+tokens[i],'If-Match':latest['revision']},json={'project_name':f'Concurrent employee {i+1}'}) for i in range(2)
            ])
            assert sorted(r.status_code for r in simultaneous)==[200,409]
            checks.append('Simultaneous edits: one save, one 409; no lost update')

            # Persisted proposal branding uses the same row lock and revision guard.
            latest=await refresh()
            branded=(await call('PATCH',path+'/proposal-brand',json={'brand':'verona'})).json()
            assert branded['pdf_layout']['proposal_brand']=='verona'
            await call('PATCH',path+'/proposal-brand',409,json={'brand':'wallpanels'})
            latest=await refresh();assert latest['pdf_layout']['proposal_brand']=='verona'
            await call('PATCH',path+'/proposal-brand',422,json={'brand':'unknown'})
            pre_id=eid

            for i in range(1,12):
                await refresh()
                await call('POST',path+'/zones',201,json={'label':f'Area {i+1}','zone_type':'wall'})
            latest=await refresh(); zones=latest['zones']; assert len(zones)==12
            photo=BytesIO();Image.new('RGB',(1200,800),'#cbbba0').save(photo,format='JPEG',quality=95)
            for index,z in enumerate(zones):
                await refresh()
                await call('POST',f'{path}/zones/{z["id"]}/images/1',200,files={'file':('photo.jpg',photo.getvalue(),'image/jpeg')})
                for j in range(1 if index else 12):
                    await refresh()
                    await call('POST',path+'/line-items',201,json={'zone_id':z['id'],'name':f'Component {j+1}','quantity':10,'unit':'SF','unit_price':25,'calc_type':'sf'})
            latest=await refresh();total=latest['subtotal']; assert float(total)==5750
            image_id=latest['zones'][0]['images'][0]['id']
            media=await call('GET',f'/media/{image_id}'); assert media.content==photo.getvalue()
            await call('POST',f'{path}/zones/{zid}/images/5',400,files={'file':('photo.jpg',photo.getvalue(),'image/jpeg')})
            await refresh();await call('POST',path+'/zones/reorder',json=[z['id'] for z in reversed(zones)])
            await refresh();await call('PATCH',path,json={'markup_pct':10,'discount_pct':5})
            for mode in ('pre','final'):
                if mode=='final':
                    await refresh();est=(await call('POST',path+'/mode',json={'mode':'final'})).json();eid=est['id'];path=f'/estimates/{eid}';await refresh()
                before=(await refresh())
                assert before['pdf_layout']['proposal_brand']=='verona'
                start=time.perf_counter();r=await call('GET',f'/pdf/{eid}/{mode}-estimate');timings[mode+'_pdf_seconds']=round(time.perf_counter()-start,3)
                pdf=PdfReader(BytesIO(r.content));assert len(pdf.pages)>29
                assert pdf.metadata['/WallPanelsCompanySlidesCount']=='29'
                assert r.headers['x-proposal-brand']=='verona'
                assert 'Verona%20Home' in r.headers['content-disposition']
                assert r.headers.get('content-type','').startswith('application/pdf')
                # Attachment uses the same renderer and page order; no business data mutation.
                attachment=await call('GET',f'/pdf/{eid}/{mode}-estimate?download=true');other=PdfReader(BytesIO(attachment.content))
                assert len(other.pages)==len(pdf.pages)
                assert [p.extract_text() for p in other.pages]==[p.extract_text() for p in pdf.pages]
                start=time.perf_counter();xlsx=await call('GET',f'/pdf/{eid}/passport');timings[mode+'_xlsx_seconds']=round(time.perf_counter()-start,3)
                workbook=load_workbook(BytesIO(xlsx.content));assert workbook.active['C3'].value=='Local fixture'
                after=await refresh();assert after['subtotal']==before['subtotal']==total
            await refresh();await call('PATCH',path+'/proposal-brand',json={'brand':'wallpanels'})
            assert (await call('GET',f'/estimates/{pre_id}')).json()['pdf_layout']['proposal_brand']=='verona'
            history=(await call('GET',path+'/history?limit=500')).json();assert history and len({row['actor_name'] for row in history})==2
            # Shared visibility and recovery through a fresh authenticated session.
            c.headers['Authorization']='Bearer '+tokens[0]
            assert (await call('GET','/estimates')).json()
            await refresh();copy=(await call('POST',path+'/duplicate',201)).json();copy_path=f'/estimates/{copy["id"]}'
            c.headers['If-Match']=copy['revision'];await call('DELETE',copy_path,204)
            assert (await call('GET','/estimates/trash')).json()
            latest=(await call('GET',copy_path)).json();c.headers['If-Match']=latest['revision'];await call('POST',copy_path+'/restore')
            # Price Book edits are isolated; verify revision conflict protection.
            config=(await call('GET','/pricing/config')).json()
            await call('PUT','/pricing/config',json={'config':config['config'],'expected_revision':config['revision']})
            await call('GET','/pricing/schema');await call('GET','/pricing/catalog')
            category=(await call('POST','/pricing/catalog/categories',201,json={'name':'Audit finishes','icon':'folder'})).json()
            item=(await call('POST','/pricing/catalog/items',201,json={'category_id':category['id'],'name':'Audit panel','unit':'SF','unit_price':'12.50'})).json()
            c.headers['Authorization']='Bearer '+tokens[1]
            catalog=(await call('GET','/pricing/catalog')).json()
            assert any(i['id']==item['id'] for i in catalog['items'])
            quote=(await call('POST',f"/pricing/catalog/items/{item['id']}/quote",json={'quantity':'4'})).json()
            assert float(quote['total_price'])==50
            edited=(await call('PUT',f"/pricing/catalog/items/{item['id']}",json={'category_id':category['id'],'name':'Updated audit panel','unit':'SF','unit_price':'15.00','expected_version':item['version']})).json()
            await call('PUT',f"/pricing/catalog/items/{item['id']}",409,json={'category_id':category['id'],'name':'Stale panel','unit_price':'1.00','expected_version':item['version']})
            archived=(await call('PUT',f"/pricing/catalog/items/{item['id']}",json={'category_id':category['id'],'name':edited['name'],'unit':'SF','unit_price':'15.00','archived':True,'expected_version':edited['version']})).json()
            await call('DELETE',f"/pricing/catalog/items/{item['id']}?expected_version={archived['version']}",204)

            # Owner-managed page grants persist in fresh sessions and act on a
            # previously issued token immediately; no employee data is rewritten.
            owner_headers={'Authorization':'Bearer '+tokens[0]}
            staff_headers={'Authorization':'Bearer '+tokens[1]}
            c.headers.update(owner_headers)
            new_user=(await call('POST','/users',201,json={'email':'audit.new','name':'New employee','password':password})).json()
            assert new_user['page_access']==[]
            new_token=(await call('POST','/auth/login',json={'email':'audit.new','password':password})).json()['access_token']
            assert (await call('GET','/auth/me',headers={'Authorization':'Bearer '+new_token})).json()['page_access']==[]
            await call('GET','/estimates',403,headers={'Authorization':'Bearer '+new_token})
            grant_path=f'/users/{access_target}/access'
            original=(await call('GET',grant_path)).json()
            await call('PUT',grant_path,json={'pages':['estimates'],'expected_updated_at':original['updated_at']})
            await call('PUT',grant_path,409,json={'pages':[],'expected_updated_at':original['updated_at']})
            current=(await call('GET',grant_path)).json();assert current['pages']==['estimates']
            assert (await call('GET','/auth/me',headers=staff_headers)).json()['page_access']==['estimates']
            await call('GET','/estimates',headers=staff_headers)
            await call('GET','/pricing/schema',headers=staff_headers)
            await call('POST','/pricing/calc/wall',json={'square_footage':100},headers=staff_headers)
            for method,target,body in [('GET','/users',None),('GET','/estimates/trash',None),('PUT','/pricing/config',{}),('POST','/users',{}),('POST',f'/users/{settings.ACCESS_MANAGER_USER_ID}/password',{'password':'not-a-real-password'}),('PUT',grant_path,{'pages':list(('estimates','quick_estimate','price_book','users','trash')),'expected_updated_at':current['updated_at']})]:
                await call(method,target,403,headers=staff_headers,**({'json':body} if body is not None else {}))
            await call('PUT',grant_path,json={'pages':[],'expected_updated_at':current['updated_at']})
            assert (await call('GET','/auth/me',headers=staff_headers)).json()['page_access']==[]
            for target in ('/estimates','/pricing/schema',f'/pdf/{eid}/final-estimate',f'/media/{image_id}'):
                await call('GET',target,403,headers=staff_headers)
            current=(await call('GET',grant_path)).json()
            await call('PUT',grant_path,json={'pages':['quick_estimate'],'expected_updated_at':current['updated_at']})
            quick=(await call('POST','/estimates',201,json={'type':'quick','title':'Isolated restricted Quick'},headers=staff_headers)).json()
            await call('GET',f'/estimates/{quick['id']}',headers=staff_headers)
            await call('GET',path,403,headers=staff_headers)
            await call('POST','/estimates',403,json={'type':'pre'},headers=staff_headers)
            await call('PATCH',f'/estimates/{quick['id']}',403,json={'type':'pre'},headers=staff_headers)
            me=(await call('GET','/auth/me')).json();assert me['can_manage_access'] and len(me['page_access'])==6
            own=(await call('GET',f'/users/{me['id']}/access')).json()
            await call('PUT',f'/users/{me['id']}/access',409,json={'pages':[],'expected_updated_at':own['updated_at']})
            events=(await call('GET','/audit')).json();assert any('page_access' in event['changes'] for event in events)

        report={'checks_passed':len(checks),'isolation':'temporary PostgreSQL schema; temporary storage; two synthetic accounts','timings':timings,'checks':checks}
        output=ROOT/'.local/audit/workflows.json';output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2))
        print(json.dumps({'checks_passed':len(checks),'timings':timings},indent=2))
    finally:
        app.dependency_overrides.pop(get_db,None);settings.STORAGE_PATH=previous_storage;settings.ACCESS_MANAGER_USER_ID=previous_owner
        await engine.dispose()
        async with admin.begin() as conn:await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose();temporary.cleanup()
if __name__=='__main__':asyncio.run(main())
