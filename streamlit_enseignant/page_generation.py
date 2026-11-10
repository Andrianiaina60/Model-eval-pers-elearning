"""Page Streamlit : détection de couverture, proposition chapitre/leçon, revue HITL."""
from __future__ import annotations
import json
import os
from pathlib import Path
import hmac
import pandas as pd
import streamlit as st
from generation_pedagogique import (
    actual_catalogue, chercher_contexte, creer_proposition, exporter_catalogue_valide,
    gap_assessment, generer_avec_ollama, lister_propositions,
    reviser_proposition, validate_content,
)


def _vd()->str:
    u=st.session_state.get('user',{});return '' if u.get('role')=='admin' else u.get('identifiant','')


def _vl()->bool:
    return st.session_state.get('user',{}).get('role')!='admin'


def _teacher_access()->bool:
    secret=os.environ.get('TEACHER_REVIEW_PASSWORD','')
    if not secret:
        st.error('Configurer TEACHER_REVIEW_PASSWORD pour activer les décisions pédagogiques. Mode sécurisé désactivé.')
        return False
    if st.session_state.get('_teacher_access'):
        return True
    with st.form('access_form_rag'):
        pwd=st.text_input('Mot de passe de revue pédagogique (prototype local)',type='password')
        ok=st.form_submit_button('Déverrouiller la revue')
    if ok and hmac.compare_digest(pwd,secret):
        st.session_state['_teacher_access']=True
        st.rerun()
    elif ok:
        st.error('Mot de passe invalide.')
    return False


def _catalogues(root:Path, get_data):
    a=get_data('catalogue_chapitres')
    b=get_data('catalogue_lecons')
    if b.empty:b=get_data('source_lecons')
    a,b=actual_catalogue(root,a,b)
    for col in ('parcours_id','cours_id','chapitre_id','chapitre_titre','chemin_pdf'):
        if col not in a:a[col]=''
    for col in ('chapter_id','lesson_title','learning_objectives','keywords'):
        if col not in b:b[col]=''
    return a.fillna(''),b.fillna('')


def show_page(root:Path,get_data,filter_group,group_details):
    st.info('Le système propose un NOUVEAU chapitre ou une leçon seulement lorsque la couverture du besoin doit être complétée. Tout contenu demeure un BROUILLON jusqu’à approbation enseignante.')
    if not _teacher_access():return
    a,b=st.tabs(['Détecter et préparer une proposition','Revue enseignante et publication'])
    with a:
        cycle=st.radio('Moment pédagogique',['T0','T1'],horizontal=True,key='gen_cycle')
        _,gid=filter_group(cycle)
        if gid is None:
            st.warning('Aucun groupe disponible dans les exports. Vérifier les sorties du notebook 05.')
        else:
            group_details(cycle,gid)
            groups=get_data('groupes_'+cycle.lower())
            row=groups.loc[groups['ID_GROUPE']==gid].iloc[0]
            parcours=str(row.get('PARCOURS',''))
            if parcours not in ('DA','BI','DS','IA'):
                st.error('Parcours non reconnu : génération impossible.');return
            catalogue,lecons=_catalogues(root,get_data)
            course_catalog=get_data('cours')
            course_ids=set(catalogue.loc[catalogue['parcours_id']==parcours,'cours_id'].astype(str))
            if not course_catalog.empty and 'cours_id' in course_catalog.columns:
                cc=course_catalog.copy()
                if 'parcours_id' in cc:cc=cc[cc['parcours_id']==parcours]
                course_ids.update(str(x) for x in cc['cours_id'].tolist())
            course_ids=sorted(x for x in course_ids if x and x.lower()!='nan')
            st.subheader('1. Analyser le besoin non couvert')
            lacune=st.text_area('Compétences/lacunes documentées',value=str(row.get('LACUNE_PRINCIPALE','')).strip(),
                                key=f'gen_lacune_{cycle}_{gid}',height=80)
            if not course_ids:
                st.error('Aucun cours référencé pour ce parcours : compléter d’abord le catalogue des cours.')
                return
            cours=st.selectbox('Cours destinataire',course_ids,key='gen_cours')
            nature=st.radio('À proposer',['CHAPITRE','LECON'],horizontal=True,
                            format_func=lambda x:'Nouveau chapitre avec leçons' if x=='CHAPITRE' else 'Nouvelle leçon dans un chapitre existant')
            target=''
            if nature=='LECON':
                possible=catalogue.loc[(catalogue['parcours_id']==parcours)&(catalogue['cours_id']==cours)]
                if possible.empty:
                    st.error('Aucun chapitre existant dans ce cours ; proposer un nouveau chapitre plutôt qu’une leçon isolée.')
                    return
                target=st.selectbox('Chapitre parent',possible['chapitre_id'].tolist(),
                                    format_func=lambda x:f"{x} — {possible.loc[possible['chapitre_id']==x,'chapitre_titre'].iloc[0]}")
            seuil=st.slider('Seuil exploratoire de similarité lexicale (pas une mesure de pertinence)',0.05,0.6,0.2,0.05)
            audit=gap_assessment(lacune,parcours,catalogue,lecons,seuil)
            c1,c2=st.columns(2)
            c1.metric('Similarité lexicale maximale',f"{audit['score_max']:.3f}" if audit['score_max'] is not None else '—')
            c2.metric('Signal de couverture',audit['statut'])
            if audit.get('chapitre_proche'):
                st.caption('Chapitre le plus proche : '+audit['chapitre_proche'])
            st.warning('La similarité lexicale ne prouve PAS l’absence de couverture pédagogique. Examiner les ressources avant de créer un doublon.')
            confirmer_besoin=st.checkbox('J’ai vérifié que la lacune justifie une proposition complémentaire, sans créer de doublon.',key='gen_confirmer_besoin')
            contexte=chercher_contexte(root,lacune,parcours,cours,catalogue,lecons)
            st.write('**Provenance documentaire :**',contexte['statut'])
            st.caption(f"{len(contexte['elements'])} extrait(s) utiles ; {contexte['n_pdf']} passage(s) issus de PDF.")
            if contexte['statut']!='RAG_PDF':
                st.warning('Aucun passage PDF pertinent récupéré : la génération éventuelle sera étiquetée LLM_SANS_RAG. Elle ne doit pas être qualifiée de RAG documenté.')
            with st.expander('Voir les sources récupérées'):
                for e in contexte['elements']:
                    st.write(f"**{e['ref']}** — {e['source']} (page {e['page'] or 'métadonnées'})")
                    st.caption(e['texte'][:800])
            st.subheader('2. Construire un brouillon non validé')
            modele=st.text_input('Modèle Ollama installé',value=os.getenv('OLLAMA_MODEL',''),placeholder='ex. qwen2.5:3b')
            b1,b2=st.columns(2)
            with b1:
                generate=st.button('Générer un brouillon avec Ollama',disabled=not confirmer_besoin or not lacune.strip())
            with b2:
                manual=st.button('Préparer un brouillon manuel',disabled=not confirmer_besoin or not lacune.strip())
            key=f'generated_{cycle}_{gid}_{nature}_{cours}_{target}'
            if generate:
                try:
                    doc=generer_avec_ollama(nature,parcours,cours,target,lacune,contexte,modele)
                    st.session_state[key]={'contenu':doc,'origine':('RAG_LLM_PDF' if any(ref.startswith('PDF_') for ref in doc.get('references',[])) else 'LLM_SANS_RAG'), 'modele':modele}
                    st.success('Brouillon produit. Aucun avis ni publication automatique.')
                except Exception as exc:
                    st.error(f'Génération impossible : {exc}. Vérifier Ollama et le modèle, ou préparer un brouillon manuel.')
            if manual:
                # Squelette à compléter avant soumission ; pas de faux contenu d’apprentissage.
                st.session_state[key]={'contenu':{'titre':'','objectif':'','contenu':'','mots_cles':'','references':[],
                       'lecons':[{'titre':'','objectif':'','contenu':'','mots_cles':''}] if nature=='CHAPITRE' else []},
                       'origine':'REDACTION_MANUELLE','modele':''}
            if key in st.session_state:
                entry=st.session_state[key]
                edited=st.text_area('Contenu du brouillon (JSON éditable avant soumission)',
                                    value=json.dumps(entry['contenu'],ensure_ascii=False,indent=2),height=360,key=key+'_editor')
                if st.button('Soumettre le brouillon à la validation enseignante',key=key+'_submit'):
                    if not confirmer_besoin:st.error('Confirmer la nécessité pédagogique.');return
                    try:
                        body=json.loads(edited)
                        ident=creer_proposition(root,nature,parcours,cours,target,cycle,gid,lacune,body,
                                 contexte,entry['modele'],entry['origine'])
                        del st.session_state[key]
                        st.success(f'Brouillon enregistré : {ident}. Statut EN_ATTENTE. Publication interdite sans avis.')
                    except Exception as exc:
                        st.error(f'Brouillon non enregistré : {exc}')
    with b:
        propositions=lister_propositions(root)
        _u=st.session_state.get('user',{})
        if _u.get('role')!='admin':
            propositions=[p for p in propositions if p['parcours']==_u.get('parcours')]
        attente=[p for p in propositions if p['statut']=='EN_ATTENTE']
        c1,c2,c3=st.columns(3)
        c1.metric('En attente',len(attente))
        c2.metric('Approuvés',sum(p['statut']=='APPROUVE' for p in propositions))
        c3.metric('Rejetés / à corriger',sum(p['statut'] in ('REJETE','A_CORRIGER') for p in propositions))
        if not attente:
            st.info('Aucun nouveau brouillon en attente de validation.')
        else:
            ids=[p['id'] for p in attente]
            selected=st.selectbox('Brouillon à examiner',ids,
                                  format_func=lambda x:next(f"{p['nature']} — {p['donnees']['titre']} ({p['groupe_id']})" for p in attente if p['id']==x))
            p=next(p for p in attente if p['id']==selected)
            st.write(f"**Parcours :** {p['parcours']}  · **Cours :** {p['cours_id']}  · **Groupe :** {p['groupe_id']}")
            st.write('**Besoin :**',p['lacune'])
            st.write('**Origine :**',p['type_generation'],' · **Modèle :**',p['modele'] or 'Rédaction manuelle')
            st.caption('Un contenu généré peut contenir des erreurs ; vérifier les objectifs, les notions, les exemples, les prérequis et les sources.')
            with st.expander('Provenance des extraits'):
                for e in p['sources'].get('elements',[]):st.write(e['ref'], '—',e['source'], '(p.',e['page'],')')
            with st.form('review_generated_'+p['id']):
                contenu=st.text_area('Réviser le chapitre/la leçon (JSON)',
                       value=json.dumps(p['donnees'],indent=2,ensure_ascii=False),height=360)
                decision=st.selectbox('Décision',['APPROUVE','A_CORRIGER','REJETE'])
                evaluateur=st.text_input('Identifiant de l’enseignant',value=_vd(),disabled=_vl())
                commentaire=st.text_area('Justification pédagogique et vérification des prérequis (obligatoire)')
                confirme=st.checkbox('Je confirme avoir vérifié l’exactitude, les sources, le niveau, les prérequis et la cohérence pédagogique.')
                submit=st.form_submit_button('Enregistrer cette décision')
            if submit:
                try:
                    reviser_proposition(root,p['id'],decision,evaluateur,commentaire,
                                       json.loads(contenu),confirme,p['version'])
                    st.success('Décision sauvegardée avec journal ; seul APPROUVE est exporté dans le catalogue complémentaire.')
                    st.rerun()
                except Exception as exc:
                    st.error(f'Décision non enregistrée : {exc}')
        st.divider()
        st.subheader('Catalogue complémentaire approuvé')
        if st.button('Reconstruire les exports à partir des décisions approuvées'):
            st.success(str(exporter_catalogue_valide(root)))
        approved=[p for p in propositions if p['statut']=='APPROUVE']
        if approved:
            st.dataframe(pd.DataFrame([{'Proposition':p['id'],'Nature':p['nature'],'Titre':p['donnees']['titre'],
                                      'Groupe':p['groupe_id'],'Validateur déclaré':p['evaluateur'],'Date':p['valide_le']} for p in approved]),
                         use_container_width=True,hide_index=True)
        st.caption('Le secret partagé protège ce prototype, mais ne constitue pas une authentification nominative. Pour une étude H4/H5 ou la production : intégrer des comptes enseignants vérifiés.')
