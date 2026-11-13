"""Verify extraction evidence, arithmetic and failure paths without provider access."""
import sys, unittest, json, asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
import httpx
from fastapi import HTTPException
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/backend'))
from app.services.manual_import_ai import amount, verified_rows, parse_list


def row(**kw):
    return dict(source_lines=[1],kind='item',name='Cabinets',section='General',
                quantity=None,unit='ea',unit_price=None,total_price=None,**kw)


class ManualImportAITests(unittest.IsolatedAsyncioTestCase):
    def test_exact_source_numbers(self):
        for source, expected in [('3000?','3000.00'),('17,6','17.60'),('1,558.61','1558.61'),('1.558,61','1558.61'),('1 558,61','1558.61'),('0','0.00')]:
            self.assertEqual(amount(source, 'Cabinet $'+source), expected)
        for value, source in [('10','-10'),('55','550'),('50','500'),('12','12.5'),('-10','-10'),('1e3','1e3'),('NaN','NaN')]:
            with self.assertRaises(ValueError): amount(value,source)

    def test_math_not_delegated_to_model(self):
        r=row();r.update(quantity='17,6',unit_price='1200',unit='LF')
        result=verified_rows({'rows':[r]},['Cabinets 17,6 Lin x 1200'])[0]
        self.assertEqual(result['total_price'],'21120.00');self.assertTrue(result['review'])
        r.update(quantity='3',unit_price='10',total_price='20')
        result=verified_rows({'rows':[r]},['Cabinets 3 x 10 = 20'])[0]
        self.assertEqual(result['total_price'],'20.00') # Preserve mismatch for explicit review.
        r.update(quantity='0.05',unit_price='0.10',total_price=None)
        self.assertEqual(verified_rows({'rows':[r]},['Item 0.05 x 0.10'])[0]['total_price'],'0.01')

    def test_no_dropped_or_invented_lines(self):
        r=row();r['total_price']='100'
        with self.assertRaises(ValueError): verified_rows({'rows':[r]},['Item 100','Other 200'])
        with self.assertRaises(ValueError): verified_rows({'rows':[r]},['Item 200'])
        with self.assertRaises(ValueError): verified_rows({'rows':[r,r]},['Item 100','Other 100'])
        second={**r,'source_lines':[2]}
        with self.assertRaises(ValueError): verified_rows({'rows':[second,r]},['Item 100','Other 100'])
        heading={**r,'kind':'heading','total_price':None}
        result=verified_rows({'rows':[heading]},['Cabinets 100:'])
        self.assertEqual(len(result),1);self.assertEqual(result[0]['total_price'],'')
        result=verified_rows({'rows':[{**heading,'source_lines':[1]},second]},['Bar:','Item 100'])
        self.assertEqual(len(result),1)
        result=verified_rows({'rows':[{**r,'kind':'unparsed'}]},['Grand total 100'])
        self.assertEqual(result[0]['total_price'],'')

    async def test_failures_and_retry_do_not_leak_key(self):
        with patch('app.services.manual_import_ai.settings.MANUAL_IMPORT_GROQ_API_KEY',''):
            with self.assertRaises(HTTPException) as e: await parse_list('Item 10','user')
            self.assertEqual(e.exception.status_code,503)
        with patch('app.services.manual_import_ai.settings.MANUAL_IMPORT_GROQ_API_KEY','test-secret'):
            for status in [401,429,500]:
                fake=SimpleNamespace(status_code=status,is_success=False)
                with patch('httpx.AsyncClient.post',new=AsyncMock(return_value=fake)):
                    with self.assertRaises(HTTPException) as e: await parse_list('Item 10','user')
                    self.assertEqual(e.exception.status_code,429 if status==429 else 503)
                    self.assertNotIn('test-secret',e.exception.detail)
            with patch('httpx.AsyncClient.post',new=AsyncMock(side_effect=httpx.ReadTimeout('test-secret'))):
                with self.assertRaises(HTTPException) as e: await parse_list('Item 10','user')
                self.assertNotIn('test-secret',e.exception.detail)
            fake=SimpleNamespace(status_code=200,is_success=True,json=lambda:{'choices':[{'finish_reason':'length','message':{'content':'{}'}}]})
            with patch('httpx.AsyncClient.post',new=AsyncMock(return_value=fake)):
                with self.assertRaises(HTTPException) as e: await parse_list('Item 10','user')
                self.assertEqual(e.exception.status_code,502)
            r=row();r['total_price']='10'
            fake.json=lambda:{'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'rows':[r]})}}]}
            with patch('httpx.AsyncClient.post',new=AsyncMock(return_value=fake)) as transport:
                self.assertEqual((await parse_list('Item 10','user'))['rows'][0]['total_price'],'10.00')
                self.assertTrue(transport.call_args.kwargs['json']['response_format']['json_schema']['strict'])

    async def test_concurrent_same_user(self):
        started=asyncio.Event();release=asyncio.Event()
        async def slow(*a,**kw):
            started.set();await release.wait()
            return SimpleNamespace(status_code=503,is_success=False)
        with patch('app.services.manual_import_ai.settings.MANUAL_IMPORT_GROQ_API_KEY','test-secret'),patch('httpx.AsyncClient.post',new=slow):
            task=asyncio.create_task(parse_list('Item 10','same'))
            await started.wait()
            with self.assertRaises(HTTPException) as e: await parse_list('Item 10','same')
            self.assertEqual(e.exception.status_code,429)
            release.set()
            with self.assertRaises(HTTPException): await task

if __name__=='__main__':unittest.main()
