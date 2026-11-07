"""Manual candidates, shared status management, filters and private file round trips in the disposable schema."""
async def check_hr_tools(call, client, tokens):
    client.headers['Authorization']='Bearer '+tokens[0]
    v=(await call('POST','/hr/vacancies',201,json={'name':'Isolated tools vacancy'})).json()['id']
    statuses=(await call('GET','/hr/statuses')).json();new=next(s for s in statuses if s['key']=='new')
    custom=(await call('POST','/hr/statuses',201,json={'name_en':'Portfolio review','name_ru':'Проверка портфолио'})).json()
    await call('POST','/hr/statuses',409,json={'name_en':'portfolio review'})
    renamed=(await call('PATCH','/hr/statuses/'+custom['key'],json={'name_en':'Portfolio ready','name_ru':'Портфолио получено','version':custom['version']})).json()
    await call('PATCH','/hr/statuses/'+custom['key'],409,json={'name_en':'Stale','version':custom['version']})
    await call('POST',f'/hr/vacancies/{v}/candidates',422,json={'name':'Missing contact'})
    c=(await call('POST',f'/hr/vacancies/{v}/candidates',201,json={'name':'Manual Alpha','email':'alpha@example.com','telegram_username':'@alpha_user','status':renamed['key'],'notes':'Keep this note','experience':'5+ years','english':'Fluent','us_market':'3+ years','drawings':'advanced'})).json()
    await call('POST',f'/hr/vacancies/{v}/candidates',409,json={'name':'Duplicate','email':'ALPHA@example.com'})
    await call('POST',f'/hr/vacancies/{v}/candidates',201,json={'name':'Manual Beta','phone':'+15550102000'})
    for suffix,expected in [('contact=email',1),('contact=telegram',1),('notes=true',1),('score_min=80',1),('score_max=0',0),('q=Beta',1)]:
        assert (await call('GET',f'/hr/vacancies/{v}/candidates?'+suffix)).json()['total']==expected
    await call('GET',f'/hr/vacancies/{v}/candidates?score_min=90&score_max=10',422)
    data=b'<html>Arbitrary attachment is downloaded, never executed</html>'
    f=(await call('POST',f'/hr/candidates/{c["id"]}/files',201,files={'file':('../resume.html',data,'text/html')})).json()
    assert f['name']=='resume.html' and f['size']==len(data)
    listed=(await call('GET',f'/hr/candidates/{c["id"]}/files')).json();assert listed[0]['id']==f['id']
    response=await call('GET','/hr/candidate-files/'+f['id']);assert response.content==data
    assert response.headers['content-type']=='application/octet-stream' and 'attachment' in response.headers['content-disposition']
    await call('GET','/hr/candidate-files/'+f['id'],403,headers={'Authorization':''})
    await call('POST',f'/hr/candidates/{c["id"]}/files',422,files={'file':('empty.txt',b'','text/plain')})
    await call('DELETE','/hr/statuses/'+renamed['key'],422,json={'version':renamed['version'],'replacement':renamed['key']})
    await call('DELETE','/hr/statuses/'+renamed['key'],json={'version':renamed['version'],'replacement':'review'})
    fresh=(await call('GET',f'/hr/vacancies/{v}/candidates?q=Alpha')).json()['items'][0]
    assert fresh['status']=='review' and fresh['version']==c['version']+1
    assert all(fresh[k]==c[k] for k in ('notes','answers','email','phone','score','priority'))
    assert not any(s['key']==renamed['key'] for s in (await call('GET','/hr/statuses')).json())
    await call('POST',f'/hr/vacancies/{v}/candidates',422,json={'name':'Removed status','email':'removed@example.com','status':renamed['key']})
    await call('DELETE','/hr/statuses/new',409,json={'version':max(1,new['version']),'replacement':'review'})
