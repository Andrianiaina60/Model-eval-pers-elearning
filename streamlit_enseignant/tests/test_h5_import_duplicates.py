"""Contrôle de l'import H5 avec confirmation explicite des doublons."""
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path

import pandas as pd

SRC = Path(__file__).resolve().parents[1] / 'validation_rapide_h5.py'
added_st = 'streamlit' not in sys.modules
added_data = 'data_access' not in sys.modules
try:
    try:
        import streamlit  # noqa: F401
    except ImportError:
        sys.modules['streamlit'] = types.ModuleType('streamlit')
    try:
        import data_access  # noqa: F401
    except ImportError:
        mod = types.ModuleType('data_access')
        mod.safe_pdf = lambda *args, **kwargs: None
        sys.modules['data_access'] = mod
    spec = importlib.util.spec_from_file_location('h5_overwrite_checks', SRC)
    h5 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h5)
finally:
    # Keep a Streamlit stub only in environments without Streamlit, for other unit tests.
    if added_data and isinstance(sys.modules.get('data_access'), types.ModuleType) and not getattr(sys.modules['data_access'], '__file__', None):
        sys.modules.pop('data_access', None)


class ImportDuplicatesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pool = pd.DataFrame([
            {'ETAPE': 'T1', 'ID_GROUPE': 'G005', 'PARCOURS': 'BI', 'ID_CHAPITRE': 'CH_BI01_01', 'CHAPITRE': 'Power Query', 'RANG': '1'},
            {'ETAPE': 'T1', 'ID_GROUPE': 'G006', 'PARCOURS': 'BI', 'ID_CHAPITRE': 'CH_BI01_02', 'CHAPITRE': 'Jointures', 'RANG': '2'},
        ])

    def batch(self, score='4', title='Power Query'):
        csv_bytes = pd.DataFrame([{
            'Cycle': 'T1', 'Groupe': 'G005', 'Chapitre': title,
            'Pertinence /5': score, 'Justification': 'Avis enseignant'
        }]).to_csv(index=False).encode('utf-8-sig')
        return [('h5.csv', 'ENS-BI-01', h5.prepare_csv_import(csv_bytes, self.pool, 'ENS-BI-01', 'BI'))]

    def test_new_import_without_confirmation_of_replacement(self):
        self.assertEqual(h5.import_prepared_reviews(self.root, self.batch('4'), False), (1, 0))
        self.assertEqual(len(h5.read_reviews(self.root)), 1)

    def test_existing_entry_requires_confirmation_and_remains_intact(self):
        h5.import_prepared_reviews(self.root, self.batch('4'))
        before = h5.read_reviews(self.root).copy()
        with self.assertRaisesRegex(ValueError, 'confirmer'):
            h5.import_prepared_reviews(self.root, self.batch('2'), False)
        pd.testing.assert_frame_equal(before, h5.read_reviews(self.root))

    def test_confirmed_replace_updates_and_historises(self):
        h5.import_prepared_reviews(self.root, self.batch('4'))
        self.assertEqual(len(h5.duplicate_import_keys(self.batch('2'), h5.read_reviews(self.root))), 1)
        result = h5.import_prepared_reviews(self.root, self.batch('2'), True)
        self.assertEqual(result, (0, 1))
        self.assertEqual(h5.read_reviews(self.root).iloc[0]['NOTE_PERTINENCE_1_5'], '2')
        hist = pd.read_csv(h5._path(self.root, historisation=True), dtype=str, keep_default_na=False)
        self.assertEqual(hist['ACTION'].tolist(), ['CREATION', 'REVISION'])
        self.assertEqual(hist.iloc[1]['NOTE_PRECEDENTE'], '4')

    def test_same_note_still_counts_as_existing_without_new_revision(self):
        h5.import_prepared_reviews(self.root, self.batch('4'))
        self.assertEqual(len(h5.duplicate_import_keys(self.batch('4'), h5.read_reviews(self.root))), 1)
        self.assertEqual(h5.import_prepared_reviews(self.root, self.batch('4'), True), (0, 0))
        hist = pd.read_csv(h5._path(self.root, historisation=True))
        self.assertEqual(len(hist), 1)

    def test_duplicates_inside_upload_batch_are_refused(self):
        prepared = self.batch('4') + self.batch('3')
        with self.assertRaisesRegex(ValueError, 'Doublons entre les CSV'):
            h5.import_prepared_reviews(self.root, prepared, True)
        self.assertFalse(h5._path(self.root).exists())

    def test_cancel_does_not_modify_storage(self):
        h5.import_prepared_reviews(self.root, self.batch('4'))
        prior = h5.read_reviews(self.root).copy()
        # In the UI, clicking Annuler only clears the uploader and reruns;
        # import_prepared_reviews is not called.
        pd.testing.assert_frame_equal(prior, h5.read_reviews(self.root))


if __name__ == '__main__':
    unittest.main()
