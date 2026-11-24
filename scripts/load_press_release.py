"""Load one directly inspected official fact; evidence is an excerpt, not raw HTTP."""
import hashlib
import json
from pathlib import Path
from app.etl.importer import import_file


def load_press_release(session):
    root = Path('data/official')
    meta = json.loads((root / 'rosstat-births-2024-provenance.json').read_text(encoding='utf-8'))
    evidence = (root / meta['evidence_file']).read_bytes().replace(b'\r\n', b'\n')
    normalized = root / meta['normalized_file']
    payload = normalized.read_bytes().replace(b'\r\n', b'\n')
    if hashlib.sha256(evidence).hexdigest() != meta['evidence_sha256'] or hashlib.sha256(payload).hexdigest() != meta['normalized_sha256']:
        raise ValueError('Official press-release evidence checksum mismatch')
    if 'По оперативным данным в 2024 году родилось 1 миллион 222 тыс. 408 младенцев.' not in evidence.decode('utf-8'):
        raise ValueError('Official inspected publication excerpt changed')
    rows = json.loads(payload)
    if len(rows) != 1 or rows[0] != dict(indicator_code='births', region='RU',
        period_start='2024-01-01', period_end='2024-12-31', value='1222408', unit='человек',
        published_at=None, data_status='provisional'):
        raise ValueError('Official press-release fact coverage mismatch')
    batch = import_file(session, normalized, meta['source_url'], meta['source_name'], meta['publisher'],
                        parser_version='rosstat-inspected-press-release/1.0.0')
    # The browser DOM excerpt is not the original response bytes.
    batch.original_checksum = None
    if batch.errors or batch.status == 'failed':
        raise ValueError('Official press-release import failed; transaction must roll back')
    return batch
