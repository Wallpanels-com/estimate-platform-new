"""Clipboard PNGs use the ordinary persistent zone-photo upload endpoint."""
import io
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch
import sys
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'apps/backend'), str(Path(__file__).parent)]
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.datastructures import Headers, UploadFile
from app.core.database import Base
from app.core.config import settings
from app.models.estimate import Estimate, EstimateZone, EstimateImage
from app.api.v1 import files
from test_estimate_branches import AsyncSessionAdapter


class PhotoPersistence(IsolatedAsyncioTestCase):
    async def test_clipboard_png_survives_new_database_session_for_pre_and_final(self):
        engine = create_engine('sqlite://')
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        image = io.BytesIO()
        Image.new('RGB', (32, 24), '#b39b7b').save(image, 'PNG')
        content = image.getvalue()
        with tempfile.TemporaryDirectory() as directory, patch.object(settings, 'STORAGE_PATH', directory):
            for mode in ('pre', 'final'):
                eid, zid = uuid.uuid4(), uuid.uuid4()
                with Session(engine) as session:
                    estimate = Estimate(id=eid, user_id=uuid.uuid4(), type=mode, subtotal=0, final_total=0)
                    session.add_all([estimate, EstimateZone(id=zid, estimate_id=eid, label='Photo test')])
                    session.commit()
                    upload = UploadFile(io.BytesIO(content), filename='image.png', headers=Headers({'content-type': 'image/png'}))
                    with patch.object(files, 'load_estimate', AsyncMock(return_value=estimate)):
                        await files.upload_image(eid, zid, 1, upload, AsyncSessionAdapter(session), SimpleNamespace(name='Employee'))
                # A fresh connection to persisted rows represents reload/reopening.
                with Session(engine) as reopened:
                    record = reopened.scalars(select(EstimateImage).where(EstimateImage.zone_id == zid)).one()
                    self.assertEqual(record.slot, 1)
                    self.assertEqual(record.original_name, 'image.png')
                    self.assertEqual(Path(record.file_path).read_bytes(), content)
                    self.assertEqual(reopened.get(Estimate, eid).updated_by_name, 'Employee')
