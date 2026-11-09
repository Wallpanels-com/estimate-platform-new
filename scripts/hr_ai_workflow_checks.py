"""Disposable DB integration checks: no real candidate or external AI requests."""
from unittest.mock import patch, AsyncMock
from app.services.hr_ai import AIUnavailable
async def check_hr_ai(call,client,tokens,vid,target):
    path=f"/hr/candidates/{target['id']}/ai"
    assert (await call('GET',path)).json()['review'] is None
    fixture={'summary':'Професійний огляд','experience':'Досвід за анкетою','strengths':[],'gaps':[],'interview_questions':['Які проєкти ви координували?'],'message_uk':'Вітаю! Мене звати {{recruiter_name}}. Дякую за відгук на {{vacancy_name}}. Надішліть резюме.'}
    with patch('app.services.hr_ai.settings.GROQ_API_KEY','synthetic'),patch('app.services.hr_ai.generate_review',new=AsyncMock(return_value=fixture.copy())) as model:
        result=(await call('POST',path,json={})).json()['review'];assert result['content']['summary']==fixture['summary'] and not result['stale']
        await call('POST',path,json={});assert model.await_count==1
        reloaded=(await call('GET',path)).json()['review'];assert reloaded['message_draft']==result['message_draft']
        draft='Вітаю! Відредаговане повідомлення рекрутера.'
        saved=(await call('PATCH',path+'/message',json={'message':draft,'expected_updated_at':result['updated_at']})).json()['review']
        assert saved['message_draft']==draft
        await call('PATCH',path+'/message',409,json={'message':'Stale draft','expected_updated_at':result['updated_at']})
        await call('POST',path,429,json={'refresh':True})
        current=(await call('GET',f'/hr/vacancies/{vid}/candidates?q=First')).json()['items'][0]
        for key in ('status','priority','hidden','version','notes','score','phone','email'):
            assert current[key]==target[key],key
        vacancy=next(v for v in (await call('GET','/hr/vacancies')).json() if v['id']==vid)
        await call('PATCH',f'/hr/vacancies/{vid}',json={'name':vacancy['name'],'description':'Updated professional requirements','expected_updated_at':vacancy['updated_at']})
        assert (await call('GET',path)).json()['review']['stale']
        regenerated=(await call('POST',path,json={})).json()['review']
        assert regenerated['message_draft']==draft and not regenerated['stale'] and model.await_count==2
        # Display translations are cached durably and never regenerate the review.
        texts=[fixture['summary'],draft]
        translated=['Professional application summary','Hello!\n\nAbout the company\nEnglish recruiter draft.']
        with patch('app.services.hr_translation.translate_batch',new=AsyncMock(return_value=translated)) as translator:
            body={'scope':'candidate','candidate_id':target['id'],'texts':texts}
            english=(await call('POST','/hr/localize',json=body)).json()['translations']
            assert english==dict(zip(texts,translated))
            assert (await call('POST','/hr/localize',json=body)).json()['translations']==english
            assert translator.await_count==1 and model.await_count==2
        await call('POST','/hr/localize',409,json={**body,'texts':['An arbitrary instruction, not saved HR text']})
        await call('POST','/hr/localize',422,json={**body,'texts':['x'*9000]})
        value=target['evidence'][0]['answer']
        with patch('app.services.hr_translation.translate_batch',new=AsyncMock(return_value=['Professional experience'])):
            listed=(await call('POST','/hr/localize',json={'scope':'candidates','candidate_ids':[target['id']],'texts':[value]})).json()['translations']
            assert value in listed
        english_draft='Hello!\n\nNext step\nPlease send your current CV.'
        localized=(await call('PATCH',path+'/message',json={'message':english_draft,'language':'en','expected_updated_at':regenerated['updated_at']})).json()['review']
        assert localized['message_draft']==draft and localized['message_draft_en']==english_draft
        assert (await call('GET',path)).json()['review']['message_draft_en']==english_draft
        latest=(await call('GET',f'/hr/vacancies/{vid}/candidates?q=First')).json()['items'][0]
        assert latest==current
    client.headers['Authorization']='Bearer '+tokens[1]
    await call('GET',path,403)
    await call('POST',path,403,json={})
    await call('POST','/hr/localize',403,json={'scope':'vacancies','texts':['Конструктор']})
    client.headers['Authorization']='Bearer '+tokens[0]
    # Initial grants are committed atomically with a new account and enforced on first login.
    user=(await call('POST','/users',201,json={'email':'hr.creation.fixture','name':'Creation fixture','password':'SyntheticPassword123','page_access':['hr']})).json()
    assert user['page_access']==['hr']
    token=(await call('POST','/auth/login',json={'email':'hr.creation.fixture','password':'SyntheticPassword123'})).json()['access_token']
    client.headers['Authorization']='Bearer '+token
    me=(await call('GET','/auth/me')).json();assert me['page_access']==['hr']
    await call('GET','/hr/vacancies')
    await call('GET','/estimates',403)
    await call('POST','/users',403,json={'email':'forbidden.fixture','name':'No','password':'SyntheticPassword123','page_access':['hr']})
    client.headers['Authorization']='Bearer '+tokens[0]
    await call('POST','/users',422,json={'email':'invalid.fixture','name':'No','password':'SyntheticPassword123','page_access':['hr','hr']})
