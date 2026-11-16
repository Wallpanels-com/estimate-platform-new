"""Sales pilot: immutable owner boundary, GET-only CRM, evidence validation."""
import sys,uuid,json
from pathlib import Path
from types import SimpleNamespace as O
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch
import httpx
from fastapi import HTTPException
from starlette.requests import Request
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/backend'))
from app.services.page_access import can_view_sales,authorize_request
from app.core.config import settings
from app.services.sales.client import GhlClient
from app.services.sales.store import clean_payload,stamp
from app.services.sales.analysis import validate_review

class OwnerBoundary(IsolatedAsyncioTestCase):
    async def test_only_immutable_active_owner_with_correct_portal_identity(self):
        ident=uuid.uuid4();owner=O(id=ident,is_active=True,page_access=[])
        with patch.object(settings,'ACCESS_MANAGER_USER_ID',ident):
            self.assertTrue(can_view_sales(owner))
            employee=O(id=uuid.uuid4(),is_active=True,page_access=['sales','sales_control'],role='admin')
            self.assertFalse(can_view_sales(employee))
            for identity,allowed in [(dict(owner=True,module='estimating'),True),(dict(owner=True,module=None),True),(dict(owner=True,module='hr'),False),(dict(owner=False,module=None),False)]:
                owner._portal_profile=identity;self.assertEqual(can_view_sales(owner),allowed)
            owner._portal_profile=dict(owner=True,module='estimating')
            for endpoint in ('/sales/status','/sales/export','/sales/contacts/example','/sales/recordings/call'):
                request=Request({'type':'http','method':'GET','path':'/api/v1'+endpoint,'headers':[],'query_string':b''})
                await authorize_request(owner,O(),request)
                with self.assertRaises(HTTPException):await authorize_request(employee,O(),request)
            for method in ('POST','PUT','PATCH','DELETE'):
                with self.assertRaises(HTTPException) as e:await authorize_request(owner,O(),Request({'type':'http','method':method,'path':'/api/v1/sales/numbers','headers':[],'query_string':b''}))
                self.assertEqual(e.exception.status_code,405)
            owner.is_active=False;self.assertFalse(can_view_sales(owner))

class UpstreamBoundary(IsolatedAsyncioTestCase):
    async def test_advanced_search_is_fixed_readonly_operation(self):
        seen=[]
        async def handle(request):
            seen.append(request);return httpx.Response(201,json={'opportunities':[],'total':0})
        with patch.object(settings,'SALES_GHL_TOKEN','synthetic'),patch.object(settings,'SALES_GHL_LOCATION_ID','location'):
            c=GhlClient(transport=httpx.MockTransport(handle))
            try:await c.search_changed_opportunities('2026-11-15T00:00:00Z','2026-11-16T00:00:00Z',[123,'id'])
            finally:await c.close()
        request=seen[0];body=json.loads(request.content)
        self.assertEqual(str(request.url),'https://services.leadconnectorhq.com/opportunities/search')
        self.assertEqual(request.method,'POST');self.assertEqual(request.headers['Version'],'v3')
        self.assertEqual(set(body),{'locationId','limit','filters','sort','searchAfter'})
        self.assertEqual(body['filters'][0]['field'],'date_updated')
        self.assertEqual(body['locationId'],'location')

    async def test_get_allowlist_no_redirects_or_mutation_surface(self):
        seen=[]
        async def handle(request):
            seen.append((request.method,str(request.url)));return httpx.Response(200,json={'users':[]})
        with patch.object(settings,'SALES_GHL_TOKEN','synthetic'):
            c=GhlClient(transport=httpx.MockTransport(handle))
            try:
                await c.get('/users/',{'locationId':'test'})
                for path in ('https://evil.example/users/','/contacts/a/../b','/users/a','/voice-ai/agents/a','/phone-system/numbers/location/a/purchase'):
                    with self.assertRaises(ValueError):await c.get(path)
                self.assertFalse(hasattr(c,'post'));self.assertFalse(hasattr(c,'delete'))
            finally:await c.close()
        self.assertEqual(len(seen),1);self.assertEqual(seen[0][0],'GET');self.assertTrue(seen[0][1].startswith('https://services.leadconnectorhq.com/'))

class Evidence(TestCase):
    def test_invented_and_empty_quotes_are_rejected_and_outcome_recomputed(self):
        def finding(quote):return dict(kind='issue',severity='concern',source_id='m1',quote=quote,explanation='Check',recommendation='Verify',confidence='high')
        raw=dict(summary='Review',outcome='review_needed',findings=[finding('invented'),finding('')],next_steps=[],limitations=[],lead_reasons=[])
        r=validate_review(raw,[{'id':'m1','text':'Confirmed price requires measurement.'}]);self.assertEqual(r['findings'],[]);self.assertEqual(r['outcome'],'no_significant_issues')
        raw['findings']=[finding('requires measurement')];self.assertEqual(len(validate_review(raw,[{'id':'m1','text':'Confirmed price requires measurement.'}])['findings']),1)
    def test_nested_credentials_are_not_mirrored(self):
        self.assertEqual(clean_payload({'actions':[{'apiKey':'secret','actionParameters':{'authenticationValue':'secret','headers':{'Authorization':'secret'},'description':'Keep'}}],'name':'agent'}),{'actions':[{'actionParameters':{'description':'Keep'}}],'name':'agent'})
    def test_timestamp_formats(self):
        self.assertEqual(stamp(1700000000000),stamp('1700000000000'));self.assertIsNone(stamp('bad'));self.assertIsNotNone(stamp('2026-11-16T10:00:00Z'))
        self.assertEqual(stamp('2026-11-16T05:00:00-05:00'),stamp('2026-11-16T10:00:00Z'))

class SyncCursors(IsolatedAsyncioTestCase):
    async def test_change_search_keeps_cursor_and_replays_overlap(self):
        from unittest.mock import AsyncMock
        from datetime import timedelta
        from app.services.sales.sync import sync_resource
        from app.services.sales.store import now
        row=O(state={},next_run=now()-timedelta(seconds=1),last_success=None,error=None)
        client=O(search_changed_opportunities=AsyncMock(side_effect=[{'opportunities':[{'id':str(i),'sort':[i,str(i)]} for i in range(100)],'total':101},{'opportunities':[{'id':'100','sort':[100,'100']}],'total':101}]))
        with patch('app.services.sales.sync.state_for',AsyncMock(return_value=row)),patch('app.services.sales.sync.save_opportunity',AsyncMock()) as save:
            await sync_resource(O(),client,'opportunity_changes')
            until=row.state['until'];self.assertEqual(row.state['cursor'],[99,'99'])
            row.next_run=now()-timedelta(seconds=1)
            await sync_resource(O(),client,'opportunity_changes')
            self.assertTrue(row.state['complete']);self.assertEqual(row.state['loaded'],101)
            self.assertEqual(stamp(row.state['checkpoint']),stamp(until)-timedelta(minutes=5))
            self.assertEqual(save.await_count,101)
            self.assertEqual(client.search_changed_opportunities.call_args.args[2],[99,'99'])

    async def test_incomplete_number_list_never_retires_records(self):
        from unittest.mock import AsyncMock
        from datetime import timedelta
        from app.services.sales.sync import sync_resource
        from app.services.sales.client import GhlError
        from app.services.sales.store import now
        row=O(state={},next_run=now()-timedelta(seconds=1))
        client=O(get=AsyncMock(side_effect=[{'numbers':[{'sid':str(i)} for i in range(100)]},GhlError(429)]))
        with patch('app.services.sales.sync.state_for',AsyncMock(return_value=row)),patch('app.services.sales.sync.reconcile',AsyncMock()) as reconcile:
            with self.assertRaises(GhlError):await sync_resource(O(),client,'numbers')
            reconcile.assert_not_awaited();self.assertEqual(row.state,{})

class ProviderBackoff(IsolatedAsyncioTestCase):
    async def test_rate_limit_pauses_all_jobs_and_refunds_rejected_request(self):
        from unittest.mock import AsyncMock, MagicMock
        from app.models.sales import SalesSync
        from app.services.sales.analysis import analyze
        from app.services.sales.store import now,stamp
        usage=O(state={'day':now().date().isoformat(),'requests':2},last_success=None,error=None)
        async def get(model,key):return usage if model is SalesSync else None
        db=O(get=get,commit=AsyncMock())
        job=O(payload={'source_kind':'calls','id':'test'},attempts=0,error=None,next_run=now())
        client=MagicMock();client.__aenter__=AsyncMock(return_value=client);client.__aexit__=AsyncMock(return_value=False)
        client.post=AsyncMock(return_value=httpx.Response(429,headers={'retry-after':'45'},json={'error':{'code':'rate_limit'}}))
        with patch.object(settings,'SALES_GROQ_API_KEY','synthetic'),patch.object(settings,'SALES_AI_DAILY_LIMIT',150),patch('app.services.sales.analysis.sources_for',AsyncMock(return_value=([{'id':'call:test','text':'Available conversation text for a grounded analysis. '*3}],None))),patch('app.services.sales.analysis.httpx.AsyncClient',return_value=client):
            self.assertFalse(await analyze(db,job))
            self.assertEqual(usage.state['requests'],2)
            self.assertGreater(stamp(usage.state['blocked_until']),now())
            self.assertFalse(await analyze(db,job))
            client.post.assert_awaited_once()

class SalesDates(TestCase):
    def test_bundled_timezone_data_supports_browser_aliases_without_system_data(self):
        from datetime import date
        from zoneinfo import ZoneInfo, reset_tzpath, TZPATH
        from app.api.v1.sales import date_conditions
        original=TZPATH
        try:
            reset_tzpath([]);ZoneInfo.clear_cache()
            old=date_conditions(date(2026,11,16),None,'Europe/Kiev')
            canonical=date_conditions(date(2026,11,16),None,'Europe/Kyiv')
            self.assertEqual(old[0].right.value,canonical[0].right.value)
            self.assertTrue(date_conditions(date(2026,11,16),None,'America/New_York'))
        finally:
            reset_tzpath(original);ZoneInfo.clear_cache()

    def test_local_day_tracks_dst_and_rejects_invalid_filters(self):
        from datetime import date, timedelta
        from app.api.v1.sales import date_conditions
        bounds=date_conditions(date(2026,3,8),date(2026,3,8),'America/New_York')
        self.assertEqual(bounds[1].right.value-bounds[0].right.value,timedelta(hours=23))
        self.assertEqual(bounds[0].right.value.hour,5)
        for args in [(date(2026,1,2),date(2026,1,1),'UTC'),(None,None,'Not/AZone')]:
            with self.assertRaises(HTTPException) as e:date_conditions(*args)
            self.assertEqual(e.exception.status_code,422)

class TranscriptionFallback(IsolatedAsyncioTestCase):
    def test_segments_do_not_invent_speakers_or_timestamps(self):
        from app.services.sales.transcription import speech_segments
        rows=speech_segments({'segments':[{'text':' hello ','start':1.25},{'text':'No timestamp'}, {'text':'noise','no_speech_prob':.99,'avg_logprob':-2}]})
        self.assertEqual(rows,[{'text':'hello','startTime':1250},{'text':'No timestamp'}])

    async def test_missing_ghl_text_only_transcribes_new_or_opened_calls(self):
        from unittest.mock import AsyncMock
        from app.services.sales.transcription import read_ghl_transcript
        from app.services.sales.client import GhlError
        db=O(scalar=AsyncMock(return_value=None));client=O(get=AsyncMock(side_effect=GhlError(400)))
        for priority,expected in [(0,False),(5,True),(50,True)]:
            job=O(payload={'id':'call','contactId':'contact'},priority=priority)
            with patch('app.services.sales.transcription.get_record',AsyncMock(return_value=None)),patch('app.services.sales.transcription.save',AsyncMock()),patch('app.services.sales.transcription.enqueue',AsyncMock()) as enqueue:
                self.assertTrue(await read_ghl_transcript(db,client,job))
                self.assertEqual(bool(enqueue.await_count),expected)
                if expected:self.assertEqual(enqueue.call_args.args[1],'asr')

    async def test_missing_recording_never_calls_groq(self):
        from unittest.mock import AsyncMock,MagicMock
        from app.services.sales.transcription import transcribe_recording
        from app.services.sales.client import GhlError
        from app.services.sales.store import now
        usage=O(state={});db=O(get=AsyncMock(return_value=usage))
        job=O(payload={'id':'call'},priority=50)
        with patch.object(settings,'SALES_GROQ_API_KEY','synthetic'),patch('app.services.sales.transcription.get_record',AsyncMock(return_value=None)),patch('app.services.sales.transcription.save',AsyncMock()) as save,patch('app.services.sales.transcription.httpx.AsyncClient',MagicMock()) as groq:
            self.assertTrue(await transcribe_recording(db,O(get=AsyncMock(side_effect=GhlError(404))),job))
            groq.assert_not_called();self.assertEqual(save.call_args.args[2]['availability'],'not_recorded')

class ReviewBudget(IsolatedAsyncioTestCase):
    async def test_no_local_cap_and_large_input_retries_smaller_excerpt(self):
        from unittest.mock import AsyncMock,MagicMock
        from app.models.sales import SalesSync
        from app.services.sales.analysis import analyze
        from app.services.sales.store import now
        usage=O(state={'day':now().date().isoformat(),'requests':999},last_success=None,error=None)
        async def get(model,key):return usage if model is SalesSync else None
        db=O(get=get,commit=AsyncMock())
        job=O(payload={'source_kind':'calls','id':'test'},attempts=0,error=None,next_run=now())
        client=MagicMock();client.__aenter__=AsyncMock(return_value=client);client.__aexit__=AsyncMock(return_value=False)
        client.post=AsyncMock(return_value=httpx.Response(413))
        with patch.object(settings,'SALES_GROQ_API_KEY','synthetic'),patch.object(settings,'SALES_AI_DAILY_LIMIT',0),patch('app.services.sales.analysis.sources_for',AsyncMock(return_value=([{'id':'call:test','text':'Recorded words. '*100}],None))),patch('app.services.sales.analysis.httpx.AsyncClient',return_value=client):
            self.assertFalse(await analyze(db,job))
            client.post.assert_awaited_once();self.assertEqual(usage.state['requests'],999)
            self.assertEqual(job.payload['input_limit'],22500)

    async def test_opening_unchanged_review_uses_cache_before_provider_call(self):
        from unittest.mock import AsyncMock,MagicMock
        from app.services.sales.analysis import analyze,VERSION
        from app.services.sales.store import digest
        sources=[{'id':'call:test','text':'Recorded words. '*100}]
        fingerprint=digest({'version':VERSION,'model':settings.SALES_AI_MODEL,'sources':sources,'unreviewed_calls':False})
        db=O(get=AsyncMock(return_value=O(fingerprint=fingerprint)))
        with patch.object(settings,'SALES_GROQ_API_KEY','synthetic'),patch('app.services.sales.analysis.sources_for',AsyncMock(return_value=(sources,None))),patch('app.services.sales.analysis.httpx.AsyncClient',MagicMock()) as groq:
            self.assertTrue(await analyze(db,O(payload={'source_kind':'calls','id':'test','input_limit':3000})))
            groq.assert_not_called()

    async def test_archive_jobs_are_excluded_without_blocking_crm(self):
        from unittest.mock import AsyncMock,MagicMock
        from app.services.sales.sync import poll_jobs
        db=O(scalar=AsyncMock(return_value=None))
        context=MagicMock();context.__aenter__=AsyncMock(return_value=db);context.__aexit__=AsyncMock(return_value=False)
        with patch.object(settings,'SALES_AI_ARCHIVE_AUTOMATIC',False),patch('app.services.sales.sync.AsyncSessionLocal',return_value=context):
            await poll_jobs(O(),analysis_only=True)
            query=db.scalar.call_args.args[0].compile()
            self.assertIn(20,query.params.values())
            self.assertIn('analysis',query.params.values())
            await poll_jobs(O())
            query=db.scalar.call_args.args[0].compile()
            self.assertNotIn(20,query.params.values())
