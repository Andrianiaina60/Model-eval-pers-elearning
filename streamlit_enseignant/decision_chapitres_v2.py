"""Décisions pédagogiques versionnées, séparées des exportations scientifiques et H5.

La recommandation automatique initiale ne doit jamais être écrasée.
La décision de conserver/remplacer/rejeter est distincte des ajouts facultatifs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import closing
import os
import tempfile
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

import pandas as pd

RELATIVE_DB = Path('outputs/streamlit_validation/decisions_chapitres_v2.sqlite3')
DECISIONS = {'VALIDE', 'REMPLACE', 'REJETE', 'AUCUNE_PROPOSITION'}
PARCOURS = {'DA', 'BI', 'DS', 'IA'}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _connect(root: Path) -> sqlite3.Connection:
    path = Path(root) / RELATIVE_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA busy_timeout=15000')
    con.execute('''CREATE TABLE IF NOT EXISTS decisions_chapitres (
        id TEXT PRIMARY KEY,
        date_utc TEXT NOT NULL,
        etape TEXT NOT NULL,
        groupe_id TEXT NOT NULL,
        parcours TEXT NOT NULL,
        chapitre_initial_id TEXT NOT NULL,
        chapitre_initial_titre TEXT NOT NULL,
        cours_id TEXT NOT NULL,
        decision TEXT NOT NULL,
        enseignant_id TEXT NOT NULL,
        justification TEXT NOT NULL,
        chapitre_existants_json TEXT NOT NULL,
        nouveaux_titres_json TEXT NOT NULL,
        nouveaux_titres_approuves INTEGER NOT NULL,
        lacunes_json TEXT NOT NULL,
        source_suggestion TEXT NOT NULL,
        modele TEXT NOT NULL,
        provenance TEXT NOT NULL DEFAULT 'REVISION_ENSEIGNANTE_APRES_RECOMMANDATION'
    )''')
    return con


def _clean_titles(titles: list[str]) -> list[str]:
    if not isinstance(titles, list):
        raise ValueError('Les titres doivent être fournis dans une liste.')
    result, seen = [], set()
    for title in titles:
        title = ' '.join(str(title).strip().split())
        if not title:
            continue
        if len(title) < 5 or len(title) > 180:
            raise ValueError('Chaque titre doit comporter entre 5 et 180 caractères.')
        if title.casefold() not in seen:
            result.append(title)
            seen.add(title.casefold())
    if len(result) > 20:
        raise ValueError('Limite : 20 nouveaux titres pour une décision.')
    return result


def _check_catalogue(
    catalogue: pd.DataFrame, parcours: str, initial_id: str, selected_ids: list[str]
) -> list[str]:
    if not isinstance(selected_ids, list):
        raise ValueError('Sélections de chapitres invalides.')
    distinct = list(dict.fromkeys(str(x).strip() for x in selected_ids if str(x).strip()))
    if initial_id in distinct:
        raise ValueError('Le chapitre initial ne doit pas être ajouté comme alternative à lui-même.')
    if catalogue.empty:
        if distinct:
            raise ValueError('Impossible de valider des chapitres existants sans catalogue.')
        return distinct
    required = {'parcours_id', 'chapitre_id'}
    if not required.issubset(catalogue.columns):
        raise ValueError('Catalogue incomplet : parcours_id / chapitre_id.')
    authorized = set(catalogue.loc[catalogue['parcours_id'].astype(str).eq(parcours), 'chapitre_id'].astype(str))
    if not set(distinct).issubset(authorized):
        raise ValueError('Un chapitre sélectionné est absent du parcours de référence.')
    return distinct


def save_decision(
    root: Path,
    *,
    etape: str,
    groupe_id: str,
    parcours: str,
    chapitre_initial_id: str,
    chapitre_initial_titre: str,
    cours_id: str,
    decision: str,
    enseignant_id: str,
    justification: str,
    chapitres_existants: list[str],
    nouveaux_titres: list[str],
    titres_approuves: bool,
    lacunes: list[dict],
    catalogue: pd.DataFrame,
    source_suggestion: str = 'AUCUNE',
    modele: str = '',
) -> str:
    if etape not in {'T0', 'T1'} or parcours not in PARCOURS or decision not in DECISIONS:
        raise ValueError('Cycle, parcours ou décision invalide.')
    if not str(groupe_id).strip() or not str(enseignant_id).strip():
        raise ValueError('Groupe et identifiant enseignant obligatoires.')
    if len(str(enseignant_id).strip()) < 3:
        raise ValueError('Identifiant enseignant trop court (3 caractères minimum).')
    if decision != 'AUCUNE_PROPOSITION' and not str(chapitre_initial_id).strip():
        raise ValueError('Identifiant du chapitre initial obligatoire.')
    if decision == 'AUCUNE_PROPOSITION' and str(chapitre_initial_id).strip():
        raise ValueError('Une absence de proposition ne peut porter sur un chapitre existant.')
    if decision != 'AUCUNE_PROPOSITION' and not str(chapitre_initial_titre).strip():
        raise ValueError('Titre du chapitre initial obligatoire.')
    if decision in {'REMPLACE', 'REJETE'} and not str(justification).strip():
        raise ValueError('Justification obligatoire pour remplacer ou rejeter.')
    if decision == 'AUCUNE_PROPOSITION' and not str(justification).strip():
        raise ValueError('Justification obligatoire pour un groupe sans recommandation.')
    if not isinstance(lacunes, list):
        raise ValueError('Les lacunes doivent être une liste.')
    existing = _check_catalogue(catalogue, parcours, str(chapitre_initial_id), chapitres_existants)
    titles = _clean_titles(nouveaux_titres)
    if titles and not catalogue.empty and {'parcours_id', 'chapitre_titre'}.issubset(catalogue.columns):
        same_parcours = catalogue.loc[catalogue['parcours_id'].astype(str).eq(parcours)]
        known_titles = {str(v).strip().casefold() for v in same_parcours['chapitre_titre']}
        if any(title.casefold() in known_titles for title in titles):
            raise ValueError('Un titre nouveau existe déjà dans le catalogue du parcours ; le sélectionner parmi les chapitres existants.')
        if 'cours_id' in same_parcours.columns:
            known_courses = set(same_parcours['cours_id'].astype(str))
            if cours_id not in known_courses:
                raise ValueError('Le cours destinataire ne fait pas partie du catalogue de ce parcours.')
    if decision == 'REMPLACE' and not existing and not titles:
        raise ValueError('REMPLACE nécessite au moins un chapitre existant ou un titre nouveau.')
    if decision == 'REJETE' and not existing and not titles:
        # Un rejet simple reste autorisé : l'enseignant peut conclure qu'aucun ajout n'est nécessaire.
        pass
    if (titles or existing) and not str(justification).strip():
        raise ValueError('Justification requise pour les ajouts ou les alternatives pédagogiques.')
    if titles and not str(cours_id).strip():
        raise ValueError('Choisir un cours destinataire pour les nouveaux titres.')
    if titles and not isinstance(titres_approuves, bool):
        raise ValueError('Confirmation des titres invalide.')
    code = f'REV_{uuid4().hex[:20]}'
    row = (
        code, _timestamp(), etape, str(groupe_id), parcours,
        str(chapitre_initial_id), str(chapitre_initial_titre), str(cours_id),
        decision, str(enseignant_id).strip(), str(justification).strip(),
        json.dumps(existing, ensure_ascii=False), json.dumps(titles, ensure_ascii=False),
        int(bool(titres_approuves) and bool(titles)),
        json.dumps(lacunes, ensure_ascii=False), str(source_suggestion), str(modele),
    )
    with closing(_connect(root)) as con:
        con.execute('''INSERT INTO decisions_chapitres (
            id,date_utc,etape,groupe_id,parcours,chapitre_initial_id,chapitre_initial_titre,
            cours_id,decision,enseignant_id,justification,chapitre_existants_json,
            nouveaux_titres_json,nouveaux_titres_approuves,lacunes_json,source_suggestion,modele
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', row)
        con.commit()
    export_decisions_csv(root)
    return code


def read_decisions(root: Path, only_last: bool = False) -> pd.DataFrame:
    with closing(_connect(root)) as con:
        df = pd.read_sql_query('SELECT * FROM decisions_chapitres ORDER BY date_utc, rowid', con)
    if only_last and not df.empty:
        df = df.drop_duplicates(['etape', 'groupe_id', 'chapitre_initial_id'], keep='last')
    return df


def approved_titles_for_decision(row: dict) -> list[str]:
    if not bool(row.get('nouveaux_titres_approuves', 0)):
        return []
    try:
        return _clean_titles(json.loads(row['nouveaux_titres_json']))
    except (ValueError, TypeError, KeyError):
        return []


def export_decisions_csv(root: Path) -> Path:
    """Miroir CSV pour le manuscrit; l'historique SQLite reste la source de vérité."""
    path = Path(root) / 'outputs/streamlit_validation/decisions_chapitres_v2.csv'
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = read_decisions(root)
    fd, tmp = tempfile.mkstemp(prefix='decisions_chapitres_v2_', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8-sig', newline='') as stream:
            rows.to_csv(stream, index=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return path
