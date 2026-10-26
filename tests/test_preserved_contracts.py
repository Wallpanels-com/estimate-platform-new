from pathlib import Path
import hashlib,json,os,sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'apps/backend'))
os.environ.setdefault('DATABASE_URL','postgresql+asyncpg://unused:unused@127.0.0.1:55432/unused')
os.environ.setdefault('SECRET_KEY','unit-tests-only')
os.environ.setdefault('OPENAI_API_KEY','')
from app.services.rule_engine import calc_wall,calc_cabinet,calc_mirror

class PreservedContracts(unittest.TestCase):
    def test_original_export_and_price_sources_are_preserved(self):
        manifest=json.loads((ROOT/'docs/reference-checksums.json').read_text())
        files=['app/services/pdf_service.py','app/services/rule_engine.py','app/services/pricing_config.py','app/templates/project_passport_template.xlsx','app/templates/pre_estimate.html','app/templates/final_estimate.html']
        for path in files:
            with self.subTest(path=path):self.assertEqual(hashlib.sha256((ROOT/'apps/backend'/path).read_bytes()).hexdigest(),manifest['Estimates_platform_backend-main/'+path])
    def test_estimate_model_only_adds_final_branch_fields(self):
        source=(ROOT/'apps/backend/app/models/estimate.py').read_text()
        # Revision is a derived concurrency token, not a mapped column.
        start=source.index('    @property\n    def revision(')
        end=source.index('    id:', start)
        source=source[:start]+source[end:]
        original='\n'.join(line for line in source.split('\n') if not any(line.startswith('    '+field+':') for field in ('source_estimate_id','branch_state','cover_image_id')))
        manifest=json.loads((ROOT/'docs/reference-checksums.json').read_text())
        self.assertEqual(hashlib.sha256(original.encode()).hexdigest(),manifest['Estimates_platform_backend-main/app/models/estimate.py'])
    def test_wall_size_boundaries(self):
        for sf,rate in [(99,60),(100,55),(249,55),(250,50)]:
            with self.subTest(sf=sf):self.assertEqual(calc_wall(sf)['total'],sf*rate)
    def test_wall_features_and_coverage(self):
        result=calc_wall(120,['led'],[{'key':'hidden_door','qty':2}],panel_coverage_pct=50)
        self.assertEqual(result['total'],8600)
        self.assertEqual(len(result['line_items']),2)
    def test_cabinet_type_and_addons(self):
        self.assertEqual(calc_cabinet(8,False,'tv_stand',['led_lighting'])['total'],5600)
    def test_mirror_installation_is_additive(self):
        self.assertEqual(calc_mirror(20)['total'],2600)

if __name__=='__main__':unittest.main()
