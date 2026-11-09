"""Display translation tests; no real candidate or provider requests."""
import sys, json, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/backend'))
from app.services.hr_translation import protect, needs_translation, cache_key, translate_batch
from app.services.hr_ai import AIUnavailable


class HRTranslationTests(unittest.IsolatedAsyncioTestCase):
    def test_contacts_and_source_identity(self):
        original = 'Досвід_роботи: 5 років. https://example.com/my_cv mail@example.com @example_user +380671112233'
        masked, tokens = protect(original)
        for value in tokens.values():
            self.assertNotIn(value, masked)
        self.assertIn('[[KEEP_0]]', masked)
        self.assertIn('Досвід роботи', masked)
        self.assertTrue(needs_translation(original))
        self.assertFalse(needs_translation('English B2 — 5 years'))
        self.assertNotEqual(cache_key(original), cache_key(original + ' changed'))

    async def test_structure_and_placeholder_validation(self):
        source = ['Вітаю!\nСайт: https://wallpanels.com']
        raw = {'texts': ['Hello!\nWebsite: [[KEEP_0]]']}
        response = SimpleNamespace(is_success=True, json=lambda: {'choices': [{'message': {'content': json.dumps(raw)}}]})
        with patch('app.services.hr_translation.settings.GROQ_API_KEY', 'test-secret'), patch('httpx.AsyncClient.post', new=AsyncMock(return_value=response)) as provider:
            result = await translate_batch(source)
            self.assertEqual(result, ['Hello!\nWebsite: https://wallpanels.com'])
            payload = json.dumps(provider.call_args.kwargs['json']['messages'][1])
            self.assertNotIn('https://wallpanels.com', payload)
            raw['texts'] = ['Hello, no website']
            with self.assertRaises(AIUnavailable):
                await translate_batch(source)
            raw['texts'] = []
            with self.assertRaises(AIUnavailable):
                await translate_batch(source)

    async def test_safe_provider_failure(self):
        with patch('app.services.hr_translation.settings.GROQ_API_KEY', 'test-secret'), patch('httpx.AsyncClient.post', new=AsyncMock(return_value=SimpleNamespace(is_success=False, status_code=401))):
            with self.assertRaises(AIUnavailable) as error:
                await translate_batch(['Вітаю!'])
            self.assertNotIn('test-secret', error.exception.message)
