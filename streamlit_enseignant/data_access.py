"""Lecture non destructive des exports 00--06. Aucune exécution de notebook."""
from __future__ import annotations
import os
from pathlib import Path
import json
import pandas as pd

PATHS = {
    "diagnostic_t0": "outputs/02_diagnostic_T0/resultat_T0_deux_cycles.csv",
    "t1": "outputs/03_modelisation_MT0_MT1/resultat_T1_deux_cycles.csv",
    "recommandation_auto": "outputs/05_groupes_recommandation/tables/deux_cycles/resultat_recommandation_auto_T0.csv",
    "recommandation_finale_experimentale": "outputs/05_groupes_recommandation/tables/deux_cycles/resultat_recommandation_finale_T0.csv",
    "groupes_t0": "outputs/05_groupes_recommandation/tables/deux_cycles/recommandations_contenu_groupes_T0.csv",
    "groupes_t1": "outputs/05_groupes_recommandation/tables/recommandations_contenu_groupes.csv",
    "base_groupes_t1": "outputs/05_groupes_recommandation/tables/base_groupes_pedagogiques.csv",
    "couverture_t1": "outputs/05_groupes_recommandation/tables/couverture_lacunes_T1_par_groupe.csv",
    "chapitres_t0": "outputs/06_RAG_LLM_HITL_HIERARCHIQUE/hybride_competences/recommandations_chapitres_streamlit_T0.csv",
    "chapitres_t1": "outputs/06_RAG_LLM_HITL_HIERARCHIQUE/hybride_competences/recommandations_chapitres_streamlit_T1.csv",
    "catalogue_chapitres": "data/ressources_pedagogiques/architecture/catalogue_chapitres_embeddings.csv",
    "catalogue_lecons": "data/ressources_pedagogiques/architecture/catalogue_lecons_embeddings.csv",
    "cours": "data/ressources_pedagogiques/architecture/cours.csv",
    "source_lecons": "data/ressources_pedagogiques/chapitres_lecons.csv",
    "modele_metadata": "outputs/04_validation_XAI/models/MT1_RandomForest_final_metadata.json",
    "xai_importance": "outputs/04_validation_XAI/tables/importance_native_RF.csv",
    "xai_permutation": "outputs/04_validation_XAI/tables/permutation_importance_CV.csv",
    "xai_shap": "outputs/04_validation_XAI/tables/importance_SHAP.csv",
    "besoins_t0_t1": "outputs/06_RAG_LLM_HITL_HIERARCHIQUE/hybride_competences/besoins_collectifs_T0_T1.csv",
    "rapport_organisation": "data/ressources_pedagogiques/plateforme/_index/rapport_organisation.json",
}
REQUIRED = {
    "diagnostic_t0", "t1", "recommandation_auto", "recommandation_finale_experimentale",
    "groupes_t0", "groupes_t1", "base_groupes_t1", "chapitres_t0", "chapitres_t1", "catalogue_chapitres",
}
SCHEMAS = {
    "diagnostic_t0": {"_ID_NORM", "S_DA", "S_BI", "S_DS", "S_IA"},
    "t1": {"_ID_NORM", "PARCOURS_T1", "SCORE_T1"},
    "recommandation_auto": {"_ID_NORM", "PARCOURS_AUTO", "STATUT_AUTO"},
    "recommandation_finale_experimentale": {"_ID_NORM", "PARCOURS_AUTO", "STATUT_FINAL"},
    "groupes_t0": {"ID_GROUPE", "PARCOURS", "NIVEAU", "LACUNE_PRINCIPALE"},
    "groupes_t1": {"ID_GROUPE", "PARCOURS", "NIVEAU", "LACUNE_PRINCIPALE"},
    "base_groupes_t1": {"_ID_NORM", "ID_GROUPE"},
    "chapitres_t0": {"ETAPE", "ID_GROUPE", "RANG", "PARCOURS", "ID_CHAPITRE", "CHAPITRE", "STATUT"},
    "chapitres_t1": {"ETAPE", "ID_GROUPE", "RANG", "PARCOURS", "ID_CHAPITRE", "CHAPITRE", "STATUT"},
    "catalogue_chapitres": {"parcours_id", "cours_id", "chapitre_id", "chapitre_titre"},
    "besoins_t0_t1": {"ETAPE", "ID_GROUPE", "COMPETENCE", "POIDS"},
}

def project_root(script_dir: Path | None = None) -> Path:
    override = os.environ.get("PROJECT_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    bases = [Path.cwd()]
    if script_dir is not None: bases.append(Path(script_dir))
    for base in bases:
        for candidate in (base, *base.parents):
            if (candidate / "outputs" / "05_groupes_recommandation" / "tables").is_dir():
                return candidate.resolve()
    return (script_dir or Path.cwd()).resolve()

def read_csv(root: Path, name: str) -> pd.DataFrame:
    if name not in PATHS or not PATHS[name].endswith('.csv'):
        raise KeyError(name)
    path = Path(root) / PATHS[name]
    if not path.is_file():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, encoding="utf-8-sig", keep_default_na=False)

def read_json(root: Path, name: str) -> dict:
    if not PATHS[name].endswith('.json'): raise KeyError(name)
    path=Path(root)/PATHS[name]
    if not path.is_file(): return {}
    with open(path,encoding='utf-8') as f: return json.load(f)

def diagnostics(root: Path) -> list[dict]:
    result=[]
    for name, rel in PATHS.items():
        path=Path(root)/rel
        status='OK' if path.is_file() else ('MANQUANT' if name in REQUIRED else 'OPTIONNEL_ABSENT')
        detail=''
        n=None
        if status=='OK' and name in SCHEMAS:
            try:
                df=read_csv(root,name)
                n=len(df)
                miss=SCHEMAS[name] - set(df.columns)
                if miss:
                    status='COLONNES_MANQUANTES';detail=', '.join(sorted(miss))
                elif name in ('chapitres_t0','chapitres_t1') and (df['ETAPE'] != name[-2:].upper()).any():
                    status='ETAPE_INCOHERENTE';detail='La colonne ETAPE ne correspond pas au fichier'
                elif name in ('groupes_t0','groupes_t1') and df['ID_GROUPE'].duplicated().any():
                    status='GROUPES_DUPLIQUES'
            except Exception as e:
                status='ERREUR_LECTURE';detail=f'{type(e).__name__}: {str(e)[:140]}'
        result.append({'Fichier':name, 'Statut':status,'Lignes':n,'Détail':detail,'Chemin':rel})
    return result

def safe_pdf(root: Path, value: str) -> Path | None:
    """PDF sous projet uniquement. Interdit lecture arbitraire et chemins absolus externes."""
    val=(value or '').strip()
    if not val or val.lower() in {'nan','none'}: return None
    base=Path(root).resolve()
    raw=Path(val)
    options=[raw] if raw.is_absolute() else [base/raw, base/'data'/'ressources_pedagogiques'/raw]
    for candidate in options:
        try:
            actual=candidate.resolve(strict=True)
            if actual.is_relative_to(base) and actual.is_file() and actual.suffix.lower()=='.pdf':
                return actual
        except (OSError,RuntimeError):pass
    return None

def chapter_file_guard(t0:pd.DataFrame,t1:pd.DataFrame)->list[str]:
    problems=[]
    for label, df in [('T0',t0),('T1',t1)]:
        if df.empty: problems.append(f'{label} : fichier absent ou vide'); continue
        if df.duplicated(['ETAPE','ID_GROUPE','ID_CHAPITRE']).any():
            problems.append(f'{label}: doublons chapitre/groupe')
        if not df['ETAPE'].eq(label).all(): problems.append(f'{label}: cycle incorrect')
        if df['STATUT'].ne('CANDIDAT_HYBRIDE_NON_VALIDE').any():
            problems.append(f'{label}: statuts inattendus dans l’export brut')
        if 'TARGET_T2' in df.columns or 'T2_REEL' in df.columns:
            problems.append(f'{label}: colonne T2 observée dans les candidats')
    return problems
