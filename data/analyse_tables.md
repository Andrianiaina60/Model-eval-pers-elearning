# Analyse des deux tables DIEGO 2026

## Structure des tables

### Table 1 — `inscriptions.csv` (472 lignes)

| Colonne | Type | Description |
|---|---|---|
| **IDENTIFICATION** | Texte (clé) | Identifiant unique ex: `DIEG2026-001` |
| Année de naissance | Nombre | Année de naissance (quelques anomalies à nettoyer) |
| Genre | Catégorie | Masculin / Féminin |
| Région d'origine | Catégorie | 22 régions de Madagascar |
| Filière | Catégorie | 15 filières académiques |
| Niveau d'étude | Catégorie | L1 → Master 2 → Doctorat |
| Statut actuel | Catégorie | Étudiant plein temps, alternance, diplômé, etc. |
| Niveau informatique | Catégorie ordonnée | Aucun / Débutant / Intermédiaire / Avancé |
| Niveau Excel | Catégorie ordonnée | Aucun / Débutant / Intermédiaire / Avancé |
| Niveau Power BI | Catégorie ordonnée | Aucun / Débutant / Intermédiaire / Avancé |
| Niveau Python | Catégorie ordonnée | Aucun / Débutant / Intermédiaire / Avancé |
| Niveau IA | Catégorie ordonnée | Aucun / Débutant / Intermédiaire / Avancé |
| Motivation | Multi-valeur | 7 options (ex: Acquérir compétences, Employabilité…) |
| Objectif pro | Catégorie | Data Analyst, Data Scientist, Développeur, etc. |
| Disponibilité | Multi-valeur | Semaine matin/aprem/soir, Samedi, Week-end, Flexible |
| Source info | Catégorie | Facebook, LinkedIn, WhatsApp, Ami(e), etc. |
| Title | Texte | Nom composé (résidu post-anonymisation) |
| CreatedAt / UpdatedAt | Date | Horodatages |

---

### Table 2 — `tests.csv` (315 lignes)

| Colonne | Type | Description |
|---|---|---|
| **Identification** | Texte (clé) | Identifiant ex: `DIEG2026-001` |
| Date du test | Date | Moment où le test a été passé |
| Q1 – Q5 | Catégorie | Bloc **Excel** (5 questions à choix multiples) |
| Q6 – Q10 | Catégorie | Bloc **Power BI / DAX** (4 questions + 1 visu) |
| Q11 – Q15 | Catégorie | Bloc **Python / Data Science / ML** (5 questions) |
| Q16 – Q20 | Catégorie | Bloc **IA générative / LLM / RAG** (5 questions) |
| Commentaires | Texte libre | Commentaire optionnel du candidat |
| CreatedAt / UpdatedAt | Date | Horodatages |

**Détail des questions :**

| Question | Bloc | Sujet |
|---|---|---|
| Q1 | Excel | Résumer ventes par région |
| Q2 | Excel | Importer un CSV |
| Q3 | Excel | Modèle de données |
| Q4 | Excel | Mauvaise pratique de visualisation |
| Q5 | Excel | 2e grande valeur |
| Q6 | Power BI | Mesure vs Colonne DAX |
| Q7 | Power BI | CA année précédente DAX |
| Q8 | Power BI | Vue Modèle Power BI |
| Q9 | Power BI | Accès directeurs régionaux |
| Q10 | Power BI | 12 commerciaux 3 indicateurs |
| Q11 | Python | Bibliothèque CSV Python |
| Q12 | Data Science | Overfitting / Underfitting |
| Q13 | Data Science | Segmentation 50 000 clients |
| Q14 | ML | Déployer modèle Python API |
| Q15 | ML | Valeurs manquantes 30% |
| Q16 | IA | Rôle system prompt LLM |
| Q17 | IA | Assistant IA PDF financiers |
| Q18 | IA | Rôle embedding dans RAG |
| Q19 | IA | Agent IA sélection outil |
| Q20 | IA | Sortie fiable LLM tableau |

---

## Clé de liaison

```
inscriptions.IDENTIFICATION  ←→  tests.Identification
```

> ⚠️ Attention à la casse : `IDENTIFICATION` (majuscules) dans inscriptions vs `Identification` dans tests.

| | Nombre |
|---|---|
| Inscrits | 472 |
| Tests passés | 315 |
| Inscrits sans test | 157 (33%) |
| Tests sans Identification | ~6 (anonymes) |

---

## Axes d'analyse possibles

### A. Taux de participation
- % d'inscrits ayant passé le test
- Taux de passage par Filière, Genre, Région, Statut
- Délai entre inscription et passage du test

### B. Profil des participants
- Distribution par Genre, Région, Filière, Niveau d'étude
- Pyramide des âges (Année de naissance)
- Canal d'acquisition (Source info) → ROI marketing
- Motivations et objectifs professionnels

### C. Niveau déclaré vs score au test ⭐
- `Niveau Excel déclaré` → score aux Q1–Q5
- `Niveau Python déclaré` → score aux Q11–Q13
- `Niveau IA déclaré` → score aux Q16–Q20
- Identifier les surévaluations / sous-évaluations

### D. Analyse du score au test
- Score global (nb bonnes réponses / 20) par participant
- Score par bloc thématique (Excel, Power BI, Python, IA)
- Distribution des scores → courbe de niveau
- Questions les plus échouées → lacunes collectives

### E. Segmentation des candidats
- Croiser Objectif pro × Score → adéquation ambition/niveau
- Croiser Filière × Score par bloc → profils par origine académique
- Croiser Disponibilité × Statut → groupes de formation potentiels
- Clustering automatique (K-Means) pour placement en niveaux

### F. Analyse géographique
- Carte des inscriptions par région de Madagascar
- Taux de passage du test par région
- Score moyen par région

---

## Prochaines étapes recommandées

| Priorité | Analyse | Livrable |
|---|---|---|
| 🔴 Haute | Niveau déclaré vs score réel | Tableau comparatif + heatmap |
| 🔴 Haute | Taux de passage du test par segment | Tableau croisé + graphique barres |
| 🟡 Moyenne | Score par bloc × Filière | Heatmap blocs/filières |
| 🟡 Moyenne | Canal d'acquisition × taux conversion | Funnel marketing |
| 🟢 Exploratoire | Clustering candidats | Segments niveaux pour groupes |
