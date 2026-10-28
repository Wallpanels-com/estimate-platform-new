"""Regression checks for the audit: no pricing changes, bounded queries, responsive exports."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace as Object
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'apps/backend'))
os.environ.setdefault('DATABASE_URL','postgresql://unused:unused@localhost/unused')
os.environ.setdefault('SECRET_KEY','unit-tests-only')
from app.api.v1 import estimates, pdf
from app.services import pricebook_service as book
from app.services.pricing_config import DEFAULT_PRICING_CONFIG
from app.services.managed_rates import with_managed_rates

class AuditRegressions(IsolatedAsyncioTestCase):
    async def test_first_rate_save_matches_the_effective_get_revision(self):
        current=deepcopy(DEFAULT_PRICING_CONFIG)
        effective=with_managed_rates(current)
        row=Object(config=effective,updated_by_name='Employee',updated_at=datetime.now(timezone.utc))
        with patch.object(book,'lock_config',new=AsyncMock()), patch.object(book,'get_pricing_config',new=AsyncMock(return_value=current)), patch.object(book,'save_pricing_config',new=AsyncMock(return_value=row)) as save:
            result=await book.save_legacy(Object(),effective,'Employee',book.revision(effective))
            self.assertEqual(result['config'],effective)
            self.assertEqual(save.await_args.args[1],effective)
            changed=deepcopy(current);changed['wall']['base_rates']['large']+=1
            with patch.object(book,'get_pricing_config',new=AsyncMock(return_value=changed)):
                with self.assertRaises(Exception) as error:
                    await book.save_legacy(Object(),effective,'Employee',book.revision(effective))
                self.assertEqual(error.exception.status_code,409)

    async def test_register_is_bounded_and_preserves_selected_branches(self):
        now=datetime.now(timezone.utc)
        roots=[Object(id=uuid4(),branch_state={'active_mode':'final'}) for _ in range(100)]
        finals=[Object(id=uuid4(),source_estimate_id=r.id,type='final',status='draft',title=str(i),room_name=None,client_name=None,final_total=Decimal('125.50'),created_by_name='Original',updated_by_name='Editor',created_at=now,updated_at=now,deleted_at=None) for i,r in enumerate(roots)]
        result=lambda rows:Object(scalars=lambda:Object(all=lambda:rows))
        for trash in (False,True):
            db=Object(execute=AsyncMock(side_effect=[result(roots),result(finals)]))
            items=await estimates.estimate_register(db,trash=trash)
            self.assertEqual(db.execute.await_count,2)
            self.assertEqual([i.id for i in items],[f.id for f in finals])
            self.assertTrue(all(i.created_by=='Original' and i.updated_by=='Editor' for i in items))

    async def test_xlsx_does_not_block_other_async_requests_and_cleans_up(self):
        est=Object(client_name='Client',title='Local',source_estimate_id=None)
        db=Object(execute=AsyncMock(return_value=Object(scalar_one_or_none=lambda:est)))
        def render(source,destination):
            time.sleep(.1)
            Path(destination).write_bytes(b'xlsx-test')
        with tempfile.TemporaryDirectory() as directory, patch.object(pdf.settings,'STORAGE_PATH',directory), patch.object(pdf,'generate_passport',side_effect=render):
            task=asyncio.create_task(pdf.passport(uuid4(),db,Object()))
            start=time.perf_counter()
            await asyncio.sleep(.02)
            self.assertLess(time.perf_counter()-start,.08)
            response=await task
            self.assertTrue(Path(response.path).is_file())
            await response.background()
            self.assertFalse(Path(response.path).exists())
