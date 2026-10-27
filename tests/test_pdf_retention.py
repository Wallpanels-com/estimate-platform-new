import hashlib, io, json, os, sys, tarfile, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'apps/backend'))
os.environ.setdefault('DATABASE_URL','postgresql://unused:unused@localhost/unused')
os.environ.setdefault('SECRET_KEY','unit-tests-only')
from app.services.pdf_retention import rewrite_archive, purge_generated_files


class PDFRetention(unittest.TestCase):
    def test_old_backup_is_rewritten_without_pdfs_preserving_data(self):
        entries={'database.dump':b'database snapshot','storage/images/zone/photo.webp':b'photo',
                 'storage/issued/estimate/export.xlsx':b'xlsx', 'storage/issued/estimate/pre.pdf':b'heavy pre',
                 'storage/pdfs/final.PDF':b'heavy final','release/assets/company-slides.pdf':b'company',
                 'release/assets/background.png':b'release kept in Git'}
        manifest={'created_at':'2026-10-27T12:00:00+00:00','tables':{'users':7},'files':{name:hashlib.sha256(data).hexdigest() for name,data in entries.items()}}
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'old.tar.gz';target=Path(d)/'new.tar.gz'
            with tarfile.open(source,'w:gz') as archive:
                for name,data in {**entries,'manifest.json':json.dumps(manifest).encode()}.items():
                    info=tarfile.TarInfo(name);info.size=len(data);archive.addfile(info,io.BytesIO(data))
            rewritten=rewrite_archive(source,target)
            with tarfile.open(target) as archive:
                self.assertEqual(set(archive.getnames()),{'database.dump','storage/images/zone/photo.webp','storage/issued/estimate/export.xlsx','manifest.json'})
                for name in rewritten['files']:
                    self.assertEqual(archive.extractfile(name).read(),entries[name])
            self.assertTrue(rewritten['pdf_presentations_excluded'])
            self.assertEqual(rewritten['tables'],manifest['tables'])

    def test_cleanup_deletes_only_generated_pdf_files(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for name in ['issued/estimate/pre.pdf','pdfs/final.PDF','images/photo.webp','issued/estimate/export.xlsx','templates/company.pdf']:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'example')
            result=purge_generated_files(root)
            self.assertEqual(result['pdf_files_removed'],2)
            self.assertEqual(result['bytes_freed'],14)
            for name in ['images/photo.webp','issued/estimate/export.xlsx','templates/company.pdf']:
                self.assertTrue((root/name).is_file())
