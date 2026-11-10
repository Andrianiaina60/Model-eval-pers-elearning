"""Revue H5 rapide: jugements experts par parcours, sans afficher le modèle ou son rang.

N'écrit jamais dans data/, notebooks/ ou les exports expérimentaux 00-06.
Ne peut pas produire une comparaison TF-IDF/E5/RRF sans un pool multi-méthodes.
"""
from __future__ import annotations

import csv
import hashlib
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from data_access import safe_pdf

PARCOURS = {
    'DA': 'Excel / Data Analysis',
    'BI': 'Power BI / Business Intelligence',
    'DS': 'Data Science',
    'IA': 'Intelligence Artificielle',
}
FIELDS = [
    'EVALUATEUR_ID', 'PARCOURS', 'ETAPE', 'ID_GROUPE', 'ID_CHAPITRE',
    'NOTE_PERTINENCE_1_5', 'NOTE_NIVEAU_1_5', 'NOTE_LACUNE_1_5',
    'PREREQUIS', 'COMMENTAIRE', 'DATE_EVALUATION_UTC',
    'METHODE_SOURCE', 'RANG_SOURCE', 'TITRE_CHAPITRE',
]
KEYS = ['EVALUATEUR_ID', 'ETAPE', 'ID_GROUPE', 'ID_CHAPITRE']
DECISIONS = ['', 'NON_VERIFIES', 'SATISFAITS', 'NON_SATISFAITS']


def _path(root: Path, historisation=False) -> Path:
    name = 'jugements_H5_historique.csv' if historisation else 'jugements_H5_enseignants.csv'
    return Path(root) / 'outputs' / 'streamlit_validation' / name


def _atomic_write(path: Path, rows: list[dict], columns: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=path.stem+'_', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def read_reviews(root: Path) -> pd.DataFrame:
    path = _path(root)
    if not path.is_file():
        return pd.DataFrame(columns=FIELDS)
    result = pd.read_csv(path, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    absent = set(FIELDS) - set(result.columns)
    if absent:
        raise ValueError(f'Fichier H5 incomplet : {sorted(absent)}')
    return result[FIELDS].copy()


def pool_from_exports(t0: pd.DataFrame, t1: pd.DataFrame, groups_t0: pd.DataFrame | None = None,
                      groups_t1: pd.DataFrame | None = None) -> pd.DataFrame:
    required = {'ETAPE', 'ID_GROUPE', 'PARCOURS', 'ID_CHAPITRE', 'CHAPITRE', 'RANG'}
    frames = []
    for phase, df, groups in [('T0', t0, groups_t0), ('T1', t1, groups_t1)]:
        if df.empty:
            continue
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f'{phase}: colonnes manquantes : {sorted(missing)}')
        if not df['ETAPE'].astype(str).eq(phase).all():
            raise ValueError(f'{phase}: la colonne ETAPE est incohérente')
        tmp = df.copy().fillna('').astype(str)
        if 'STATUT' in tmp.columns and not tmp['STATUT'].eq('CANDIDAT_HYBRIDE_NON_VALIDE').all():
            raise ValueError(f'{phase}: statut inattendu ; ne pas modifier les propositions historiques')
        tmp['LACUNE_GROUPE'] = ''
        if groups is not None and not groups.empty and {'ID_GROUPE', 'LACUNE_PRINCIPALE'}.issubset(groups.columns):
            gl = (groups.drop_duplicates('ID_GROUPE').set_index('ID_GROUPE')['LACUNE_PRINCIPALE']
                  .astype(str).to_dict())
            tmp['LACUNE_GROUPE'] = tmp['ID_GROUPE'].map(gl).fillna('')
        frames.append(tmp)
    if not frames:
        return pd.DataFrame(columns=['ETAPE', 'ID_GROUPE', 'PARCOURS', 'ID_CHAPITRE', 'CHAPITRE', 'RANG'])
    combined = pd.concat(frames, ignore_index=True)
    dup = combined.duplicated(['ETAPE', 'ID_GROUPE', 'ID_CHAPITRE'])
    if dup.any():
        raise ValueError('Identifiants de proposition dupliqués : revue suspendue')
    unknown = set(combined['PARCOURS']) - set(PARCOURS)
    if unknown:
        raise ValueError(f'Parcours non reconnus: {unknown}')
    # Ordre stable et aléatoire dans le navigateur; le rang et la méthode ne sont pas visibles.
    combined['_ORDER_BLIND'] = combined.apply(
        lambda r: hashlib.sha256(f"h5|{r['ETAPE']}|{r['ID_GROUPE']}|{r['ID_CHAPITRE']}".encode()).hexdigest(),
        axis=1)
    return combined.sort_values('_ORDER_BLIND').reset_index(drop=True)


def _normaliser_saisie(value) -> str:
    """Cellules vides (notamment pandas/Streamlit) et nombres saisis."""
    if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        return ''
    return str(value).strip()


def _valid_note(value):
    return _normaliser_saisie(value) in {'1', '2', '3', '4', '5'}


def _valider_note_principale(row: dict) -> bool:
    """Une ligne évaluée doit comporter une pertinence 1–5.

    Une ligne entièrement vide reste une proposition non évaluée ; aucune
    appréciation secondaire ne doit être enregistrée sans la note principale.
    """
    note = _normaliser_saisie(row.get('NOTE_PERTINENCE_1_5', ''))
    autres = ('NOTE_NIVEAU_1_5', 'NOTE_LACUNE_1_5', 'PREREQUIS', 'COMMENTAIRE')
    commencée = any(_normaliser_saisie(row.get(c, '')) for c in autres)
    if not note:
        if commencée:
            raise ValueError(
                f"Pertinence /5 obligatoire pour le chapitre {row.get('ID_CHAPITRE', '?')} "
                "dès qu'une autre appréciation est renseignée. "
                "Choisir une note de 1 à 5 ou effacer les autres appréciations de cette ligne."
            )
        return False
    if not _valid_note(note):
        raise ValueError(
            f"Pertinence /5 invalide pour le chapitre {row.get('ID_CHAPITRE', '?')} : "
            "sélectionner une note entière de 1 à 5."
        )
    return True


def save_reviews(root: Path, reviewer: str, rows: list[dict]) -> tuple[int, int]:
    """Enregistre uniquement les notes explicitement saisies; journalise les révisions."""
    reviewer = reviewer.strip()
    if len(reviewer) < 3:
        raise ValueError('Renseigner un identifiant d’enseignant (3 caractères minimum).')
    before = read_reviews(root)
    existing = before.to_dict('records')
    journal_path = _path(root, historisation=True)
    if journal_path.exists():
        log = pd.read_csv(journal_path, dtype=str, keep_default_na=False, encoding='utf-8-sig').to_dict('records')
    else:
        log = []
    inserted, modified = 0, 0
    unique = set()
    for r in rows:
        if not _valider_note_principale(r):
            continue
        note = _normaliser_saisie(r.get('NOTE_PERTINENCE_1_5', ''))
        if r.get('PARCOURS') not in PARCOURS or r.get('ETAPE') not in {'T0', 'T1'}:
            raise ValueError('Parcours/cycle non reconnu.')
        for c in ('NOTE_NIVEAU_1_5', 'NOTE_LACUNE_1_5'):
            if _normaliser_saisie(r.get(c, '')) and not _valid_note(r[c]):
                raise ValueError(f'{c}: utiliser une note de 1 à 5 ou laisser vide.')
        if _normaliser_saisie(r.get('PREREQUIS', '')) not in DECISIONS:
            raise ValueError('Valeur de prérequis invalide.')
        key = (reviewer, str(r['ETAPE']), str(r['ID_GROUPE']), str(r['ID_CHAPITRE']))
        if key in unique:
            raise ValueError('Une proposition est répétée dans la saisie.')
        unique.add(key)
        if not str(r['ID_GROUPE']).strip() or not str(r['ID_CHAPITRE']).strip():
            raise ValueError('Identifiants de groupe ou chapitre manquants.')
        prior = next((i for i, e in enumerate(existing) if tuple(e.get(k, '') for k in KEYS) == key), None)
        entry = {c: '' for c in FIELDS}
        entry.update({
            'EVALUATEUR_ID': reviewer,
            'PARCOURS': str(r['PARCOURS']),
            'ETAPE': str(r['ETAPE']),
            'ID_GROUPE': str(r['ID_GROUPE']),
            'ID_CHAPITRE': str(r['ID_CHAPITRE']),
            'NOTE_PERTINENCE_1_5': note,
            'NOTE_NIVEAU_1_5': _normaliser_saisie(r.get('NOTE_NIVEAU_1_5', '')),
            'NOTE_LACUNE_1_5': _normaliser_saisie(r.get('NOTE_LACUNE_1_5', '')),
            'PREREQUIS': _normaliser_saisie(r.get('PREREQUIS', '')),
            'COMMENTAIRE': _normaliser_saisie(r.get('COMMENTAIRE', '')),
            'DATE_EVALUATION_UTC': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'METHODE_SOURCE': 'HYBRIDE_RRF',
            'RANG_SOURCE': str(r.get('RANG', '')),
            'TITRE_CHAPITRE': str(r.get('CHAPITRE', '')),
        })
        if prior is not None:
            old = existing[prior]
            if old['PARCOURS'] != entry['PARCOURS']:
                raise ValueError('Le parcours d’une évaluation existante ne peut pas changer.')
            # Ignorer les soumissions inchangées, pour éviter un historique artificiellement gonflé.
            fields_to_compare = [k for k in FIELDS if k != 'DATE_EVALUATION_UTC']
            if all(str(old.get(k, '')) == str(entry.get(k, '')) for k in fields_to_compare):
                continue
            existing[prior] = entry
            modified += 1
        else:
            old = None
            existing.append(entry)
            inserted += 1
        log.append({**entry, 'ACTION': 'REVISION' if old else 'CREATION',
                    'NOTE_PRECEDENTE': old['NOTE_PERTINENCE_1_5'] if old else ''})
    if inserted or modified:
        _atomic_write(_path(root), existing, FIELDS)
        _atomic_write(journal_path, log, FIELDS + ['ACTION', 'NOTE_PRECEDENTE'])
    return inserted, modified


def _review_table(pool: pd.DataFrame, previous: pd.DataFrame, reviewer: str) -> pd.DataFrame:
    data = []
    lookup = {}
    if not previous.empty:
        scoped = previous[previous['EVALUATEUR_ID'].eq(reviewer)]
        lookup = {(r['ETAPE'], r['ID_GROUPE'], r['ID_CHAPITRE']): r for _, r in scoped.iterrows()}
    for _, r in pool.iterrows():
        old = lookup.get((r['ETAPE'], r['ID_GROUPE'], r['ID_CHAPITRE']), {})
        data.append({
            'Cycle': r['ETAPE'], 'Groupe': r['ID_GROUPE'],
            'Niveau': r.get('NIVEAU', ''),
            'Chapitre': r['CHAPITRE'],
            'Compétences': r.get('COMPETENCES_CIBLEES', ''),
            'Lacune collective': r.get('LACUNE_GROUPE', ''),
            'Pertinence /5': old.get('NOTE_PERTINENCE_1_5', ''),
            'Niveau /5': old.get('NOTE_NIVEAU_1_5', ''),
            'Lacune /5': old.get('NOTE_LACUNE_1_5', ''),
            'Prérequis': old.get('PREREQUIS', ''),
            'Justification': old.get('COMMENTAIRE', ''),
            '_ETAPE': r['ETAPE'], '_ID_GROUPE': r['ID_GROUPE'],
            '_ID_CHAPITRE': r['ID_CHAPITRE'], '_PARCOURS': r['PARCOURS'],
            '_RANG': r.get('RANG',''),
        })
    return pd.DataFrame(data)



def save_uncovered_group(root: Path, reviewer: str, phase: str, parcours: str, gid: str,
                         observation: str, justification: str):
    reviewer = reviewer.strip()
    if len(reviewer) < 3 or phase not in {'T0', 'T1'} or parcours not in PARCOURS or not gid.strip():
        raise ValueError('Enseignant, cycle, parcours et groupe obligatoires.')
    allowed = {'AUCUN_BESOIN_CIBLE', 'RESSOURCE_MANQUANTE', 'A_VERIFIER'}
    if observation not in allowed:
        raise ValueError('Diagnostic de couverture inconnu.')
    if not justification.strip():
        raise ValueError('Justifier ce groupe sans chapitre proposé.')
    path = Path(root) / 'outputs' / 'streamlit_validation' / 'couverture_groupes_sans_recommandation.csv'
    fields = ['EVALUATEUR_ID','ETAPE','PARCOURS','ID_GROUPE','OBSERVATION', 'JUSTIFICATION','DATE_UTC']
    old = pd.read_csv(path, dtype=str, keep_default_na=False, encoding='utf-8-sig').to_dict('records') if path.is_file() else []
    old = [r for r in old if not (r['EVALUATEUR_ID']==reviewer and r['ETAPE']==phase and r['ID_GROUPE']==gid)]
    old.append({'EVALUATEUR_ID':reviewer,'ETAPE':phase,'PARCOURS':parcours,'ID_GROUPE':gid,
                'OBSERVATION':observation,'JUSTIFICATION':justification.strip(),
                'DATE_UTC':datetime.now(timezone.utc).isoformat(timespec='seconds')})
    _atomic_write(path, old, fields)


def prepare_csv_import(file_bytes: bytes, pool: pd.DataFrame, reviewer: str, parcours: str,
                       filename: str = "import.csv") -> list[dict]:
    """Import strict de la grille H5 exportée, avec réconciliation au corpus historique.

    Les CSV exportés n'exposent pas ID_CHAPITRE : on refuse tout appariement ambigu.
    Les lignes doivent correspondre aux candidats historiques du parcours indiqué.
    """
    from io import BytesIO
    if not reviewer or len(reviewer.strip()) < 3:
        raise ValueError(f"{filename}: identifiant enseignant réel requis (3 caractères minimum).")
    if parcours not in PARCOURS:
        raise ValueError(f"{filename}: parcours non reconnu.")
    if len(file_bytes) > 5_000_000:
        raise ValueError(f"{filename}: CSV trop volumineux (limite 5 Mo).")
    try:
        imported = pd.read_csv(BytesIO(file_bytes), dtype=str, keep_default_na=False,
                               encoding='utf-8-sig', sep=None, engine='python')
    except Exception as exc:
        raise ValueError(f"{filename}: lecture CSV impossible : {exc}") from exc
    needed = {'Cycle', 'Groupe', 'Chapitre', 'Pertinence /5'}
    if not needed.issubset(imported.columns):
        raise ValueError(f"{filename}: colonnes absentes : {sorted(needed-set(imported.columns))}")
    if imported.empty:
        raise ValueError(f"{filename}: fichier vide.")
    reference = pool[pool['PARCOURS'].eq(parcours)]
    lookup = {}
    for _, r in reference.iterrows():
        key = (str(r['ETAPE']).strip(), str(r['ID_GROUPE']).strip(), str(r['CHAPITRE']).strip())
        lookup.setdefault(key, []).append(r)
    rows = []
    seen = set()
    for lineno, r in imported.iterrows():
        line = lineno + 2
        key = (str(r['Cycle']).strip(), str(r['Groupe']).strip(), str(r['Chapitre']).strip())
        candidates = lookup.get(key, [])
        if len(candidates) != 1:
            raise ValueError(
                f"{filename}, ligne {line}: candidat {'inconnu' if not candidates else 'ambigu'} "
                f"{key}; import refusé pour éviter une attribution erronée.")
        candidate = candidates[0]
        stable_key = (key[0], key[1], str(candidate['ID_CHAPITRE']))
        if stable_key in seen:
            raise ValueError(f"{filename}, ligne {line}: doublon {key}.")
        seen.add(stable_key)
        note = _normaliser_saisie(r['Pertinence /5'])
        if not _valid_note(note):
            raise ValueError(f"{filename}, ligne {line}: pertinence de 1 à 5 obligatoire.")
        optional = {}
        for label, dest in [('Niveau /5', 'NOTE_NIVEAU_1_5'), ('Lacune /5', 'NOTE_LACUNE_1_5')]:
            val = _normaliser_saisie(r.get(label, ''))
            if val and not _valid_note(val):
                raise ValueError(f"{filename}, ligne {line}: {label} invalide.")
            optional[dest] = val
        pre = _normaliser_saisie(r.get('Prérequis', ''))
        if pre not in DECISIONS:
            raise ValueError(f"{filename}, ligne {line}: prérequis invalide.")
        rows.append({
            'PARCOURS': parcours, 'ETAPE': key[0], 'ID_GROUPE': key[1],
            'ID_CHAPITRE': str(candidate['ID_CHAPITRE']),
            'CHAPITRE': str(candidate['CHAPITRE']), 'RANG': str(candidate.get('RANG', '')),
            'NOTE_PERTINENCE_1_5': note, 'PREREQUIS': pre,
            'COMMENTAIRE': _normaliser_saisie(r.get('Justification', '')),
            **optional,
        })
    return rows


def duplicate_import_keys(prepared: list[tuple], previous: pd.DataFrame) -> list[tuple]:
    """Return saved review keys also present in the uploaded CSV batch.

    This is independent of whether the imported score is identical or different:
    a previously saved evaluation must not be touched without explicit consent.
    """
    old_keys = {
        (str(row['EVALUATEUR_ID']), str(row['ETAPE']),
         str(row['ID_GROUPE']), str(row['ID_CHAPITRE']))
        for _, row in previous.iterrows()
    }
    return [
        (str(reviewer).strip(), str(row['ETAPE']),
         str(row['ID_GROUPE']), str(row['ID_CHAPITRE']))
        for _filename, reviewer, rows in prepared for row in rows
        if (str(reviewer).strip(), str(row['ETAPE']),
            str(row['ID_GROUPE']), str(row['ID_CHAPITRE'])) in old_keys
    ]


def import_prepared_reviews(root: Path, prepared: list[tuple],
                            replace_existing: bool = False) -> tuple[int, int]:
    """Persist prepared reviews, refusing overwrites without explicit confirmation.

    Uploads are checked as a batch before any file is written. save_reviews
    retains the existing revision history, and identical records are not
    duplicated. This does not authenticate the declared teacher identity.
    """
    all_keys = [
        (str(reviewer).strip(), str(row['ETAPE']),
         str(row['ID_GROUPE']), str(row['ID_CHAPITRE']))
        for _filename, reviewer, rows in prepared for row in rows
    ]
    if not prepared or not all_keys:
        raise ValueError('Aucune note à importer.')
    if len(all_keys) != len(set(all_keys)):
        raise ValueError('Doublons entre les CSV sélectionnés : import annulé.')
    previous = read_reviews(root)
    duplicates = duplicate_import_keys(prepared, previous)
    if duplicates and not replace_existing:
        raise ValueError('Des notes existent déjà : confirmer « OK, remplacer » ou annuler.')
    total_added = total_updated = 0
    for _filename, reviewer, rows in prepared:
        added, updated = save_reviews(root, reviewer, rows)
        total_added += added
        total_updated += updated
    return total_added, total_updated


def show_import_csv(root: Path, pool: pd.DataFrame):
    """Upload CSV with an explicit replacement/abort choice for saved reviews."""
    if st.session_state.pop('h5_import_confirmation', False):
        st.success('Importation réussie')

    with st.expander('Importer des évaluations H5 depuis des CSV', expanded=False):
        st.info('Import CSV exportés pertinence proposer. Chaque fichier doit être associé à son parcours et à l’identifiant réel de son enseignant. Aucune identité n’est déduite du nom du fichier.')
        batch = st.session_state.get('h5_import_batch_number', 0)
        files = st.file_uploader(
            'Sélectionner les CSV H5', type=['csv'], accept_multiple_files=True,
            key=f'h5_csv_files_{batch}'
        )
        if not files:
            return
        if len(files) > 8:
            st.error('Sélectionner au maximum 8 CSV par lot.')
            return

        prepared = []
        errors = []
        for i, upload in enumerate(files):
            with st.container():
                st.write(f'**{upload.name}**')
                c1, c2 = st.columns(2)
                parcours = c1.selectbox(
                    'Parcours de ce fichier', list(PARCOURS),
                    key=f'h5_import_path_{batch}_{i}',
                    format_func=lambda code: f'{code} — {PARCOURS[code]}'
                )
                teacher = c2.text_input(
                    'Identifiant réel de l’enseignant',
                    key=f'h5_import_reviewer_{batch}_{i}',
                    placeholder='Identifiant attribué lors de la collecte'
                )
                if not teacher.strip():
                    errors.append(f'{upload.name}: renseigner l’identifiant enseignant.')
                    continue
                try:
                    rows = prepare_csv_import(
                        upload.getvalue(), pool, teacher, parcours, upload.name
                    )
                    prepared.append((upload.name, teacher.strip(), rows))
                    st.caption(f'{len(rows)} notes valides et appariées à leurs chapitres historiques.')
                except Exception as exc:
                    errors.append(str(exc))
        if errors:
            for error in errors:
                st.error(error)
            st.caption('Aucun import tant que ces erreurs ne sont pas corrigées.')
            return

        all_keys = [
            (teacher, row['ETAPE'], row['ID_GROUPE'], row['ID_CHAPITRE'])
            for _, teacher, rows in prepared for row in rows
        ]
        if len(all_keys) != len(set(all_keys)):
            st.error('Doublons entre les CSV sélectionnés : import annulé.')
            return

        previous = read_reviews(root)
        duplicates = duplicate_import_keys(prepared, previous)
        count = sum(len(rows) for _, _, rows in prepared)
        st.write(f'**Aperçu : {len(prepared)} fichier(s), {count} note(s).**')
        st.dataframe(pd.DataFrame([
            {'Fichier': filename, 'Enseignant': reviewer, 'Nombre de notes': len(rows)}
            for filename, reviewer, rows in prepared
        ]), hide_index=True, use_container_width=True)

        confirmed = st.checkbox(
            'Je confirme que les notes ont été réellement saisies par les enseignants indiqués et que les fichiers sont les exports originaux.',
            key=f'h5_import_confirm_{batch}'
        )

        def save_and_notify(allow_replace: bool):
            try:
                import_prepared_reviews(root, prepared, replace_existing=allow_replace)
                st.session_state['h5_import_confirmation'] = True
                # A new uploader key clears the selection, without losing saved reviews.
                st.session_state['h5_import_batch_number'] = batch + 1
                st.rerun()
            except Exception as exc:
                st.error(f'Importation non effectuée : {exc}')

        if duplicates:
            st.warning(
                f'{len(duplicates)} évaluation(s) déjà enregistrée(s). '
                'Voulez-vous remplacer les données existantes ?'
            )
            yes, no = st.columns(2)
            if yes.button('OK, remplacer', type='primary', disabled=not confirmed,
                          key=f'h5_import_overwrite_{batch}'):
                save_and_notify(allow_replace=True)
            if no.button('Annuler', key=f'h5_import_cancel_{batch}'):
                st.session_state['h5_import_batch_number'] = batch + 1
                st.rerun()
        else:
            if st.button('Importer et sauvegarder les CSV validés',
                         type='primary', disabled=not confirmed,
                         key=f'h5_import_save_{batch}'):
                save_and_notify(allow_replace=False)


def show_page(root: Path, data):
    st.info('Revue expérimentale H5 : un enseignant référent par parcours. Classement et scores des méthodes masqués. Les jugements sont distincts des décisions de publication.')
    st.warning('Prototype local : identité déclarative non authentifiée. Vérifier les enseignants et leur consentement hors application avant une analyse scientifique.')
    try:
        pool = pool_from_exports(data('chapitres_t0'), data('chapitres_t1'), data('groupes_t0'), data('groupes_t1'))
        prior = read_reviews(root)
    except Exception as exc:
        st.error(f'Impossible de charger la revue : {exc}')
        return
    if pool.empty:
        st.error('Aucune proposition de chapitre disponible. Exécuter le contrôle du notebook 06.')
        return
    _u = st.session_state.get('user', {})
    _admin = _u.get('role') == 'admin'
    if _admin:
        show_import_csv(root, pool)
    parcours = st.selectbox('Parcours de l’enseignant référent', list(PARCOURS) if _admin else [_u.get('parcours', '')],
                           format_func=lambda x: f'{x} — {PARCOURS[x]}')
    _u = st.session_state.get('user', {})
    reviewer = st.text_input('Identifiant de l’enseignant évaluateur', value='' if _u.get('role') == 'admin' else _u.get('identifiant', ''), disabled=_u.get('role') != 'admin',
                             help='Renseigné automatiquement par la connexion.',
                             placeholder='Identifiant attribué selon le protocole, par exemple ENS-DA-01')
    cycle = st.radio('Cycle à évaluer', ['T1', 'T0', 'Tous'], horizontal=True)
    subset = pool[pool['PARCOURS'].eq(parcours)].copy()
    if cycle != 'Tous':
        subset = subset[subset['ETAPE'].eq(cycle)]
    total = len(subset)
    this_review = prior[(prior['PARCOURS'].eq(parcours)) &
                        (prior['EVALUATEUR_ID'].eq(reviewer.strip()))] if reviewer.strip() else prior.iloc[:0]
    keys = set(zip(this_review['ETAPE'], this_review['ID_GROUPE'], this_review['ID_CHAPITRE']))
    evaluated = int(sum((r['ETAPE'], r['ID_GROUPE'], r['ID_CHAPITRE']) in keys for _,r in subset.iterrows()))
    a,b,c = st.columns(3)
    a.metric('Chapitres proposés',total)
    b.metric('Déjà notés par cet enseignant',evaluated)
    c.metric('Restants',total-evaluated)
    if total:
        st.progress(evaluated / total)
    # Un groupe sans recommandation n'est pas une preuve d'absence de besoin.
    all_missing = []
    for etape in (['T0','T1'] if cycle == 'Tous' else [cycle]):
        gr = data('groupes_'+etape.lower())
        if gr.empty or not {'PARCOURS','ID_GROUPE'}.issubset(gr.columns):
            continue
        considered = set(pool.loc[pool['ETAPE'].eq(etape), 'ID_GROUPE'].astype(str))
        all_missing += [(etape, str(gid)) for gid in gr.loc[gr['PARCOURS'].eq(parcours),'ID_GROUPE'].astype(str) if gid not in considered]
    if all_missing:
        st.warning('Groupes sans chapitre candidat : '+', '.join(f'{a}/{b}' for a,b in all_missing))
        if reviewer.strip():
            with st.expander('Documenter un groupe sans recommandation'):
                with st.form(f'group_gap_{parcours}_{cycle}_{reviewer.strip()}'):
                    missing = st.selectbox('Groupe à examiner',all_missing,format_func=lambda x:f'{x[0]} — {x[1]}')
                    status = st.selectbox('Évaluation experte de l’absence de proposition',
                        ['A_VERIFIER','AUCUN_BESOIN_CIBLE','RESSOURCE_MANQUANTE'],
                        format_func=lambda x: {'A_VERIFIER':'Informations insuffisantes',
                        'AUCUN_BESOIN_CIBLE':'Aucune ressource nécessaire selon l’enseignant',
                        'RESSOURCE_MANQUANTE':'Une ressource devrait être proposée'}[x])
                    why=st.text_area('Justification documentée')
                    submit_gap=st.form_submit_button('Enregistrer le contrôle de couverture')
                if submit_gap:
                    try:
                        save_uncovered_group(root,reviewer,missing[0],parcours,missing[1],status,why)
                        st.success('Avis sur le groupe sans recommandation sauvegardé séparément.')
                    except Exception as exc:st.error(str(exc))
    if subset.empty:
        st.info('Aucun chapitre candidat pour ce parcours et ce cycle. Ce n’est pas une erreur : ne pas inventer de proposition.')
        return
    with st.expander('Examiner les documents du chapitre avant de noter'):
        choices=list(range(len(subset)))
        idx=st.selectbox('Chapitre',choices,format_func=lambda i:f"{subset.iloc[i]['ETAPE']} — {subset.iloc[i]['ID_GROUPE']} — {subset.iloc[i]['CHAPITRE']}")
        chosen_row=subset.iloc[idx]
        st.write('**Compétences visées :**',chosen_row.get('COMPETENCES_CIBLEES','—'))
        st.write('**Lacune collective :**',chosen_row.get('LACUNE_GROUPE','—'))
        pdf=safe_pdf(root,chosen_row.get('CHEMIN_PDF',''))
        if pdf:
            with open(pdf,'rb') as f:
                st.download_button('Consulter le PDF du cours',f.read(),file_name=pdf.name,mime='application/pdf')
        else:
            st.warning('Aucun PDF accessible : la note porte sur l’adéquation des métadonnées (titre, compétences, lacune), pas sur la qualité intrinsèque d’un contenu non consulté.')
    st.info('**Critère principal H5 : Pertinence /5.** Obligatoire pour chaque chapitre évalué. Les notes Niveau /5 et Lacune /5 sont complémentaires et facultatives. Laisser une ligne entièrement vide si elle n’a pas encore été évaluée.')
    st.caption('Échelle : 1 = très faible ; 2 = faible ; 3 = moyenne ; 4 = bonne ; 5 = excellente. Sans PDF, la note évalue seulement l’adéquation titre–compétences–lacunes, pas la qualité du contenu intégral.')
    if not reviewer.strip():
        st.info('Saisis ton identifiant d’enseignant avant de noter : les notes précédentes seront rechargées automatiquement.')
        return
    view = _review_table(subset, prior, reviewer.strip())
    private = ['_ETAPE','_ID_GROUPE','_ID_CHAPITRE','_PARCOURS','_RANG']
    display = view.drop(columns=private)
    read_only = ['Cycle','Groupe','Niveau','Chapitre','Compétences','Lacune collective']
    config = {
        'Pertinence /5': st.column_config.SelectboxColumn('Pertinence /5 *', options=['','1','2','3','4','5'], help='Note scientifique principale H5 : obligatoire dès que vous évaluez ce chapitre.'),
        'Niveau /5': st.column_config.SelectboxColumn('Niveau /5', options=['','1','2','3','4','5']),
        'Lacune /5': st.column_config.SelectboxColumn('Lacune /5', options=['','1','2','3','4','5']),
        'Prérequis': st.column_config.SelectboxColumn('Prérequis', options=DECISIONS),
        'Justification': st.column_config.TextColumn('Justification'),
        'Lacune collective': st.column_config.TextColumn('Lacune collective', width='large'),
        'Compétences': st.column_config.TextColumn('Compétences', width='large'),
        'Chapitre': st.column_config.TextColumn('Chapitre', width='large'),
    }
    with st.form(f'h5_form_{parcours}_{cycle}_{reviewer.strip()}'):
        edited = st.data_editor(display, num_rows='fixed', hide_index=True,
                                use_container_width=True, disabled=read_only, column_config=config,
                                key=f'h5_editor_{parcours}_{cycle}_{reviewer.strip()}')
        submitted = st.form_submit_button('Enregistrer toutes les notes renseignées', type='primary')
    if submitted:
        try:
            rows = []
            for idx, row in edited.iterrows():
                original = view.iloc[idx]
                rows.append({
                    'PARCOURS': original['_PARCOURS'],
                    'ETAPE': original['_ETAPE'],
                    'ID_GROUPE': original['_ID_GROUPE'],
                    'ID_CHAPITRE': original['_ID_CHAPITRE'],
                    'RANG': original['_RANG'],
                    'CHAPITRE': original['Chapitre'],
                    'NOTE_PERTINENCE_1_5': row['Pertinence /5'],
                    'NOTE_NIVEAU_1_5': row['Niveau /5'],
                    'NOTE_LACUNE_1_5': row['Lacune /5'],
                    'PREREQUIS': row['Prérequis'],
                    'COMMENTAIRE': row['Justification'],
                })
            added, revised = save_reviews(root, reviewer, rows)
            if added or revised:
                st.success(f'{added} nouvel(le)(s) avis et {revised} avis mis à jour. Les autres données sont conservées.')
                st.rerun()
            else:
                st.info('Aucune nouvelle note à enregistrer : les lignes non évaluées sont restées vides ou les avis étaient inchangés.')
        except Exception as exc:
            st.error(f'Échec de l’enregistrement : {exc}')
    st.caption('Évaluation portant sur les propositions hybrides disponibles (69 au total), et non sur la comparaison TF-IDF vs E5 vs RRF. Pour cette comparaison, constituer puis anonymiser un pool commun issu des trois méthodes.')
    st.caption('Exports : outputs/streamlit_validation/jugements_H5_enseignants.csv et jugements_H5_historique.csv. Les résultats 00–06 restent intacts.')
