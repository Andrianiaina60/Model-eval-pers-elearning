import importlib.util
import io
import sys
import unittest
from pathlib import Path
import pandas as pd
# Importer les vrais modules de l'application, sans polluer sys.modules.
# tests/ est dans streamlit_enseignant/tests/ ; parents[1] = streamlit_enseignant/
APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

SRC = APP_DIR / 'validation_rapide_h5.py'
if not SRC.is_file():
    raise FileNotFoundError(f"Module H5 introuvable : {SRC}")
spec = importlib.util.spec_from_file_location('h5_import_test', SRC)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class ImportTests(unittest.TestCase):
    def setUp(self):
        self.pool = pd.DataFrame([{'ETAPE':'T1','ID_GROUPE':'G001','PARCOURS':'BI','ID_CHAPITRE':'CH_BI_1','CHAPITRE':'Power Query','RANG':'1'}])
    def content(self,note='4', title='Power Query'):
        return pd.DataFrame([{'Cycle':'T1','Groupe':'G001','Chapitre':title,'Pertinence /5':note,'Justification':'avis'}]).to_csv(index=False).encode('utf-8-sig')
    def test_accepts_valid(self):
        row=mod.prepare_csv_import(self.content(),self.pool,'ENS-BI-01','BI')[0]
        self.assertEqual(row['ID_CHAPITRE'],'CH_BI_1')
        self.assertEqual(row['NOTE_PERTINENCE_1_5'],'4')
    def test_invalid_note(self):
        with self.assertRaisesRegex(ValueError,'pertinence'):
            mod.prepare_csv_import(self.content('8'),self.pool,'ENS-BI-01','BI')
    def test_unknown_title(self):
        with self.assertRaisesRegex(ValueError,'inconnu'):
            mod.prepare_csv_import(self.content(title='Autre'),self.pool,'ENS-BI-01','BI')
    def test_wrong_path(self):
        with self.assertRaisesRegex(ValueError,'inconnu'):
            mod.prepare_csv_import(self.content(),self.pool,'ENS-DA-01','DA')
    def test_ambiguous_title(self):
        pool=pd.concat([self.pool,self.pool.assign(ID_CHAPITRE='CH_BI_2')])
        with self.assertRaisesRegex(ValueError,'ambigu'):
            mod.prepare_csv_import(self.content(),pool,'ENS-BI-01','BI')
if __name__=='__main__':unittest.main()
