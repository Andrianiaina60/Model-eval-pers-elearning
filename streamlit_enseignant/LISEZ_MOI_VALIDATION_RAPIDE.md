# Validation rapide des chapitres — Intégration non destructive

## Installation

1. Depuis la racine du projet, sauvegarder `streamlit_enseignant/` et `outputs/streamlit_validation/`.
2. **Option légère (recommandée) :** copier seulement `streamlit_enseignant/validation_rapide_h5.py` du pack dans votre dossier Streamlit existant, puis modifier `app.py` en ajoutant :

```python
from validation_rapide_h5 import show_page as show_h5_fast_review
```

Dans `PAGES`, insérer `Évaluation rapide H5` après `Validation enseignante`. Avant la branche `elif page=='Catalogue pédagogique':`, ajouter :

```python
elif page=='Évaluation rapide H5':
    show_h5_fast_review(ROOT,data)
```

**Option complète :** utiliser le `app.py` et `validation_rapide_h5.py` inclus. Les autres modules du pack restent inchangés.

3. Exécuter :

```bash
python -m unittest discover -s streamlit_enseignant/tests -v
python -m streamlit run streamlit_enseignant/app.py --server.address 127.0.0.1
```

## Utilisation pour les quatre enseignants

- Dans `Évaluation rapide H5`, choisir DA / BI / DS / IA, saisir un identifiant d’enseignant réel.
- Commencer par **T1** : 36 propositions sur 12 groupes ; puis **T0** : 33 propositions sur 11 groupes. Le groupe `T0_BI_Avance` est non couvert.
- Ouvrir les PDF pédagogiques si disponibles et noter plusieurs chapitres au sein d’une grille : pertinence, adéquation au niveau, adéquation à la lacune (1–5), prérequis et justification.
- Enregistrer en une fois ; la grille se recharge après sauvegarde.
- Le groupe absent `T0_BI_Avance` peut faire l’objet d'un avis séparé (ressource manquante / aucun besoin / à vérifier).

Les rangs/scores/méthodes ne sont jamais présentés dans cette page. Il est essentiel de ne pas montrer aux enseignants les autres pages de classement avant la fin des évaluations si l'on souhaite réduire le biais de connaissance des méthodes.

## Données

Écrit :
- `outputs/streamlit_validation/jugements_H5_enseignants.csv` (dernier avis par enseignant et proposition)
- `outputs/streamlit_validation/jugements_H5_historique.csv` (historique des saisies et révisions)
- `outputs/streamlit_validation/couverture_groupes_sans_recommandation.csv` (justifications de groupes sans candidats)

N'écrase aucun CSV des notebooks 00–06. Les décisions opérationnelles `avis_chapitres.csv` restent indépendantes.

## Portée scientifique

Cette version collecte des jugements réels sur **les 69 propositions hybrides existantes**. Elle ne suffit pas à comparer TF-IDF, E5 et RRF, car un pool multi-méthodes et des classements séparés manquent. Les identités sont déclaratives : vérifier la participation et le consentement hors application. Une seule évaluation par parcours ne permet pas de calculer l'accord inter-évaluateurs.

Le mot de passe `TEACHER_REVIEW_PASSWORD` protège seulement la page de **génération IA**, pas la revue H5.
