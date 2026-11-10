# Protocole de traçabilité des barèmes — Master Recherche

## Périmètre
Trois tests, **140 questions** (T0 : 20 ; T1 : 60 ; T2 : 60), et **10 arbitrages prioritaires** (T1 : 7, T2 : 3). Les anciennes réponses sont conservées dans `sources_originales/` et les propositions de correction dans `propositions_revision/`. Aucun de ces fichiers n'est une preuve de validation par un enseignant.

## Fichier principal
- `Registre_traçabilite_baremes_T0_T1_T2.xlsx` : onglets `Synthese`, `Registre_140`, `Arbitrages_10`, `Sources`, `Protocole`.
- `registre_baremes_140_questions.csv` : copie tabulaire modifiable et lisible par Python. **Seul ce registre CSV est utilisé par le script de contrôle final.** Le classeur est un support de relecture ; si vous y saisissez les décisions, reportez-les aussi dans le CSV (ou exportez l'onglet Registre_140 en CSV, avec exactement les mêmes en-têtes).
- `journal_decisions.csv` : append-only à tenir manuellement : ne pas effacer les décisions antérieures.
- `arbitrages_prioritaires_10_questions.csv` : vue figée de repérage pour les dix items litigieux. **Ne pas la considérer comme second registre de référence**.
- `manifest_sources_sha256.csv` : empreintes SHA-256 et tailles des huit fichiers gelés de départ.

## Processus de validation (sans simulation de validation humaine)
1. Conserver **sans modification** les six CSV `sources_originales/` et `propositions_revision/`, ainsi que le manifest.
2. Pour chaque item, comparer la question et les options originales, la réponse initiale, la proposition révisée et les sources documentaires.
3. Pour les dix items litigieux, demander une décision argumentée au formateur et vérifier si une seule réponse est légitime, plusieurs, aucune, ou si une exclusion est justifiée.
4. Dans `registre_baremes_140_questions.csv`, **renseigner réellement** `STATUT_VALIDATION` (`APPROUVE` / `REJETE` / `A_REVOIR`), `DECISION_BAREME` (`VALIDER_PROPOSITION` / `CONSERVER_ORIGINAL` / `MODIFIER` / `EXCLURE`), `REPONSE_DECIDEE`, `COMPETENCE_DECIDEE`, `JUSTIFICATION_DECIDEE`, `VALIDATEUR`, `QUALIFICATION_VALID`, `DATE_DECISION`, `SOURCE_PREUVE`, `COMMENTAIRE_VALIDATION`.
5. Ne jamais remplir `VALIDATEUR`, `DATE_DECISION` ou `SOURCE_PREUVE` sans preuve réelle. Le fichier révisé contient dix réponses volontairement vides ; ne pas les remplacer par hasard.
6. Enregistrer chaque arbitrage dans `journal_decisions.csv`, avec date, auteur, avant/après, justification et preuve. Ne pas écraser les lignes de journal existantes.
7. Une fois **les 140 items** approuvés par un responsable autorisé et chaque ambiguïté résolue, exécuter `python3 verifier_et_generer_corriges.py`. Le script refuse d'exporter un barème prétendument validé si des décisions manquent.
8. Comparer les résultats des modèles obtenus avec le barème historique et ceux obtenus avec le barème validé : n, distributions des scores, MAE, RMSE, R², IC, tests appariés ; conserver les mêmes cohortes et partitions et documenter chaque différence.

## Contraintes importantes pour les notebooks actuels
- Le code de notation actuel attend **une seule lettre A–E par question** et un corrigé complet de 20 ou 60 lignes. Une décision `EXCLURE` ou `REPONSES_MULTIPLES` nécessite une adaptation explicite du notebook avant d'être utilisée ; le script de génération refuse donc l'export standard dans ce cas.
- `corrige_T0_valide.csv` est attendu dans `outputs/02_diagnostic_T0/` ; `corrige_T1_valide.csv` et `corrige_T2_valide.csv` dans `outputs/03_modelisation_MT0_MT1/`.
- Le script n'écrit jamais directement dans les dossiers `outputs/` : les fichiers prêts à examiner sont produits dans `barèmes_approuvés_a_installer/` **seulement lorsque toutes les validations sont effectivement présentes**. Sauvegarder les fichiers en place avant toute installation.
- Pour un item dont la réponse proposée est vide, ne pas choisir l'option `VALIDER_PROPOSITION`.
- Les 126 formulations révisées concernent les étiquettes de compétences et les justifications, pas 126 changements de lettre. Aucune lettre non vide n'a été remplacée silencieusement dans la révision.

## États du dossier
- `A_VALIDER` = état initial du registre ; n'est pas une acceptation.
- `APPROUVE` = décision humaine explicite documentée ; ni la création des fichiers ni une sortie du notebook n'en constituent une preuve.

## Clause méthodologique pour le mémoire
« Les barèmes des évaluations T0, T1 et T2 ont fait l'objet d'une revue de cohérence portant sur les clés de réponse, les compétences évaluées et les justifications associées. Les réponses initiales ont été gelées et comparées aux propositions révisées dans un registre versionné, chaque item étant repéré par son étape, son parcours et son numéro. Les divergences ou ambiguïtés ont été signalées pour arbitrage humain documenté. Les analyses prédictives doivent distinguer explicitement les résultats produits avec le barème initial de ceux recalculés après validation des corrections, sans attribuer aux enseignants des validations non effectivement obtenues. »

> Cette clause décrit l'organisation de la revue ; ne déclarer les arbitrages comme effectivement achevés dans le manuscrit qu'une fois leurs signatures et preuves enregistrées.
