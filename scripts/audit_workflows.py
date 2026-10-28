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
                start=time.perf_counter();r=await call('GET',f'/pdf/{eid}/{mode}-estimate');timings[mode+'_pdf_seconds']=round(time.perf_counter()-start,3)
                pdf=PdfReader(BytesIO(r.content));assert len(pdf.pages)>13
                assert r.headers.get('content-type','').startswith('application/pdf')
                # Attachment uses the same renderer and page order; no business data mutation.
                attachment=await call('GET',f'/pdf/{eid}/{mode}-estimate?download=true');other=PdfReader(BytesIO(attachment.content))
                assert len(other.pages)==len(pdf.pages)
                assert [p.extract_text() for p in other.pages]==[p.extract_text() for p in pdf.pages]
                start=time.perf_counter();xlsx=await call('GET',f'/pdf/{eid}/passport');timings[mode+'_xlsx_seconds']=round(time.perf_counter()-start,3)
                workbook=load_workbook(BytesIO(xlsx.content));assert workbook.active['C3'].value=='Local fixture'
                after=await refresh();assert after['subtotal']==before['subtotal']==total
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

        report={'checks_passed':len(checks),'isolation':'temporary PostgreSQL schema; temporary storage; two synthetic accounts','timings':timings,'checks':checks}
        output=ROOT/'.local/audit/workflows.json';output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2))
        print(json.dumps({'checks_passed':len(checks),'timings':timings},indent=2))
    finally:
        app.dependency_overrides.pop(get_db,None);settings.STORAGE_PATH=previous_storage
        await engine.dispose()
        async with admin.begin() as conn:await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose();temporary.cleanup()
if __name__=='__main__':asyncio.run(main())
