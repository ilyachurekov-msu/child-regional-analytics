import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import pytest
from sqlalchemy import select
from app.models.entities import Source
from scripts import update_data


def test_error_rolls_back_working_database(session, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    Path('data').mkdir()
    spec = dict(id='test', url='https://example.gov.ru/fixture', name='Synthetic fixture', publisher='Synthetic',
                format='html', adapter='kemerovo-yearbook-html/1.1.0', enabled=True, years=[2020], region_id='RU-42')
    Path('data/source-manifest.json').write_text(json.dumps({'sources': [spec]}))
    original = Path('original.html')
    original.write_text('<html>synthetic</html>')
    rows = [dict(region='RU-42', indicator_code='births', period_start='2020-01-01', period_end='2020-12-31', value='1', unit='человек')]
    monkeypatch.setattr(update_data, 'kemerovo_html', lambda *a: rows)
    monkeypatch.setattr(update_data, 'engine', lambda: session.bind)

    def failing_import(db, *a, **kw):
        db.add(Source(source_id=uuid4(), source_type='official_statistics', normalized_identifier='ROLLBACK', name='ROLLBACK', url=spec['url'], publisher='Synthetic'))
        db.flush()
        return SimpleNamespace(batch_id=uuid4(), errors=1, status='failed')

    monkeypatch.setattr(update_data, 'import_file', failing_import)
    monkeypatch.setattr('sys.argv', ['update_data', '--source', 'test', '--file', str(original)])
    with pytest.raises(SystemExit):
        update_data.main()
    assert session.scalar(select(Source).where(Source.name == 'ROLLBACK')) is None
    assert json.loads(Path('data/archive/latest-update-report.json').read_text())['status'] == 'failed'


def test_dry_run_does_not_open_database(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    Path('data').mkdir()
    spec = dict(id='test', url='https://example.gov.ru/fixture', name='Synthetic', publisher='Synthetic', format='html',
                adapter='kemerovo-yearbook-html/1.1.0', enabled=True, years=[2020], region_id='RU-42')
    Path('data/source-manifest.json').write_text(json.dumps({'sources': [spec]}))
    Path('original.html').write_text('Synthetic')
    monkeypatch.setattr(update_data, 'kemerovo_html', lambda *a: [dict(region='RU-42', indicator_code='births', period_start='2020-01-01', period_end='2020-12-31', value='1', unit='человек')])
    monkeypatch.setattr(update_data, 'engine', lambda: pytest.fail('dry-run must not access database'))
    monkeypatch.setattr('sys.argv', ['update_data', '--source', 'test', '--file', 'original.html', '--dry-run'])
    update_data.main()
    assert json.loads(Path('data/archive/latest-update-report.json').read_text())['status'] == 'validated'
