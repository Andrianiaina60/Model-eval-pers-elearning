from __future__ import annotations
import sys
import tempfile
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from decision_store import read_state,save_record

class DecisionStoreRegressionTests(unittest.TestCase):
    def test_unrelated_chapter_reviews_are_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def row(group, chapter, who):
                return dict(ETAPE='T1', ID_GROUPE=group,ID_CHAPITRE=chapter,
                            DECISION_ENSEIGNANT='VALIDE',CHAPITRE_REMPLACEMENT='',
                            NOTE_PERTINENCE='4',VALIDATEUR=who,DATE_VALIDATION='2026-11-02T00:00:00Z',COMMENTAIRE='revu')
            save_record(root,'avis_chapitres',row('GR1','CH1','A'))
            save_record(root,'avis_chapitres',row('GR1','CH2','B'))
            save_record(root,'avis_chapitres',row('GR2','CH1','C'))
            state=read_state(root,'avis_chapitres')
            self.assertEqual(len(state),3)
            save_record(root,'avis_chapitres',row('GR1','CH1','D'))
            state=read_state(root,'avis_chapitres')
            self.assertEqual(len(state),3)
            self.assertEqual(state.loc[(state.ID_GROUPE=='GR1') & (state.ID_CHAPITRE=='CH1'),'VALIDATEUR'].iloc[0],'D')
            journal=read_state(root,'avis_chapitres')
            self.assertEqual(set(journal.ID_GROUPE),{'GR1','GR2'})
    def test_student_choices_do_not_delete_others(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def r(uid,track):
                return dict(APPRENANT_ID=uid,PARCOURS_CHOISI=track,DATE_CHOIX='2026-11-02',SOURCE_CHOIX='Formulaire explicite')
            save_record(root,'choix_apprenants',r('S1','DA'))
            save_record(root,'choix_apprenants',r('S2','BI'))
            save_record(root,'choix_apprenants',r('S1','DS'))
            d=read_state(root,'choix_apprenants')
            self.assertEqual(len(d),2)
            self.assertEqual(d.loc[d.APPRENANT_ID=='S1','PARCOURS_CHOISI'].iloc[0],'DS')
if __name__=='__main__':unittest.main()
