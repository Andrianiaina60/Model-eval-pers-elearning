"""Répare uniquement l'import de data_access dans test_preflight.py (non destructif)."""
from pathlib import Path
p = Path(__file__).resolve().parent.parent  # not intended inside zip root? use cwd below
p = Path.cwd() / 'streamlit_enseignant' / 'tests' / 'test_preflight.py'
if not p.is_file():
    raise SystemExit(f'Introuvable : {p}')
s = p.read_text(encoding='utf-8')
marker = '# FIX: accès aux modules streamlit_enseignant depuis tests/\n'
if marker in s:
    print('test_preflight.py déjà corrigé')
else:
    prefix = ('from pathlib import Path as _PathForImport\n'
              'import sys as _sysForImport\n'
              + marker
              + '_app_dir = str(_PathForImport(__file__).resolve().parents[1])\n'
              + 'if _app_dir not in _sysForImport.path:\n'
              + '    _sysForImport.path.insert(0, _app_dir)\n\n')
    # Insert after future import if present.
    lines = s.splitlines(keepends=True)
    future_lines = [i for i,l in enumerate(lines) if l.strip().startswith('from __future__ import ')]
    index = max(future_lines) + 1 if future_lines else 0
    lines.insert(index, prefix)
    p.with_suffix('.py.bak_before_fix').write_text(s, encoding='utf-8')
    p.write_text(''.join(lines), encoding='utf-8')
    print('test_preflight.py corrigé. Sauvegarde :', p.with_suffix('.py.bak_before_fix'))
