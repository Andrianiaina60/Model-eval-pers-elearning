
# Prédiction et évaluation de la performance académique par intelligence artificielle — Adaptive e-Learning

## Présentation du projet

Ce dépôt contient les travaux expérimentaux d'un projet de **Master Recherche en Informatique**, réalisé à l'École Nationale d'Informatique (ENI), Université de Fianarantsoa, Madagascar.

Le projet étudie l'utilisation de l'intelligence artificielle pour prédire les performances académiques, analyser les compétences et les lacunes des apprenants, recommander des parcours de formation et proposer des ressources pédagogiques adaptées.

Il repose sur une architecture d'**Adaptive e-Learning à deux cycles**, combinant apprentissage automatique, intelligence artificielle explicable (XAI), recommandation pédagogique et supervision humaine (*Human-in-the-Loop*).

## Objectifs

Le projet poursuit cinq objectifs principaux :

1. Analyser les données initiales et les résultats des évaluations des apprenants.
2. Prédire la performance académique finale à partir des informations disponibles à différents moments.
3. Proposer des parcours de formation selon les compétences, les lacunes, les objectifs et les prérequis.
4. Constituer des groupes pédagogiques selon le parcours observé et le niveau relatif des apprenants.
5. Recommander des chapitres pédagogiques adaptés aux besoins collectifs, sous supervision enseignante.

## Architecture générale

Le système exploite quatre sources de données :

| Source | Description |
|---|---|
| D1 | Données d'inscription et profils |
| T0 | Test diagnostique initial |
| T1 | Test intermédiaire |
| T2 | Test final |

Le fonctionnement expérimental est organisé en deux cycles.

### Cycle 1 — Après T0

- Intégration des profils et des résultats diagnostiques.
- Analyse des compétences initiales et des lacunes.
- Prédiction précoce de la performance finale T2.
- Recommandation automatique de parcours.
- Revue et arbitrage pédagogique par les enseignants.
- Préparation de recommandations collectives de chapitres.

### Cycle 2 — Après T1

- Actualisation des informations de l'apprenant.
- Nouvelle prédiction de T2 intégrant les résultats T1.
- Identification du parcours observé dans les évaluations.
- Constitution de groupes pédagogiques par parcours et niveau relatif.
- Analyse des lacunes collectives.
- Recommandation hybride de chapitres.
- Évaluation et validation enseignante.

T2 constitue la cible observée pour l'entraînement et l'évaluation des modèles. Il ne doit pas être utilisé comme information d'entrée lors des décisions réalisées à T0 ou T1.

## Parcours de formation

Quatre parcours sont étudiés :

| Code | Parcours |
|---|---|
| DA | Data Analysis |
| BI | Business Intelligence |
| DS | Data Science |
| IA | Intelligence Artificielle |

Chaque parcours comprend trois niveaux pédagogiques relatifs : Débutant, Intermédiaire et Avancé.

Le regroupement post-T1 comporte ainsi **12 groupes pédagogiques**.

## Organisation du projet

```text
Model-eval-pers-elearning/
│
├── notebooks/
│   ├── 00_audit_sources_donnees.ipynb
│   ├── 01_integration_nettoyage.ipynb
│   ├── 02_diagnostic_T0.ipynb
│   ├── 03_modelisation_MT0_MT1.ipynb
│   ├── 04_validation_XAI.ipynb
│   ├── 05_groupes_recommandation.ipynb
│   └── 06_RAG_TFIDF_LLM_HITL.ipynb
│
├── data/
│   └── ressources_pedagogiques/
│
├── outputs/
│   ├── 02_diagnostic_T0/
│   ├── 03_modelisation_MT0_MT1/
│   ├── 04_validation_XAI/
│   ├── 05_groupes_recommandation/
│   ├── 06_RAG_LLM_HITL_HIERARCHIQUE/
│   └── streamlit_validation/
│
├── streamlit_enseignant/
│   ├── app.py
│   ├── data_access.py
│   ├── decision_store.py
│   ├── decision_chapitres_v2.py
│   ├── generation_pedagogique.py
│   ├── page_generation.py
│   ├── page_validation_chapitres.py
│   └── validation_rapide_h5.py
│
├── requirements.txt
└── README.md
```

Cette arborescence présente les principaux composants du projet. Certains notebooks et modules peuvent avoir des variantes ou des fichiers complémentaires.

## Description des notebooks

| Notebook | Fonction |
|---|---|
| 00 — Audit des sources | Vérification des données, identifiants, schémas et qualité |
| 01 — Intégration et nettoyage | Normalisation et appariement des sources D1/T0/T1/T2 |
| 02 — Diagnostic T0 | Analyse des scores, compétences et lacunes initiales |
| 03 — Modélisation | Prédiction de T2 à partir de D1/T0, puis D1/T0/T1 |
| 04 — Validation et XAI | Validation des performances, statistiques, SHAP et importance des variables |
| 05 — Groupes et recommandations | Orientation initiale et constitution de groupes pédagogiques |
| 06 — Ressources pédagogiques | Recommandation hybride de chapitres, RAG/LLM complémentaires et supervision humaine |

Les notebooks sont conçus pour préserver la séparation entre les données expérimentales, les résultats calculés et les décisions humaines.

## Modélisation prédictive

La tâche principale consiste à prédire le score final T2.

Deux cadres de modélisation sont comparés :

**MT0 — Modèle initial**

```text
Profil D1 + Diagnostic T0 → Prédiction T2
```

**MT1 — Modèle enrichi**

```text
Profil D1 + Diagnostic T0 + Évaluation T1 → Prédiction T2
```

Les expérimentations mobilisent notamment :

- RandomForest
- Régression linéaire
- Méthodes d'évaluation statistique
- Validation croisée imbriquée répétée
- MAE, RMSE et R²
- Analyse d'importance des variables
- SHAP et importance par permutation

### Résultat expérimental principal

Sur la cohorte de 105 dossiers T2 complets, RandomForest présente les résultats suivants :

| Indicateur | Valeur |
|---|---:|
| MAE avec informations initiales | 20,30 |
| MAE après intégration de T1 | 15,91 |
| Réduction de MAE | 4,39 |
| Intervalle de confiance à 95 % du gain | [2,26 ; 6,47] |

Ces résultats indiquent une amélioration de la prédiction lorsque l'information intermédiaire T1 est intégrée, dans le périmètre de la cohorte étudiée.

## Orientation et supervision humaine

Le dispositif distingue quatre informations :

| Variable | Signification |
|---|---|
| `P_recommended` | Parcours proposé automatiquement |
| `P_teacher` | Avis ou décision pédagogique de l'enseignant |
| `P_chosen` | Parcours explicitement choisi par l'apprenant |
| `P_followed` | Parcours effectivement suivi ou estimé à partir des observations |

**Important :** le choix explicite `P_chosen` n'a pas été recueilli dans les données expérimentales disponibles.

Le parcours identifié à T1 sert d'indicateur observable de `P_followed`. Il ne constitue pas une preuve du choix libre initial.

Les décisions enseignantes doivent rester distinguées des recommandations automatiques et des règles appliquées sans relecture individuelle.

## Recommandation pédagogique

Les ressources pédagogiques sont organisées selon la hiérarchie :

```text
Domaine
  └── Parcours
       └── Cours
            └── Chapitre
                 └── Leçon
```

L'unité principale de recommandation est le **chapitre pédagogique**.

Le moteur hybride exploite :

- Les compétences et lacunes collectives.
- Le parcours et le niveau du groupe.
- La représentation lexicale TF-IDF.
- Les représentations sémantiques multilingues.
- La fusion des classements par Reciprocal Rank Fusion (RRF).

Le RAG et les modèles de langage (LLM) interviennent comme composants complémentaires pour la recherche documentaire et la proposition de contenus, sans validation pédagogique automatique.

## Interface Streamlit

Le projet comprend un prototype Streamlit destiné aux **enseignants**.

Il permet notamment :

- La consultation des diagnostics.
- L'affichage des recommandations de parcours.
- La consultation des prédictions et analyses XAI.
- L'exploration des groupes et de leurs lacunes.
- L'évaluation de pertinence des chapitres.
- La validation, la modification ou le rejet de propositions.
- La proposition de nouveaux titres de chapitres et de leçons.
- La consultation des décisions et de leur traçabilité.

Les recommandations ne deviennent pas automatiquement des contenus pédagogiques validés.

L'interface Streamlit n'est pas une plateforme d'apprentissage destinée directement aux apprenants.

## Technologies

**Analyse scientifique :** Python, NumPy, Pandas, SciPy, Statsmodels.

**Machine Learning :** Scikit-learn, XGBoost, LightGBM, CatBoost.

**Explicabilité :** SHAP, LIME.

**Recommandation :** TF-IDF, embeddings sémantiques, RRF.

**Visualisation :** Matplotlib, Seaborn, Plotly.

**Interface :** Streamlit.

**Traitement documentaire :** PDF, RAG et modèles de langage locaux facultatifs.

**Stockage :** CSV, JSON et SQLite pour certaines décisions pédagogiques.

## Installation

### 1. Cloner le dépôt

```bash
git clone https://github.com/Andrianiaina60/Model-eval-pers-elearning.git
cd Model-eval-pers-elearning
```

### 2. Créer un environnement virtuel

Sous Linux :

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Sous Windows :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Installer les dépendances

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Pour les modules utilisant les supports PDF et les représentations sémantiques, des dépendances complémentaires peuvent être nécessaires :

```bash
pip install pypdf sentence-transformers
```

Les versions exactes de ces dépendances complémentaires doivent être figées après vérification de l'environnement d'exécution.

## Exécution

### Notebooks

Démarrer Jupyter :

```bash
jupyter notebook
```

Exécuter les notebooks dans l'ordre logique de traitement, de 00 à 06, en vérifiant les chemins de données et les fichiers attendus.

### Application Streamlit

Depuis la racine du projet :

```bash
streamlit run streamlit_enseignant/app.py
```

L'interface est généralement accessible à l'adresse :

```text
http://localhost:8501
```

Les fonctionnalités de revue protégées nécessitent la configuration des variables d'environnement appropriées, notamment `TEACHER_REVIEW_PASSWORD` pour certaines pages.

### Vérification des exports

```bash
python streamlit_enseignant/preflight_integration.py
```

Cette commande contrôle la présence et certains schémas des fichiers attendus. Elle ne constitue pas une validation scientifique des résultats.

## Données et reproductibilité

Les expérimentations utilisent des données d'inscription et d'évaluation collectées dans le cadre de la formation étudiée.

Les principaux effectifs documentés sont :

| Source / cohorte | Effectif |
|---|---:|
| Inscriptions D1 | 472 |
| Diagnostics T0 identifiables | 305 |
| Évaluations T1 identifiables | 196 |
| Évaluations T2 identifiables | 206 |
| Cohorte longitudinale principale | 125 |
| Dossiers T2 complets pour certaines analyses | 105 |

Ces effectifs ne représentent pas une cohorte unique de même taille à chaque étape.

Les résultats doivent être interprétés en tenant compte de l'appariement des identifiants, de la disponibilité des données et des différences entre instruments d'évaluation.

Les données individuelles ne doivent pas être publiées sans autorisation appropriée.

## Limites scientifiques

Cette recherche comporte plusieurs limites :

1. Les résultats prédictifs proviennent d'une cohorte limitée.
2. Les instruments T0, T1 et T2 n'ont pas exactement la même granularité.
3. Le choix explicite des apprenants n'a pas été documenté.
4. Les évaluations pédagogiques reposent sur un nombre limité d'enseignants et ne fournissent pas de mesure d'accord inter-évaluateurs.
5. Les jugements de pertinence des chapitres ne démontrent pas à eux seuls la supériorité comparative du moteur hybride.
6. L'exposition réelle des apprenants aux ressources recommandées et ses effets sur leurs performances n'ont pas été mesurés.
7. Les comportements, stratégies et méthodes d'apprentissage réellement employés par les apprenants n'ont pas fait l'objet d'une étude expérimentale.

Le projet démontre principalement une amélioration prédictive dans le cadre évalué et présente une architecture de personnalisation pédagogique supervisée.

## Perspectives

Les prolongements envisagés comprennent :

- Une validation sur de nouvelles cohortes.
- L'amélioration de la prédiction des faibles performances.
- La collecte explicite des choix de parcours.
- L'étude des comportements et stratégies d'apprentissage.
- L'évaluation comparative des moteurs de recommandation.
- La mesure de l'accord entre plusieurs évaluateurs.
- Une expérimentation prospective de l'effet des recommandations pédagogiques.
- L'extension de l'architecture à de nouveaux cycles d'évaluation.

## Cadre académique

**Établissement :** École Nationale d'Informatique (ENI)

**Université :** Université de Fianarantsoa, Madagascar

**Formation :** Master Recherche en Informatique

**Parcours :** Génie logiciel et bases de données

**Auteur :** RAVINTSOANDRAIBE Andrianiaina

## Licence et utilisation

Ce dépôt est destiné à la documentation et à la reproductibilité des travaux de recherche.

Aucune licence de réutilisation n'est accordée implicitement en l'absence d'un fichier `LICENSE` explicite. Les données pédagogiques, les documents tiers et les informations individuelles restent soumis à leurs autorisations respectives.

---

**Projet académique — Master Recherche | Adaptive e-Learning | Intelligence artificielle | Educational Data Mining**
