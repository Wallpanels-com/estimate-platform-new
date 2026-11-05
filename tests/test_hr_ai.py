"""No external API calls: validate minimization, cache identity and evidence checks."""
import sys, unittest, json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/backend'))
from app.services.hr_ai import source_data, fingerprint, generate_review, AIUnavailable
from app.schemas.auth import UserCreate
from pydantic import ValidationError
class HRAITests(unittest.IsolatedAsyncioTestCase):
    def test_minimized_source_and_cache(self):
        c=SimpleNamespace(name='Private Name',phone='+380123456789',email='private@example.com',notes='Private notes',answers={'full_name':'Private Name','English_level':'B2','Years_of_experience':'5 years; contact private@example.com +380123456789','Current location':'Private place','Gender':'Private','ad_id':'meta','Опыт работы':'Residential projects','Nationality':'Private'})
        v=SimpleNamespace(name='Manager',description='Read drawings, email hiring@example.com')
        source=source_data(c,v);serialized=json.dumps(source)
        for private in ('Private Name','Private notes','private@example.com','+380123456789','Private place','hiring@example.com','Nationality','Gender'):
            self.assertNotIn(private,serialized)
        self.assertIn('English level',source['answers']);self.assertIn('Опыт работы',source['answers'])
        old=fingerprint(source);c.notes='Changed note';c.phone='changed';self.assertEqual(old,fingerprint(source_data(c,v)))
        v.description='New requirements';self.assertNotEqual(old,fingerprint(source_data(c,v)))
    def test_creation_access_validation(self):
        base=dict(email='example.user',name='Example',password='ExamplePassword123')
        self.assertEqual(UserCreate(**base,page_access=['hr','estimates']).page_access,['hr','estimates'])
        self.assertEqual(UserCreate(**base).page_access,[])
        for pages in (['not-a-page'],['hr','hr']):
            with self.assertRaises(ValidationError):UserCreate(**base,page_access=pages)
    async def test_bad_evidence_and_provider_errors_are_safe(self):
        source={'vacancy':'PM','requirements':'English','answers':{'English level':'B2'}}
        response={'summary':'Summary','experience':'Experience','strengths':[{'text':'Invented claim','question':'English level','answer':'C2'}],'gaps':[],'interview_questions':[],'message_uk':'Message'}
        fake=SimpleNamespace(status_code=200,is_success=True,json=lambda:{'choices':[{'message':{'content':json.dumps(response)}}]})
        with patch('app.services.hr_ai.settings.GROQ_API_KEY','test-secret'),patch('httpx.AsyncClient.post',new=AsyncMock(return_value=fake)):
            with self.assertRaises(AIUnavailable) as err:await generate_review(source)
            self.assertIn('verified',err.exception.message)
        response['strengths']=[{'text':'Stated English level','question':'English level','answer':'B2'}]*9
        fake=SimpleNamespace(status_code=200,is_success=True,json=lambda:{'choices':[{'message':{'content':json.dumps(response)}}]})
        with patch('app.services.hr_ai.settings.GROQ_API_KEY','test-secret'),patch('httpx.AsyncClient.post',new=AsyncMock(return_value=fake)) as transport:
            result=await generate_review(source)
            self.assertEqual(len(result['strengths']),6)
            self.assertNotIn('maxItems',json.dumps(transport.call_args.kwargs['json']['response_format']))
        fake=SimpleNamespace(status_code=401,is_success=False)
        with patch('app.services.hr_ai.settings.GROQ_API_KEY','test-secret'),patch('httpx.AsyncClient.post',new=AsyncMock(return_value=fake)):
            with self.assertRaises(AIUnavailable) as err:await generate_review(source)
            self.assertNotIn('test-secret',err.exception.message)
if __name__=='__main__':unittest.main()
