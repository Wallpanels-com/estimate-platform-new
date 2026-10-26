"""Preview/download routing without network requests, real exports or DB writes."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as Object
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/backend"))
from app.api.v1 import pdf
from fastapi import HTTPException


class PdfDelivery(IsolatedAsyncioTestCase):
    async def test_missing_photo_blocks_both_preview_and_download(self):
        from app.services.final_zone_photos import PHOTO_REQUIRED

        est = Object(type="final", client_name="Client", title="Example")
        db = Object(
            execute=AsyncMock(return_value=Object(scalar_one_or_none=lambda: est))
        )
        for attachment in (False, True):
            with patch.object(
                pdf,
                "generate_final_estimate",
                side_effect=pdf.FinalEstimatePdfError(PHOTO_REQUIRED),
            ):
                with self.assertRaises(HTTPException) as error:
                    await pdf.final_estimate(uuid.uuid4(), attachment, db, Object())
                self.assertEqual(error.exception.status_code, 422)
                self.assertEqual(error.exception.detail, PHOTO_REQUIRED)

    async def test_corporate_asset_error_blocks_preview_and_download(self):
        est = Object(type="final", client_name="Client", title="Example")
        db = Object(
            execute=AsyncMock(return_value=Object(scalar_one_or_none=lambda: est))
        )
        message = "The corporate slides PDF is damaged or invalid. Final Estimate was not generated."
        for attachment in (False, True):
            with patch.object(
                pdf,
                "generate_final_estimate",
                side_effect=pdf.FinalEstimatePdfError(message),
            ):
                with self.assertRaises(HTTPException) as error:
                    await pdf.final_estimate(uuid.uuid4(), attachment, db, Object())
                self.assertEqual(error.exception.status_code, 503)
                self.assertEqual(error.exception.detail, message)

    async def test_legacy_final_download_uses_the_same_final_assembly(self):
        ident, user = uuid.uuid4(), Object()
        db = Object(
            execute=AsyncMock(
                return_value=Object(scalar_one_or_none=lambda: Object(type="final"))
            )
        )
        with patch.object(
            pdf, "final_estimate", new=AsyncMock(return_value="combined")
        ) as endpoint:
            self.assertEqual(await pdf.download(ident, db, user), "combined")
            endpoint.assert_awaited_once_with(ident, True, db, user)

    async def test_pre_and_final_use_correct_renderers_and_read_only_models(self):
        est = Object(
            type="pre",
            title="Local example",
            client_name="Client",
            zones=[],
            line_items=[],
        )
        before = deepcopy(est)
        db = Object(
            execute=AsyncMock(return_value=Object(scalar_one_or_none=lambda: est))
        )
        for mode, endpoint in (
            ("pre", pdf.pre_estimate),
            ("final", pdf.final_estimate),
        ):
            for attachment in (False, True):

                def pre_renderer(source, destination):
                    self.assertIs(source, est)
                    Path(destination).write_bytes(b"%PDF-unit-test-pre")
                    return str(destination)

                def final_renderer(source, directory):
                    self.assertEqual(source.type, "final")
                    self.assertEqual(source.client_name, est.client_name)
                    self.assertIs(source.zones, est.zones)
                    target = Path(directory) / "unit-test-final.pdf"
                    target.write_bytes(b"%PDF-unit-test-final")
                    return str(target)

                with patch.object(
                    pdf, "generate_pre_estimate", side_effect=pre_renderer
                ) as pre, patch.object(
                    pdf, "generate_final_estimate", side_effect=final_renderer
                ) as final:
                    response = await endpoint(uuid.uuid4(), attachment, db, Object())
                    self.assertEqual(response.media_type, "application/pdf")
                    self.assertEqual(response.headers["cache-control"], "no-store")
                    self.assertTrue(
                        response.headers["content-disposition"].startswith(
                            "attachment" if attachment else "inline"
                        )
                    )
                    data = Path(response.path).read_bytes()
                    self.assertEqual(data, f"%PDF-unit-test-{mode}".encode())
                    self.assertEqual(pre.call_count, mode == "pre")
                    self.assertEqual(final.call_count, mode == "final")
                    self.assertEqual(est, before)
                    await response.background()
                    self.assertFalse(
                        Path(response.path).exists(),
                        "Temporary exports must be cleaned up",
                    )

    async def test_missing_estimate_returns_404_without_generating(self):
        db = Object(
            execute=AsyncMock(return_value=Object(scalar_one_or_none=lambda: None))
        )
        for endpoint in (pdf.pre_estimate, pdf.final_estimate):
            with patch.object(pdf, "generate_pre_estimate") as pre, patch.object(
                pdf, "generate_final_estimate"
            ) as final:
                with self.assertRaises(HTTPException) as error:
                    await endpoint(uuid.uuid4(), False, db, Object())
                self.assertEqual(error.exception.status_code, 404)
                pre.assert_not_called()
                final.assert_not_called()

    async def test_failed_final_render_cleans_temp_files(self):
        est = Object(type="pre", client_name="Client", title="Example")
        db = Object(
            execute=AsyncMock(return_value=Object(scalar_one_or_none=lambda: est))
        )
        original = tempfile.TemporaryDirectory
        folders = []

        def track(*args, **kwargs):
            result = original(*args, **kwargs)
            folders.append(Path(result.name))
            return result

        with patch.object(
            pdf.tempfile, "TemporaryDirectory", side_effect=track
        ), patch.object(
            pdf,
            "generate_final_estimate",
            side_effect=RuntimeError("Renderer unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Renderer unavailable"):
                await pdf.final_estimate(uuid.uuid4(), False, db, Object())
        self.assertTrue(folders)
        self.assertTrue(all(not folder.exists() for folder in folders))
        self.assertEqual(est.type, "pre")

    async def test_legacy_pre_download_uses_the_current_pre_renderer(self):
        ident, user = uuid.uuid4(), Object()
        db = Object(
            execute=AsyncMock(
                return_value=Object(scalar_one_or_none=lambda: Object(type="pre"))
            )
        )
        with patch.object(
            pdf, "pre_estimate", new=AsyncMock(return_value="current-pre")
        ) as endpoint:
            self.assertEqual(await pdf.download(ident, db, user), "current-pre")
            endpoint.assert_awaited_once_with(ident, True, db, user)

    async def test_legacy_pre_generation_cannot_call_old_generic_renderer(self):
        ident = uuid.uuid4()
        est = Object(type="pre", source_estimate_id=None)
        db = Object(
            execute=AsyncMock(return_value=Object(scalar_one_or_none=lambda: est)),
            add=lambda obj: None,
            flush=AsyncMock(),
            commit=AsyncMock(),
        )
        with patch.object(
            pdf, "generate_pre_estimate", return_value="current-pre.pdf"
        ) as renderer, patch.object(pdf, "generate_pdf") as old:
            result = await pdf.generate(ident, db, Object())
            self.assertEqual(result["status"], "ready")
            self.assertEqual(renderer.call_args.args[0], est)
            old.assert_not_called()
