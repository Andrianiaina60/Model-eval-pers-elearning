from __future__ import annotations
from pathlib import Path
import sys,tempfile,unittest
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from data_access import PATHS,diagnostics,chapter_file_guard,safe_pdf,read_csv
from decision_store import save_record,read_state
from preflight_streamlit import check

SCHEMA_ROWS = {
 'diagnostic_t0':[{'_ID_NORM':'ID001','S_DA':'20','S_BI':'80','S_DS':'30','S_IA':'35'}],
 't1':[{'_ID_NORM':'ID001','PARCOURS_T1':'BI','SCORE_T1':'70'}],
 'recommandation_auto':[{'_ID_NORM':'ID001','PARCOURS_AUTO':'BI','STATUT_AUTO':'PROPOSITION_UNIVOQUE'}],
 'recommandation_finale_experimentale':[{'_ID_NORM':'ID001','PARCOURS_AUTO':'BI','STATUT_FINAL':'EN_ATTENTE_CHOIX_APPRENANT'}],
 'groupes_t0':[{'ID_GROUPE':'T0_BI_Debutant','PARCOURS':'BI','NIVEAU':'Debutant','LACUNE_PRINCIPALE':'relation'}],
 'groupes_t1':[{'ID_GROUPE':'G002','PARCOURS':'BI','NIVEAU':'Debutant','LACUNE_PRINCIPALE':'DAX'}],
 'base_groupes_t1':[{'_ID_NORM':'ID001','ID_GROUPE':'G002'}],
 'chapitres_t0':[{'ETAPE':'T0','ID_GROUPE':'T0_BI_Debutant','RANG':'1','PARCOURS':'BI','ID_CHAPITRE':'CH_BI01_01','CHAPITRE':'Power BI','STATUT':'CANDIDAT_HYBRIDE_NON_VALIDE'}],
 'chapitres_t1':[{'ETAPE':'T1','ID_GROUPE':'G002','RANG':'1','PARCOURS':'BI','ID_CHAPITRE':'CH_BI01_02','CHAPITRE':'DAX','STATUT':'CANDIDAT_HYBRIDE_NON_VALIDE'}],
 'catalogue_chapitres':[{'parcours_id':'BI','cours_id':'RES_BI_01','chapitre_id':'CH_BI01_01','chapitre_titre':'Power BI'}]
}

class WorkflowTests(unittest.TestCase):
 def setUp(self):
  self.d=tempfile.TemporaryDirectory()
  self.addCleanup(self.d.cleanup)
  self.root=Path(self.d.name)
  for name,rows in SCHEMA_ROWS.items():
   file=self.root/PATHS[name];file.parent.mkdir(parents=True,exist_ok=True)
   pd.DataFrame(rows).to_csv(file,index=False,encoding='utf-8-sig')
 def test_preflight(self):
  ok,report=check(self.root)
  self.assertTrue(ok,str(report))
 def test_missing(self):
  (self.root/PATHS['chapitres_t1']).unlink()
  ok,_=check(self.root)
  self.assertFalse(ok)
 def test_no_fake_teacher(self):
  self.assertTrue(read_state(self.root,'avis_chapitres').empty)
  row={'ETAPE':'T0','ID_GROUPE':'T0_BI_Debutant','ID_CHAPITRE':'CH_BI01_01',
   'DECISION_ENSEIGNANT':'VALIDE','CHAPITRE_REMPLACEMENT':'','VALIDATEUR':'Enseignant déclaré',
   'DATE_VALIDATION':'2026-10-27T01:00:00+00:00','COMMENTAIRE':'Vérifié'}
  save_record(self.root,'avis_chapitres',row)
  self.assertEqual(len(read_state(self.root,'avis_chapitres')),1)
  self.assertEqual(read_csv(self.root,'chapitres_t0').loc[0,'STATUT'],'CANDIDAT_HYBRIDE_NON_VALIDE')
  save_record(self.root,'avis_chapitres',dict(row,COMMENTAIRE='Revu'))
  self.assertEqual(len(read_state(self.root,'avis_chapitres')),1)
  self.assertEqual(len(pd.read_csv(self.root/'outputs/streamlit_validation/journal_evenements.csv')),2)
 def test_independent_choices(self):
  save_record(self.root,'avis_parcours',{'APPRENANT_ID':'ID001','DECISION_ENSEIGNANT':'MODIFIE',
   'PARCOURS_ENSEIGNANT':'DS','VALIDATEUR':'E1','DATE_VALIDATION':'2026-10-27','COMMENTAIRE':''})
  self.assertTrue(read_state(self.root,'choix_apprenants').empty)
  save_record(self.root,'choix_apprenants',{'APPRENANT_ID':'ID001','PARCOURS_CHOISI':'IA',
   'DATE_CHOIX':'2026-10-27','SOURCE_CHOIX':'Confirmation explicite'})
  self.assertEqual(read_state(self.root,'choix_apprenants').loc[0,'PARCOURS_CHOISI'],'IA')
 def test_safe_pdf(self):
  file=self.root/'data'/'ressources_pedagogiques'/'documents'/'cours.pdf'
  file.parent.mkdir(parents=True,exist_ok=True)
  file.write_bytes(b'%PDF-1.4')
  self.assertEqual(safe_pdf(self.root,'documents/cours.pdf'),file)
  outside=Path(self.d.name).parent/'another_book_private.pdf'
  self.assertIsNone(safe_pdf(self.root,str(outside)))
 def test_duplicate_chapters(self):
  row=SCHEMA_ROWS['chapitres_t0'][0]
  a=pd.DataFrame([row,row]);b=pd.DataFrame(SCHEMA_ROWS['chapitres_t1'])
  self.assertTrue(chapter_file_guard(a,b))

if __name__=='__main__':unittest.main()
