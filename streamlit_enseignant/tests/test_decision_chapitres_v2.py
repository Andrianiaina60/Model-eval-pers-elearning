import json
from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from decision_chapitres_v2 import save_decision, read_decisions, approved_titles_for_decision


class DecisionsV2Tests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root=Path(self.folder.name)
        self.catalogue=pd.DataFrame([
            {'parcours_id':'BI','chapitre_id':'BI01','chapitre_titre':'Power Query','cours_id':'COURS_BI'},
            {'parcours_id':'BI','chapitre_id':'BI02','chapitre_titre':'Fusion','cours_id':'COURS_BI'},
            {'parcours_id':'BI','chapitre_id':'BI03','chapitre_titre':'Jointures','cours_id':'COURS_BI'},
            {'parcours_id':'DA','chapitre_id':'DA01','chapitre_titre':'Excel','cours_id':'COURS_DA'},
        ])
        self.base=dict(root=self.root,etape='T1',groupe_id='T1_G005',parcours='BI',
                       chapitre_initial_id='BI01',chapitre_initial_titre='Power Query',
                       cours_id='COURS_BI',enseignant_id='BI-ENS-01',justification='Le groupe nécessite ce contenu.',
                       chapitres_existants=[],nouveaux_titres=[],titres_approuves=False,
                       lacunes=[{'COMPETENCE':'Fusion Power Query','POIDS':'0.7'}],
                       catalogue=self.catalogue)

    def save(self, **overrides):
        args={**self.base, **overrides}
        return save_decision(**args)

    def test_valide_plus_multiple_chapters_and_titles(self):
        ident=self.save(decision='VALIDE',chapitres_existants=['BI02','BI03'],
                        nouveaux_titres=['Gestion des tables','Nettoyage des données'],titres_approuves=True)
        row=read_decisions(self.root).iloc[-1].to_dict()
        self.assertEqual(row['id'],ident)
        self.assertEqual(json.loads(row['chapitre_existants_json']),['BI02','BI03'])
        self.assertEqual(approved_titles_for_decision(row),['Gestion des tables','Nettoyage des données'])
        self.assertEqual(row['decision'],'VALIDE')

    def test_remplace_multiple_existing(self):
        self.save(decision='REMPLACE',chapitres_existants=['BI02','BI03'])
        row=read_decisions(self.root).iloc[-1]
        self.assertEqual(json.loads(row['chapitre_existants_json']),['BI02','BI03'])
        self.assertEqual(row['decision'],'REMPLACE')

    def test_remplace_unapproved_title_pending(self):
        self.save(decision='REMPLACE',nouveaux_titres=['Apprendre les jointures'],titres_approuves=False,
                  source_suggestion='LLM_SANS_RAG',modele='qwen2.5:3b')
        row=read_decisions(self.root).iloc[-1].to_dict()
        self.assertFalse(approved_titles_for_decision(row))
        self.assertEqual(json.loads(row['nouveaux_titres_json']),['Apprendre les jointures'])

    def test_remplace_requires_alternative(self):
        with self.assertRaisesRegex(ValueError,'au moins un chapitre'):
            self.save(decision='REMPLACE')

    def test_rejette_without_replacement(self):
        self.save(decision='REJETE')
        self.assertEqual(read_decisions(self.root).iloc[-1]['decision'],'REJETE')

    def test_missing_group_no_fake_candidate(self):
        self.save(decision='AUCUNE_PROPOSITION',chapitre_initial_id='',chapitre_initial_titre='',
                  nouveaux_titres=['Fusion et consolidation'],titres_approuves=True)
        self.assertEqual(read_decisions(self.root).iloc[-1]['chapitre_initial_id'],'')

    def test_cross_track_invalid(self):
        with self.assertRaisesRegex(ValueError,'absent du parcours'):
            self.save(decision='VALIDE',chapitres_existants=['DA01'])

    def test_initial_cannot_replace_itself(self):
        with self.assertRaisesRegex(ValueError,'lui-même'):
            self.save(decision='REMPLACE',chapitres_existants=['BI01'])

    def test_reject_duplicate_catalogue_title(self):
        with self.assertRaisesRegex(ValueError,'existe déjà'):
            self.save(decision='VALIDE',nouveaux_titres=['Fusion'],titres_approuves=True)

    def test_no_cross_course_for_generated_titles(self):
        with self.assertRaisesRegex(ValueError,'cours destinataire'):
            self.save(decision='VALIDE',nouveaux_titres=['Approfondissement des jointures'],
                      titres_approuves=True,cours_id='COURS_DA')

    def test_history_is_append_only_and_h5_unmodified(self):
        h5=self.root/'outputs/streamlit_validation/jugements_H5_enseignants.csv'
        h5.parent.mkdir(parents=True,exist_ok=True)
        h5.write_text('EVALUATEUR_ID,NOTE_PERTINENCE_1_5\n',encoding='utf-8')
        original=h5.read_bytes()
        self.save(decision='VALIDE')
        self.save(decision='REJETE',justification='Autres ressources requises')
        self.assertEqual(len(read_decisions(self.root)),2)
        self.assertEqual(len(read_decisions(self.root,only_last=True)),1)
        self.assertEqual(h5.read_bytes(),original)

    def test_no_catalogue_publication(self):
        self.save(decision='VALIDE',nouveaux_titres=['Apprendre la fusion des tables'],titres_approuves=True)
        dest=self.root/'outputs/streamlit_validation/catalogue_chapitres_enseignants_valides.csv'
        self.assertFalse(dest.exists())
        self.assertTrue((self.root/'outputs/streamlit_validation/decisions_chapitres_v2.csv').is_file())

    def test_justification_required_for_reject(self):
        with self.assertRaisesRegex(ValueError,'Justification'):
            self.save(decision='REJETE',justification='')

    def test_duplicate_titles_removed(self):
        self.save(decision='VALIDE',nouveaux_titres=['Gestion des jointures','  Gestion des jointures  '],titres_approuves=True)
        row=read_decisions(self.root).iloc[-1].to_dict()
        self.assertEqual(len(approved_titles_for_decision(row)),1)


if __name__=='__main__':
    unittest.main()
