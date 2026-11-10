"""Exercise the production SPA handler without application/database startup."""
import ast
from pathlib import Path
import tempfile
import unittest
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.testclient import TestClient


class FrontendEntryCacheTests(unittest.TestCase):
    def test_routes_and_direct_html_revalidate_without_disabling_asset_cache(self):
        source = Path('apps/backend/app/main.py').read_text()
        handler = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.AsyncFunctionDef) and n.name == 'frontend')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / 'index.html').write_text('<html>current build</html>')
            (root / 'logo.svg').write_text('<svg/>')
            app = FastAPI()
            namespace = dict(app=app, frontend_dist=root, FileResponse=FileResponse, HTTPException=HTTPException)
            exec(compile(ast.Module(body=[handler], type_ignores=[]), '<spa-handler>', 'exec'), namespace)
            with TestClient(app) as client:
                for path in ['/', '/hr/staff', '/portal-embed?module=hr', '/index.html']:
                    response = client.get(path)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.headers['cache-control'], 'no-cache')
                self.assertNotIn('cache-control', client.get('/logo.svg').headers)
                self.assertEqual(client.get('/api/not-found').status_code, 404)


if __name__ == '__main__':
    unittest.main()
