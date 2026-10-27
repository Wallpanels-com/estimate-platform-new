"""Apply the owner's download-only PDF policy without touching estimate data.

Existing private backups are rewritten and verified in place: their native DB
dump, photographs, audio and XLSX files are preserved. Generated PDFs and release
assets already held in Git are excluded. Historical document metadata is retained.
"""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile
import tempfile
import psycopg2
from . import backups
from app.core.config import settings


def keep_member(name):
    path = PurePosixPath(name)
    return not path.is_absolute() and '..' not in path.parts and path.suffix.lower() != '.pdf' and not name.startswith('release/')


def rewrite_archive(source, target):
    with tarfile.open(source, 'r:gz') as archive:
        original = json.load(archive.extractfile('manifest.json'))
    manifest = {**original, 'files': {}, 'pdf_presentations_excluded': True, 'release_assets_in_git': True}
    # Streaming avoids loading large presentations or seeking the gzip repeatedly.
    with tarfile.open(source, 'r|gz') as incoming, tarfile.open(target, 'w:gz') as outgoing:
        for member in incoming:
            if member.name == 'manifest.json' or not keep_member(member.name):
                continue
            if not member.isfile():
                continue
            stream = incoming.extractfile(member)
            data = stream.read()
            digest = hashlib.sha256(data).hexdigest()
            if original['files'].get(member.name) != digest:
                raise RuntimeError('Backup input checksum mismatch; original was not changed.')
            outgoing.addfile(member, io.BytesIO(data))
            manifest['files'][member.name] = digest
        contents = json.dumps(manifest, indent=2).encode()
        info = tarfile.TarInfo('manifest.json'); info.size = len(contents)
        outgoing.addfile(info, io.BytesIO(contents))
    with tarfile.open(target) as checked:
        if any(not keep_member(m.name) for m in checked):
            raise RuntimeError('PDF exclusion check failed.')
        for name, digest in manifest['files'].items():
            if hashlib.sha256(checked.extractfile(name).read()).hexdigest() != digest:
                raise RuntimeError('Rewritten backup checksum mismatch.')
    return manifest


def purge_generated_files(storage):
    root = Path(storage).resolve()
    count = size = 0
    for directory in (root/'issued', root/'pdfs'):
        if not directory.exists():
            continue
        for path in directory.rglob('*'):
            if path.is_file() and not path.is_symlink() and path.suffix.lower() == '.pdf' and path.resolve().is_relative_to(root):
                size += path.stat().st_size
                path.unlink(); count += 1
    return {'pdf_files_removed': count, 'bytes_freed': size}


def apply_policy():
    connection = psycopg2.connect(**backups.connection_options()); connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_try_advisory_lock(%s)', (backups.LOCK,))
            if not cursor.fetchone()[0]:
                raise RuntimeError('A backup is running; retry after it completes.')
        s3 = backups.client()
        index = backups.status()
        by_key = {row['key']: row for row in index.get('backups', [])}
        changed = []
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=settings.BACKUP_BUCKET, Prefix=backups.PREFIX):
            for obj in page.get('Contents', []):
                key = obj['Key']
                if not key.endswith('.tar.gz'):
                    continue
                head = s3.head_object(Bucket=settings.BACKUP_BUCKET, Key=key)
                if head.get('Metadata', {}).get('pdf-presentations-excluded') == 'true':
                    continue
                with tempfile.TemporaryDirectory(prefix='wallpanels-pdf-policy-') as directory:
                    source = Path(directory)/'original.tar.gz'; target = Path(directory)/'without-pdfs.tar.gz'
                    s3.download_file(settings.BACKUP_BUCKET, key, str(source))
                    expected = head.get('Metadata', {}).get('sha256')
                    if not expected or backups.checksum(source) != expected:
                        raise RuntimeError('Remote backup integrity check failed; no overwrite was attempted.')
                    manifest = rewrite_archive(source, target)
                    digest = backups.checksum(target)
                    metadata = {**head.get('Metadata', {}), 'sha256': digest, 'pdf-presentations-excluded': 'true'}
                    with target.open('rb') as stream:
                        s3.put_object(Bucket=settings.BACKUP_BUCKET, Key=key, Body=stream, Metadata=metadata)
                    verified = Path(directory)/'verified.tar.gz'
                    s3.download_file(settings.BACKUP_BUCKET, key, str(verified))
                    if backups.checksum(verified) != digest:
                        raise RuntimeError('Rewritten remote backup verification failed.')
                    row = {**by_key.get(key, {}), 'key': key, 'id': head.get('Metadata',{}).get('backup-id', Path(key).stem.split('.')[0]),
                           'created_at': manifest['created_at'], 'sha256': digest, 'bytes': target.stat().st_size,
                           'files': len(manifest['files']), 'tables': manifest['tables'],
                           'pdf_presentations_excluded': True, 'download_verified': True}
                    by_key[key] = row
                    changed.append({'key': key, 'before_bytes': head['ContentLength'], 'after_bytes': target.stat().st_size})
                    index['backups'] = sorted(by_key.values(), key=lambda r:r['created_at'], reverse=True)
                    index['last_error'] = None
                    backups.save_status(index)
        result = {**purge_generated_files(settings.STORAGE_PATH), 'rewritten_backups': changed,
                  'completed_at': datetime.now(timezone.utc).isoformat(), 'pdf_presentations_excluded': True}
        report = Path(settings.STORAGE_PATH)/'operations/pdf-policy.json'
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, indent=2)); report.chmod(0o600)
        return result
    finally:
        connection.close()
