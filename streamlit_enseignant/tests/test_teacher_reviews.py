"""Tests additionnels de notes et compatibilité historique, sans données réelles."""
from pathlib import Path
import sys,tempfile,unittest,csv
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from decision_store import save_record, read_state, state_path

class ReviewTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name)
  self.row={'ETAPE':'T0','ID_GROUPE':'T0_DA_Debutant','ID_CHAPITRE':'CH_DA01_01',
            'DECISION_ENSEIGNANT':'VALIDE','CHAPITRE_REMPLACEMENT':'',
            'NOTE_PERTINENCE':'5','VALIDATEUR':'Formateur declaratif',
            'DATE_VALIDATION':'2026-10-27T10:00:00Z','COMMENTAIRE':'Objectifs adaptes'}
 def test_note_and_old_row(self):
  save_record(self.root,'avis_chapitres',self.row)
  self.assertEqual(read_state(self.root,'avis_chapitres').iloc[0]['NOTE_PERTINENCE'],'5')
  # Simulation d'un CSV créé dans la version précédente.
  path=state_path(self.root,'avis_chapitres')
  old=pd.read_csv(path,dtype=str,keep_default_na=False).drop(columns=['NOTE_PERTINENCE'])
  old.to_csv(path,index=False,encoding='utf-8-sig')
  self.assertEqual(read_state(self.root,'avis_chapitres').iloc[0]['NOTE_PERTINENCE'],'')
  save_record(self.root,'avis_chapitres',dict(self.row,DECISION_ENSEIGNANT='REJETE',NOTE_PERTINENCE='2'))
  events=pd.read_csv(self.root/'outputs/streamlit_validation/journal_evenements.csv',dtype=str,keep_default_na=False)
  self.assertEqual(len(events),2)
  self.assertIn('APRES_JSON',events.columns)
  self.assertIn('AVANT_JSON',events.columns)
  self.assertIn('REJETE',events.iloc[-1]['APRES_JSON'])
 def test_reject_invalid_rating(self):
  with self.assertRaises(ValueError):
   save_record(self.root,'avis_chapitres',dict(self.row,NOTE_PERTINENCE='8'))
  self.assertFalse(state_path(self.root,'avis_chapitres').exists())
 def test_reject_self_replacement(self):
  with self.assertRaises(ValueError):
   save_record(self.root,'avis_chapitres',dict(self.row,DECISION_ENSEIGNANT='MODIFIE',CHAPITRE_REMPLACEMENT='CH_DA01_01'))
 def test_no_teacher_fabrication(self):
  self.assertTrue(read_state(self.root,'avis_chapitres').empty)
if __name__=='__main__':unittest.main()
