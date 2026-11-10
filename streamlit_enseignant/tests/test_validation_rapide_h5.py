from __future__ import annotations
import sys, types, unittest, tempfile
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import streamlit
except ImportError:
    sys.modules.setdefault('streamlit', types.ModuleType('streamlit'))
from validation_rapide_h5 import pool_from_exports, read_reviews, save_reviews, _path, _valider_note_principale


def sample(phase='T1', gid='T1_BI_Debutant', ch='CH1'):
    return {'ETAPE':phase,'ID_GROUPE':gid,'PARCOURS':'BI',
            'ID_CHAPITRE':ch,'CHAPITRE':'Introduction Power BI',
            'RANG':'1','STATUT':'CANDIDAT_HYBRIDE_NON_VALIDE',
            'NOTE_PERTINENCE_1_5':'4','NOTE_NIVEAU_1_5':'5',
            'NOTE_LACUNE_1_5':'4','PREREQUIS':'NON_VERIFIES','COMMENTAIRE':'Évaluation réelle'}

class FastReviewTests(unittest.TestCase):
    def test_pool_is_separated_and_non_destructive(self):
        t0=pd.DataFrame([sample('T0','T0_BI_Debutant','CH1')])
        t1=pd.DataFrame([sample('T1','T1_BI_Debutant','CH2')])
        baseline=t0.copy(deep=True)
        pool=pool_from_exports(t0,t1)
        self.assertEqual(len(pool),2)
        self.assertEqual(set(pool.ETAPE),{'T0','T1'})
        self.assertTrue(t0.equals(baseline))
    def test_two_chapters_preserved_and_revisions_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            a=sample(ch='CH1'); b=sample(ch='CH2')
            self.assertEqual(save_reviews(root,'ENS-BI-01',[a,b]),(2,0))
            self.assertEqual(len(read_reviews(root)),2)
            self.assertEqual(save_reviews(root,'ENS-BI-01',[a,b]),(0,0))
            c=sample(ch='CH1'); c['NOTE_PERTINENCE_1_5']='3'
            self.assertEqual(save_reviews(root,'ENS-BI-01',[c]),(0,1))
            self.assertEqual(len(read_reviews(root)),2)
            self.assertEqual(len(pd.read_csv(_path(root, True))),3)
            self.assertEqual(save_reviews(root,'ENS-BI-02',[a]),(1,0))
            self.assertEqual(len(read_reviews(root)),3)
    def test_no_fake_grade_or_bad_grades(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            bad=sample();bad['NOTE_PERTINENCE_1_5']='6'
            with self.assertRaises(ValueError):save_reviews(root,'ENS-BI-01',[bad])
            blank=sample();blank.update({
                'NOTE_PERTINENCE_1_5':'', 'NOTE_NIVEAU_1_5':'',
                'NOTE_LACUNE_1_5':'', 'PREREQUIS':'', 'COMMENTAIRE':''
            })
            self.assertEqual(save_reviews(root,'ENS-BI-01',[blank]),(0,0))
            self.assertFalse(_path(root).exists())
    def test_secondary_without_pertinence_refused_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = sample()
            row['NOTE_PERTINENCE_1_5'] = ''
            with self.assertRaisesRegex(ValueError, 'Pertinence /5 obligatoire'):
                save_reviews(root, 'ENS-BI-01', [row])
            self.assertFalse(_path(root).exists())

    def test_partial_batch_is_atomic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid = sample(ch='CH_A')
            invalid = sample(ch='CH_B')
            invalid['NOTE_PERTINENCE_1_5'] = ''
            with self.assertRaisesRegex(ValueError, 'Pertinence /5 obligatoire'):
                save_reviews(root, 'ENS-BI-01', [valid, invalid])
            self.assertFalse(_path(root).exists())

    def test_pertinence_only_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = sample()
            for key in ('NOTE_NIVEAU_1_5','NOTE_LACUNE_1_5','PREREQUIS','COMMENTAIRE'):
                row[key] = ''
            self.assertEqual(save_reviews(root,'ENS-BI-01',[row]),(1,0))
            saved = read_reviews(root).iloc[0]
            self.assertEqual(saved['NOTE_PERTINENCE_1_5'], '4')
            self.assertEqual(saved['NOTE_NIVEAU_1_5'], '')

    def test_empty_or_nan_cells_are_ignored(self):
        self.assertFalse(_valider_note_principale({
            'NOTE_PERTINENCE_1_5':float('nan'), 'NOTE_NIVEAU_1_5':'',
            'NOTE_LACUNE_1_5':'', 'PREREQUIS':None, 'COMMENTAIRE':''
        }))

    def test_duplicate_and_invalid_status_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaises(ValueError): save_reviews(root,'ENS-BI-01',[sample(),sample()])
            bad=pd.DataFrame([sample()]);bad['STATUT']='APPROUVE'
            with self.assertRaises(ValueError):pool_from_exports(pd.DataFrame(),bad)

if __name__=='__main__': unittest.main()
