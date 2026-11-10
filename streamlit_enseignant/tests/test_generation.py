from __future__ import annotations
import sys
import tempfile
from pathlib import Path
import unittest
import json
from unittest.mock import patch
from io import BytesIO
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from generation_pedagogique import (gap_assessment,chercher_contexte,creer_proposition,
    exporter_catalogue_valide,lister_propositions,actual_catalogue,reviser_proposition,
    generer_avec_ollama,validate_content)

CORPUS=pd.DataFrame([{'chapitre_id':'CH1','parcours_id':'BI','cours_id':'C1',
  'chapitre_titre':'Introduction Power BI','texte_indexable':'tableau de bord visualisation'}])
LESSONS=pd.DataFrame([{'chapter_id':'CH1','lesson_title':'Premiers graphiques',
  'learning_objectives':'Produire un graphique de colonnes'}])
DOCUMENT={'titre':'Nettoyage des données dans Power Query',
 'objectif':'Nettoyer et transformer des données provenant de sources hétérogènes',
 'contenu':'Cette leçon explicite les différentes étapes de nettoyage, de normalisation, de contrôle des valeurs manquantes et de transformation des données avec exemples à vérifier par le formateur.',
 'mots_cles':'power query, nettoyage, valeurs manquantes',
 'references':[],
 'lecons':[{'titre':'Traitement des valeurs manquantes','objectif':'Repérer et corriger les valeurs manquantes dans un tableau de données',
            'contenu':'Contenu proposé pour revue','mots_cles':'NA, nettoyage'}]}

class GenerationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def test_gap_and_empty_sources(self):
  res=gap_assessment('nettoyage des fichiers incohérents','BI',CORPUS,LESSONS)
  self.assertEqual(res['statut'],'COUVERTURE_FAIBLE')
  empty=chercher_contexte(self.root,'absent','BI','C1',CORPUS,LESSONS)
  self.assertEqual(empty['statut'],'AUCUN_PASSAGE_PERTINENT')
 def test_approval_workflow_without_premature_publication(self):
  context={'elements':[],'n_pdf':0,'statut':'AUCUNE_SOURCE'}
  ident=creer_proposition(self.root,'CHAPITRE','BI','C1','','T1','BI_D',
                          'nettoyage des données',DOCUMENT,context,'','REDACTION_MANUELLE')
  self.assertEqual(len(lister_propositions(self.root,'EN_ATTENTE')),1)
  self.assertFalse((self.root/'outputs/streamlit_validation/catalogue_chapitres_enseignants_valides.csv').exists())
  with self.assertRaises(ValueError):
   reviser_proposition(self.root,ident,'APPROUVE','prof1','Validé',DOCUMENT,False,1)
  reviser_proposition(self.root,ident,'APPROUVE','prof1','Vérification de l’exactitude, du niveau et des prérequis',DOCUMENT,True,1)
  result=exporter_catalogue_valide(self.root)
  self.assertEqual(result['chapitres'],1)
  self.assertEqual(result['lecons'],1)
  chapters,lessons=actual_catalogue(self.root,CORPUS,LESSONS)
  self.assertEqual(len(chapters),2)
  self.assertEqual(len(lessons),2)
  self.assertTrue('CHAP_GEN_' in chapters.iloc[1]['chapitre_id'])
  with self.assertRaises(ValueError):
   reviser_proposition(self.root,ident,'APPROUVE','prof1','duplicate',DOCUMENT,True,1)
 def test_reject_never_publishes(self):
  context={'elements':[],'n_pdf':0,'statut':'AUCUNE_SOURCE'}
  ident=creer_proposition(self.root,'CHAPITRE','BI','C1','','T0','BI_I','nouvelle compétence',DOCUMENT,context,'','REDACTION_MANUELLE')
  reviser_proposition(self.root,ident,'REJETE','prof2','hors référentiel',DOCUMENT,False,1)
  self.assertEqual(exporter_catalogue_valide(self.root)['chapitres'],0)
 def test_lesson_no_new_chapter(self):
  doc={**DOCUMENT,'lecons':[]}
  ctx={'elements':[],'n_pdf':0,'statut':'AUCUNE_SOURCE'}
  ident=creer_proposition(self.root,'LECON','BI','C1','CH1','T1','BI_A','nettoyage',doc,ctx,'','REDACTION_MANUELLE')
  reviser_proposition(self.root,ident,'APPROUVE','prof2','validation documentée',doc,True,1)
  result=exporter_catalogue_valide(self.root)
  self.assertEqual(result['chapitres'],0);self.assertEqual(result['lecons'],1)
  l=pd.read_csv(self.root/'outputs/streamlit_validation/catalogue_lecons_enseignants_valides.csv')
  self.assertEqual(l.iloc[0]['chapter_id'],'CH1')
 def test_reject_fabricated_source(self):
  with self.assertRaises(ValueError):validate_content('CHAPITRE',dict(DOCUMENT,references=['PDF_INVENTE']),references_admises=[])
 def test_legacy_lesson_schema_preserved(self):
  legacy=pd.DataFrame([{'chapitre_id':'CH1','lecon_id':'L1','lecon_titre':'Premier'},
                       {'chapitre_id':'CH1','lecon_id':'L2','lecon_titre':'Deuxième'}])
  chap,lecons=actual_catalogue(self.root,CORPUS,legacy)
  self.assertEqual(len(lecons),2)
  self.assertEqual(set(lecons['lesson_id']),{'L1','L2'})
  self.assertEqual(set(lecons['chapter_id']),{'CH1'})
 def test_ollama_mock(self):
  payload={'response':json.dumps(DOCUMENT,ensure_ascii=False)}
  class MockResponse:
   def __enter__(self):return self
   def __exit__(self,*args):return False
   def read(self):return json.dumps(payload).encode()
  with patch('generation_pedagogique.urlopen',return_value=MockResponse()):
   content=generer_avec_ollama('CHAPITRE','BI','C1','','nettoyage',{'elements':[], 'n_pdf':0},'test:1b')
  self.assertEqual(content['titre'],DOCUMENT['titre'])
 def test_real_pdf_retrieval(self):
  try:import fitz
  except ImportError:self.skipTest('PyMuPDF non disponible pour test PDF')
  folder=self.root/'data'/'ressources_pedagogiques';folder.mkdir(parents=True)
  pdf=fitz.open();page=pdf.new_page();page.insert_text((50,80),
     'Power Query permet de nettoyer les donnees manquantes et transformer les colonnes de tableaux. '*6,
     fontsize=10); pdf.save(folder/'cours.pdf');pdf.close()
  cat=CORPUS.assign(chemin_pdf='cours.pdf')
  result=chercher_contexte(self.root,'nettoyer donnees manquantes','BI','C1',cat,LESSONS)
  self.assertGreater(result['n_pdf'],0)
  self.assertEqual(result['statut'],'RAG_PDF')

if __name__=='__main__':unittest.main()
