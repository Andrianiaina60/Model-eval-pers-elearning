"""Validation pédagogique opérationnelle par groupe et chapitre, distincte de H5."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from data_access import safe_pdf
from decision_chapitres_v2 import (
    approved_titles_for_decision, read_decisions, save_decision,
)
from generation_pedagogique import (
    actual_catalogue, chercher_contexte, creer_proposition, generer_avec_ollama,
)
from ollama_cancel_control import start_job, stop_job, completed_job

PARCOURS = {'DA': 'Data Analysis / Excel', 'BI': 'Business Intelligence / Power BI',
            'DS': 'Data Science', 'IA': 'Intelligence Artificielle'}
NIVEAUX = {'Debutant': 'Débutant', 'Intermediaire': 'Intermédiaire', 'Avance': 'Avancé'}


def _string(value) -> str:
    value = str(value or '').strip()
    return '' if value in {'nan', 'NaN', 'None'} else value


def _introduction_lacunes(data, cycle: str, gid: str, groupe: pd.Series) -> tuple[list[dict], str]:
    lacune_principale = _string(groupe.get('LACUNE_PRINCIPALE', ''))
    st.write('**Lacune principale du groupe :**', lacune_principale or 'Non précisée')
    needs = data('besoins_t0_t1')
    records = []
    if not needs.empty and {'ETAPE', 'ID_GROUPE', 'COMPETENCE'}.issubset(needs.columns):
        subset = needs.loc[needs['ETAPE'].eq(cycle) & needs['ID_GROUPE'].eq(gid)].copy()
        if 'POIDS' in subset.columns:
            subset['_poids_num'] = pd.to_numeric(subset['POIDS'].str.replace(',', '.', regex=False), errors='coerce')
            subset = subset.sort_values('_poids_num', ascending=False)
        for _, line in subset.iterrows():
            records.append({'COMPETENCE': _string(line.get('COMPETENCE', '')),
                            'POIDS': _string(line.get('POIDS', '')),
                            'PROVENANCE': _string(line.get('PROVENANCE', ''))})
        if records:
            st.caption('Liste complète des besoins collectifs du groupe, issus du notebook 06 (poids et provenance si disponibles).')
            st.dataframe(pd.DataFrame(records), hide_index=True, use_container_width=True)
    if not records:
        st.warning('Détail des compétences / poids absent pour ce groupe : ne pas inventer de lacunes.')
    return records, lacune_principale


def _catalogue_et_cours(root: Path, data, parcours: str) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    cat, lecons = actual_catalogue(root, data('catalogue_chapitres'), data('catalogue_lecons'))
    if lecons.empty:
        _, lecons = actual_catalogue(root, data('catalogue_chapitres'), data('source_lecons'))
    if not {'parcours_id', 'chapitre_id', 'chapitre_titre'}.issubset(cat.columns):
        cat = pd.DataFrame(columns=['parcours_id', 'chapitre_id', 'chapitre_titre', 'cours_id'])
    cat = cat.loc[cat['parcours_id'].eq(parcours)].drop_duplicates('chapitre_id').copy()
    cours = data('cours')
    ids = set(cat['cours_id'].astype(str)) if 'cours_id' in cat else set()
    if not cours.empty and 'cours_id' in cours:
        if 'parcours_id' in cours:
            cours = cours.loc[cours['parcours_id'].eq(parcours)]
        ids.update(cours['cours_id'].astype(str))
    return cat, lecons, sorted(i for i in ids if i and i.lower() != 'nan')


@st.fragment(run_every="1s")
def _controle_ollama_annulable(
    *, llm_key: str, root: Path, parcours: str, cours_id: str, needs_text: str,
    original_title: str, decision: str, model: str,
    catalogue: pd.DataFrame, lecons: pd.DataFrame,
) -> None:
    """Deux boutons réactifs, même pendant le calcul Ollama.

    Le calcul (recherche PDF incluse) est exécuté dans un processus isolé.
    Un clic sur Arrêter termine le processus client et ferme la connexion HTTP.
    """
    active_key = 'rev2_ollama_process_active'
    current = st.session_state.get(active_key)
    if current is not None and current['key'] != llm_key:
        # Empêche de rattacher les titres d'un autre groupe/chapitre au groupe courant.
        stop_job(current['process'])
        st.session_state.pop(active_key, None)
        current = None

    running = current is not None
    left, right = st.columns([3, 2], gap='small')
    with left:
        generate = st.button(
            'Proposer 1 à 5 titres avec Ollama',
            key=llm_key + '_button',
            disabled=running,
            use_container_width=True,
        )
    with right:
        cancel = st.button(
            'Arrêter la génération',
            key=llm_key + '_cancel',
            disabled=not running,
            use_container_width=True,
        )

    if cancel and current is not None:
        stop_job(current['process'])
        st.session_state.pop(active_key, None)
        st.session_state[llm_key + '_notice'] = (
            'Génération interrompue à la demande. Aucun nouveau titre ni avis enregistré.'
        )
        st.rerun()

    if generate:
        try:
            if not needs_text.strip():
                raise ValueError('Aucune lacune documentée : renseigner les besoins du groupe.')
            if not cours_id.strip():
                raise ValueError('Aucun cours destinataire renseigné.')
            worker = Path(__file__).with_name('ollama_titles_worker.py')
            # Passage de données seulement : jamais de variables ou d'écriture Streamlit depuis le worker.
            payload = {
                'root': str(root),
                'parcours': parcours,
                'cours': cours_id,
                'lacunes': needs_text,
                'titre_initial': original_title,
                'decision': decision,
                'model': model,
                'catalogue': catalogue.fillna('').to_dict('records'),
                'lecons': lecons.fillna('').to_dict('records'),
            }
            process = start_job(payload, worker)
            st.session_state[active_key] = {
                'key': llm_key,
                'process': process,
                'started': time.monotonic(),
            }
            st.session_state.pop(llm_key + '_notice', None)
            st.rerun()
        except Exception as exc:
            st.error(f'Démarrage de la génération impossible : {exc}')

    current = st.session_state.get(active_key)
    if current is not None and current['key'] == llm_key:
        proc = current['process']
        elapsed = time.monotonic() - current['started']
        if elapsed > 150:
            stop_job(proc)
            st.session_state.pop(active_key, None)
            st.session_state[llm_key + '_notice'] = (
                'Génération arrêtée après dépassement du délai maximal (150 s).'
            )
            st.rerun()
        try:
            result = completed_job(proc)
            if result is not None:
                st.session_state.pop(active_key, None)
                st.session_state[llm_key] = {
                    'titres': result['titres'], 'mode': result['mode']
                }
                st.session_state.pop(llm_key + '_selected', None)
                st.session_state[llm_key + '_notice'] = (
                    f"{len(result['titres'])} titre(s) proposé(s). "
                    'Sélectionner explicitement ceux à conserver.'
                )
                st.rerun()
        except Exception as exc:
            st.session_state.pop(active_key, None)
            st.session_state[llm_key + '_notice'] = f'Erreur de génération : {exc}'
            st.rerun()
        st.info(f'Génération en cours ({elapsed:.0f} s). Le bouton « Arrêter la génération » est actif.')

    message = st.session_state.get(llm_key + '_notice', '')
    if message:
        if message.startswith('Erreur') or message.startswith('Génération arrêtée'):
            st.warning(message)
        elif message.startswith('Génération interrompue'):
            st.info(message)
        else:
            st.success(message)


def show_page(root: Path, data) -> None:
    st.info('Validation OPÉRATIONNELLE : approuver, remplacer ou rejeter un chapitre, puis ajouter facultativement des chapitres. La page « Évaluation rapide » est distincte et doit être remplie avant de consulter les scores et de réviser les recommandations.')
    st.warning('Prototype local : identité déclarative. Vérifier réellement le rôle de l’enseignant avant la collecte définitive.')
    _u = st.session_state.get('user', {})
    if _u.get('role') != 'admin':
        st.session_state['rev2_teacher'] = _u.get('identifiant', '')
    enseignant = st.text_input('Identifiant de l’enseignant référent', key='rev2_teacher', disabled=_u.get('role') != 'admin',
                               placeholder='Identifiant attribué au référent du parcours')
    cycle = st.radio('Cycle pédagogique', ['T1', 'T0'], horizontal=True, key='rev2_cycle')
    groups = data('groupes_' + cycle.lower())
    if groups.empty or not {'ID_GROUPE', 'PARCOURS'}.issubset(groups.columns):
        st.error('Export des groupes manquant ou incomplet.')
        return
    available = sorted(set(groups['PARCOURS']) & set(PARCOURS))
    if not available:
        st.error('Aucun parcours reconnu dans les groupes.')
        return
    parcours = st.selectbox('Parcours de l’enseignant', available,
                            format_func=lambda p: f'{p} — {PARCOURS[p]}', key='rev2_parcours')
    selected_groups = groups.loc[groups['PARCOURS'].eq(parcours)].copy()
    if selected_groups.empty:
        st.info('Aucun groupe pour ce parcours.')
        return
    gid = st.selectbox('Groupe pédagogique', selected_groups['ID_GROUPE'].tolist(),
                       format_func=lambda g: f"{g} — {NIVEAUX.get(_string(selected_groups.loc[selected_groups['ID_GROUPE'].eq(g)].iloc[0].get('NIVEAU')), selected_groups.loc[selected_groups['ID_GROUPE'].eq(g)].iloc[0].get('NIVEAU',''))}",
                       key='rev2_group')
    group_row = selected_groups.loc[selected_groups['ID_GROUPE'].eq(gid)].iloc[0]
    a,b,c=st.columns(3)
    a.metric('Parcours', parcours)
    b.metric('Niveau', NIVEAUX.get(_string(group_row.get('NIVEAU')), _string(group_row.get('NIVEAU'))))
    c.metric('Effectif déclaré', _string(group_row.get('N_APPRENANTS')) or '—')
    st.subheader('1. Lacunes et besoins collectifs du groupe')
    needs, main_gap = _introduction_lacunes(data, cycle, gid, group_row)
    needs_text = '; '.join(str(x['COMPETENCE']) for x in needs if x['COMPETENCE']) or main_gap

    candidates = data('chapitres_' + cycle.lower())
    subset = candidates.loc[candidates['ID_GROUPE'].eq(gid)].copy() if not candidates.empty and 'ID_GROUPE' in candidates else pd.DataFrame()
    if not subset.empty:
        if 'RANG' in subset:
            subset['_rank'] = pd.to_numeric(subset['RANG'], errors='coerce')
            subset = subset.sort_values('_rank')
        labels = list(range(len(subset)))
        position = st.selectbox('Chapitre initial à examiner', labels,
                                format_func=lambda i: f"{subset.iloc[i].get('CHAPITRE', '')} — {subset.iloc[i].get('ID_CHAPITRE', '')}",
                                key=f'rev2_initial_{cycle}_{gid}')
        initial = subset.iloc[position]
        initial_id = _string(initial.get('ID_CHAPITRE'))
        original_title = _string(initial.get('CHAPITRE'))
        default_course = _string(initial.get('COURS_ID'))
        st.write('**Compétences que ce chapitre est censé couvrir :**',
                 _string(initial.get('COMPETENCES_CIBLEES')) or 'Non renseignées')
        st.caption('À distinguer des lacunes réellement observées ci-dessus. Les correspondances automatiques restent à valider.')
        pdf = safe_pdf(root, _string(initial.get('CHEMIN_PDF')))
        if pdf:
            with open(pdf, 'rb') as handle:
                st.download_button('Consulter le PDF du cours', handle.read(), file_name=pdf.name,
                                   mime='application/pdf', key=f'rev2_pdf_{cycle}_{gid}_{initial_id}')
        else:
            st.caption('PDF absent : vérifier la pertinence des métadonnées sans conclure à la qualité du contenu.')
        decisions = ['VALIDE', 'REMPLACE', 'REJETE']
    else:
        st.warning('Aucun chapitre candidat pour ce groupe. L’absence de proposition n’est pas une absence de lacune.')
        initial_id, original_title, default_course = '', '', ''
        decisions = ['AUCUNE_PROPOSITION']

    st.subheader('2. Décision sur le chapitre initial')
    decision = st.selectbox('Décision pédagogique', decisions, key=f'rev2_action_{cycle}_{gid}_{initial_id}',
                            format_func=lambda x: {
                                'VALIDE':'VALIDER — conserver le chapitre initial',
                                'REMPLACE':'REMPLACER — substituer un ou plusieurs chapitres',
                                'REJETE':'REJETER — exclure le chapitre initial',
                                'AUCUNE_PROPOSITION':'AUCUN CANDIDAT — proposer si nécessaire',
                            }[x])
    st.caption('Quel que soit le choix, l’enseignant peut ajouter plusieurs chapitres complémentaires.')
    st.caption('La note scientifique de pertinence (1 à 5) se saisit exclusivement dans la page « Évaluation rapide », avant toute révision opérationnelle.')
    catalogue, lecons, cours_ids = _catalogue_et_cours(root, data, parcours)
    candidate_existing = catalogue.loc[~catalogue['chapitre_id'].astype(str).eq(initial_id)]
    choices = list(candidate_existing['chapitre_id'].astype(str))
    title_by_id = dict(zip(candidate_existing['chapitre_id'].astype(str), candidate_existing['chapitre_titre'].astype(str)))
    if decision == 'REMPLACE':
        st.subheader('3. Sélectionner plusieurs chapitres de remplacement')
        selection_label = 'Chapitres existants à utiliser À LA PLACE du chapitre initial'
    else:
        st.subheader('3. Ajouter éventuellement plusieurs chapitres')
        selection_label = 'Chapitres existants à ajouter (facultatif)'
    selected_existing = st.multiselect(selection_label, choices,
                                       format_func=lambda cid: f'{cid} — {title_by_id.get(cid,cid)}',
                                       key=f'rev2_existing_{cycle}_{gid}_{initial_id}')
    if decision == 'REJETE':
        st.caption('Un rejet sans ajout reste possible. Propose des alternatives seulement si la lacune reste à couvrir.')
    if not cours_ids and (default_course and default_course != 'nan'):
        cours_ids=[default_course]
    if cours_ids:
        cours_id=st.selectbox('Cours destinataire des nouveaux titres éventuels', cours_ids,
                              index=cours_ids.index(default_course) if default_course in cours_ids else 0,
                              key=f'rev2_course_{cycle}_{gid}_{initial_id}')
    else:
        cours_id = default_course
        st.warning('Aucun cours du parcours disponible : un titre nouveau ne pourra pas être enregistré avant correction du catalogue.')
    free_titles = st.text_area('Autres nouveaux TITRES proposés par l’enseignant (un par ligne)',
                               key=f'rev2_manual_titles_{cycle}_{gid}_{initial_id}',
                               placeholder='Fusion de requêtes Power Query\nGestion des jointures')
    st.caption('Ces titres sont des propositions de plan ; ils ne signifient pas qu’un contenu existe déjà.')

    st.subheader('4. Assistance facultative Ollama / RAG')
    model = st.text_input('Modèle Ollama local', value=os.getenv('OLLAMA_MODEL', 'qwen2.5:3b'),
                          key='rev2_ollama_model')
    llm_key = f'rev2_llm_{cycle}_{gid}_{initial_id}_{cours_id}_{decision}'
    _controle_ollama_annulable(
        llm_key=llm_key, root=root, parcours=parcours, cours_id=cours_id,
        needs_text=needs_text, original_title=original_title, decision=decision,
        model=model, catalogue=catalogue, lecons=lecons,
    )
    llm_state = st.session_state.get(llm_key, {})
    llm_titles=llm_state.get('titres', [])
    chosen_llm = st.multiselect('Titres suggérés par Ollama à RETENIR', llm_titles,
                                key=llm_key+'_selected') if llm_titles else []
    if llm_titles:
        st.caption('Origine : ' + llm_state.get('mode','LLM_SANS_RAG') + '. Une proposition de titre n’est pas un contenu validé.')
    new_titles = [line.strip() for line in free_titles.splitlines() if line.strip()] + chosen_llm
    approve_titles = st.checkbox('J’approuve ces nouveaux titres comme plan pédagogique (PAS leurs contenus)',
                                  value=False,key=f'rev2_title_approve_{cycle}_{gid}_{initial_id}',
                                  disabled=not new_titles)
    reason = st.text_area('Justification pédagogique / explication des choix',
                          key=f'rev2_why_{cycle}_{gid}_{initial_id}',
                          placeholder='Décrire l’adéquation aux lacunes et aux prérequis...')
    if not enseignant.strip():
        st.warning('Avant d’enregistrer : renseigner « Identifiant de l’enseignant référent (réel) » tout en haut de cette page. Le groupe est déjà sélectionné.')
    if st.button('Enregistrer la décision et les chapitres retenus',type='primary',
                 key=f'rev2_save_{cycle}_{gid}_{initial_id}'):
        try:
            ref = save_decision(
                root,etape=cycle,groupe_id=gid,parcours=parcours,
                chapitre_initial_id=initial_id,chapitre_initial_titre=original_title,
                cours_id=cours_id,decision=decision,enseignant_id=enseignant,
                justification=reason,chapitres_existants=selected_existing,
                nouveaux_titres=new_titles,titres_approuves=bool(approve_titles),
                lacunes=needs,catalogue=catalogue,
                source_suggestion=llm_state.get('mode','AUCUNE') if chosen_llm else 'TITRES_MANUELS_OU_AUCUN',
                modele=model if chosen_llm else '',
            )
            st.success('Décision pédagogique enregistrée : '+ref+'.')
            if new_titles and not approve_titles:
                st.warning('Les titres nouveaux sont EN ATTENTE de validation du plan pédagogique.')
        except Exception as exc:
            st.error(str(exc))

    st.divider()
    st.subheader('5. Décisions et génération de brouillons après approbation des titres')
    history = read_decisions(root)
    _p = st.session_state.get('user', {})
    if _p.get('role') != 'admin' and not history.empty:
        history = history[history['parcours'].eq(_p.get('parcours', ''))]
    same_group=history.loc[(history['etape'].eq(cycle)) & (history['groupe_id'].eq(gid))] if not history.empty else history
    if not same_group.empty:
        latest=same_group.drop_duplicates(['etape','groupe_id','chapitre_initial_id'],keep='last')
        with st.expander('Historique des décisions (recommandations initiales conservées)',expanded=False):
            st.dataframe(same_group[['date_utc','enseignant_id','decision','chapitre_initial_titre','justification']].iloc[::-1],
                         use_container_width=True,hide_index=True)
            st.download_button('Exporter toutes les décisions pédagogiques (CSV)',
                               history.to_csv(index=False).encode('utf-8-sig'),
                               file_name='decisions_chapitres_v2.csv',mime='text/csv')
        available_for_generation=[]
        for _, rr in latest.iterrows():
            for title in approved_titles_for_decision(rr.to_dict()):
                available_for_generation.append((rr['id'],title,rr['cours_id'],rr['enseignant_id']))
        if available_for_generation:
            st.write('**Titres nouveaux approuvés comme plan pédagogique :**')
            pick=st.selectbox('Titre pour générer un BROUILLON de chapitre',
                              list(range(len(available_for_generation))),
                              format_func=lambda i: available_for_generation[i][1],
                              key=f'rev2_pick_content_{cycle}_{gid}')
            entry=available_for_generation[pick]
            if st.button('Générer le contenu de ce chapitre (brouillon à revalider)',
                         key=f'rev2_generate_content_{cycle}_{gid}'):
                try:
                    if not enseignant.strip():
                        raise ValueError('Identifiant enseignant obligatoire.')
                    if not entry[2]:
                        raise ValueError('Cours destinataire manquant.')
                    if not needs_text.strip():
                        raise ValueError('Besoins du groupe non documentés.')
                    with st.spinner('Génération de brouillon avec Ollama...'):
                        context=chercher_contexte(root,needs_text,parcours,entry[2],catalogue,lecons)
                        doc=generer_avec_ollama(
                            'CHAPITRE',parcours,entry[2],'',
                            'Titre de chapitre approuvé à respecter : '+entry[1]+'. Lacunes : '+needs_text,
                            context,model)
                        # Le titre définitif vient du plan approuvé ; le corps généré reste un brouillon.
                        doc['titre']=entry[1]
                        origin='RAG_LLM_PDF' if context.get('n_pdf',0)>0 else 'LLM_SANS_RAG'
                        ident=creer_proposition(root,'CHAPITRE',parcours,entry[2],'',cycle,gid,
                                               needs_text,doc,context,model,origin)
                    st.success(f'Brouillon {ident} créé. Validation du CONTENU à effectuer dans « Propositions IA — chapitres et leçons ».')
                except Exception as exc:
                    st.error(f'Génération impossible : {exc}')
    else:
        st.info('Aucune décision sauvegardée pour ce groupe.')
    st.caption('Les sélections existantes sont des décisions pédagogiques de groupe ; les nouveaux contenus ne sont publiés qu’après approbation dans « Propositions IA ». H5 reste une expérience distincte.')
