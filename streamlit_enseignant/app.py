"""Adaptive e-Learning — interface de démonstration et revue de résultats 00–06.

Lancement: streamlit run app.py
Ne relance ni notebook, ni entraînement, ni embeddings.
"""
from __future__ import annotations
import os
from pathlib import Path
import pandas as pd
import streamlit as st
from data_access import PATHS, REQUIRED, project_root, read_csv, read_json, diagnostics, safe_pdf, chapter_file_guard
from decision_store import read_state, save_record, utcnow
from page_generation import show_page
from validation_rapide_h5 import read_reviews, show_page as show_h5_fast_review
from page_validation_chapitres import show_page as show_chapter_validation
from decision_chapitres_v2 import read_decisions
from generation_pedagogique import actual_catalogue
from auth import require_login, logout_button, current_user, validator_default, validator_locked, my_parcours, is_admin

st.set_page_config(page_title='Adaptive e-Learning — Master Recherche', page_icon='📘',layout='wide',initial_sidebar_state='expanded')
ROOT=project_root(Path(__file__).resolve().parent)
require_login(ROOT)

LABELS={'DA':'Data Analysis','BI':'Business Intelligence','DS':'Data Science','IA':'Intelligence Artificielle'}
LEVELS={'Debutant':'Débutant','Intermediaire':'Intermédiaire','Avance':'Avancé'}
PAGES=['Tableau de bord','Diagnostic et scoring','Orientation des parcours','Groupes et critères','Performance et XAI','Chapitres recommandés','Propositions IA — chapitres et leçons','Validation enseignante','Évaluation rapide','Catalogue pédagogique','Contrôles et traçabilité']

@st.cache_data(ttl=45,show_spinner=False)
def load_data(root_str:str,name:str)->pd.DataFrame:
    return read_csv(Path(root_str),name)

ADMIN_ONLY_PAGES={'Performance et XAI','Contrôles et traçabilité'}


def _ids(name:str,col:str,p:str,by:str)->set:
    df=load_data(str(ROOT),name)
    return set(df.loc[df[by].eq(p),col]) if not df.empty and {col,by}.issubset(df.columns) else set()


def my_learners(p:str)->set:
    return _ids('recommandation_auto','_ID_NORM',p,'PARCOURS_AUTO')


def my_groups(p:str)->set:
    return _ids('groupes_t0','ID_GROUPE',p,'PARCOURS')|_ids('groupes_t1','ID_GROUPE',p,'PARCOURS')


def scope_state(df:pd.DataFrame,col:str,values:set)->pd.DataFrame:
    return df if df.empty or col not in df.columns else df[df[col].isin(values)]


def scope_df(name:str,df:pd.DataFrame,p:str)->pd.DataFrame:
    """Vue enseignant : seulement les lignes de son parcours."""
    if df.empty:return df
    if name in ('diagnostic_t0','recommandation_auto','recommandation_finale_experimentale'):
        return scope_state(df,'_ID_NORM',my_learners(p))
    if name=='t1':return df[df['PARCOURS_T1'].eq(p)] if 'PARCOURS_T1' in df.columns else df
    if name in ('groupes_t0','groupes_t1','chapitres_t0','chapitres_t1','couverture_t1'):
        return df[df['PARCOURS'].eq(p)] if 'PARCOURS' in df.columns else scope_state(df,'ID_GROUPE',my_groups(p))
    if name in ('base_groupes_t1','besoins_t0_t1'):return scope_state(df,'ID_GROUPE',my_groups(p))
    if name in ('catalogue_chapitres','cours'):
        return df[df['parcours_id'].eq(p)] if 'parcours_id' in df.columns else df
    if name in ('catalogue_lecons','source_lecons') and 'chapter_id' in df.columns:
        cat=load_data(str(ROOT),'catalogue_chapitres')
        ok=set(cat.loc[cat['parcours_id'].eq(p),'chapitre_id']) if not cat.empty else set()
        return df[df['chapter_id'].isin(ok)]
    return df


def data(name:str)->pd.DataFrame:
    df=load_data(str(ROOT),name);p=my_parcours()
    return df if p is None else scope_df(name,df,p)

def safe_col(df:pd.DataFrame,columns:list[str])->list[str]:
    return [col for col in columns if col in df.columns]

def nonempty(x)->bool:
    return str(x).strip() not in {'','nan','None','<NA>'}

def numeric(x):
    try:return float(str(x).replace(',','.'))
    except (TypeError,ValueError):return None

def present(df:pd.DataFrame,preferred:list[str],limit:int=400):
    if df.empty:
        st.info('Aucune ligne disponible.');return
    cols=safe_col(df,preferred)
    st.dataframe(df[cols] if cols else df, use_container_width=True,hide_index=True,height=min(560,45+36*min(len(df),limit)))

def filter_group(phase:str):
    groups=data('groupes_'+phase.lower())
    if groups.empty:return groups,None
    available=sorted(groups['PARCOURS'].unique())
    path=st.selectbox('Parcours',available,format_func=lambda x:f'{x} — {LABELS.get(x,x)}',key=f'{phase}_parcours')
    groups=groups[groups['PARCOURS']==path]
    levels=list(dict.fromkeys(groups['NIVEAU'].tolist()))
    lev=st.selectbox('Niveau',levels,format_func=lambda x:LEVELS.get(x,x),key=f'{phase}_niveau')
    groups=groups[groups['NIVEAU']==lev]
    options=groups['ID_GROUPE'].tolist()
    if not options:return groups,None
    group=st.selectbox('Groupe',options,key=f'{phase}_group')
    return groups,group

def group_details(phase:str,gid:str):
    groups=data('groupes_'+phase.lower())
    matching=groups.loc[groups['ID_GROUPE']==gid]
    if matching.empty:return
    row=matching.iloc[0]
    a,b,c=st.columns(3)
    a.metric('Parcours',row.get('PARCOURS','—'))
    b.metric('Niveau du groupe',LEVELS.get(row.get('NIVEAU',''),row.get('NIVEAU','—')))
    c.metric('Effectif déclaré',str(row.get('N_APPRENANTS','—')))
    st.write('**Lacunes collectives :**',row.get('LACUNE_PRINCIPALE','Non renseignées') or 'Aucune lacune ciblée')
    for field,label in [('SOURCE_LACUNES','Source des lacunes'),('OBJECTIFS_DOMINANTS','Objectifs dominants'),
                        ('PREREQUIS_LIMITANT','Prérequis limitants (proposés)'),('EXPLICATION','Explication du regroupement'),
                        ('TYPE_ACCOMPAGNEMENT','Accompagnement proposé'),('STATUT_GROUPE','Statut du groupe')]:
        value=str(row.get(field,'')).strip()
        if value and value.lower()!='nan':
            st.write(f'**{label} :** {value}')
    needs=data('besoins_t0_t1')
    if not needs.empty and {'ETAPE','ID_GROUPE'}.issubset(needs.columns):
        needs=needs[needs['ETAPE'].eq(phase)&needs['ID_GROUPE'].eq(gid)]
        if not needs.empty:
            with st.expander('Compétences et poids utilisés pour ce groupe'):
                present(needs,['COMPETENCE','POIDS','PROVENANCE'])
    if 'STATUT_NIVEAU' in row and nonempty(row['STATUT_NIVEAU']):
        st.caption('Statut du niveau : '+row['STATUT_NIVEAU'])
    if phase=='T0':
        st.warning('À T0 : groupes de préparation pédagogique, basés sur des parcours provisoires. Ils ne prouvent ni validation enseignante ni choix final de l’apprenant.')
    else:
        st.info('À T1 : segmentation exploratoire rétrospective, fondée sur des prédictions T2 hors pli (OOF). Ne pas la présenter comme un déploiement prospectif validé.')

def chapter_display(df:pd.DataFrame,include_review:bool=False):
    if df.empty:
        st.info('Aucune proposition de chapitre pour ce groupe. Cela peut provenir de l’absence de lacune ciblée ou du filtre du moteur hybride.')
        return
    order=df.copy()
    order['_rank']=pd.to_numeric(order['RANG'],errors='coerce')
    order=order.sort_values('_rank')
    recorded=read_state(ROOT,'avis_chapitres')
    revised=read_decisions(ROOT,only_last=True)
    for _,row in order.iterrows():
        gid=row['ID_GROUPE']; phase=row['ETAPE'];cid=row['ID_CHAPITRE']
        titre=str(row.get('CHAPITRE',cid))
        rang=row.get('RANG','?')
        header=f'#{rang} · {titre} ({cid})'
        with st.expander(header,expanded=str(rang)=='1'):
            st.write('**Cours :**',row.get('COURS_TITRE','—'),f"({row.get('COURS_ID','')})")
            st.write('**Compétences ciblées :**',row.get('COMPETENCES_CIBLEES','—'))
            score=numeric(row.get('SCORE_RRF_AGREGE',''))
            if score is not None:
                st.metric('Score de fusion RRF agrégé', f'{score:.6f}')
                st.caption('Score de classement (TF-IDF + embeddings) ; il ne représente pas une probabilité de pertinence.')
            else:
                st.caption('Score hybride non disponible dans cet export.')
            st.caption('Statut de la proposition : '+row.get('STATUT','CANDIDAT_HYBRIDE_NON_VALIDE'))
            st.caption('Prérequis : '+row.get('STATUT_PREREQUIS','Non renseignés'))
            if row.get('CORRESPONDANCE_EXPERTE','')!='AU_MOINS_UN_MAPPING_VALIDE':
                st.caption('Correspondances compétence–chapitre : à faire vérifier.')
            nl=LEVELS.get(row.get('NIVEAU',''),row.get('NIVEAU',''))
            nc=LEVELS.get(row.get('NIVEAU_COURS',''),row.get('NIVEAU_COURS',''))
            vals=['Debutant','Intermediaire','Avance']
            if row.get('NIVEAU','') in vals and row.get('NIVEAU_COURS','') in vals and vals.index(row['NIVEAU_COURS'])>vals.index(row['NIVEAU']):
                st.warning(f'Vérification pédagogique requise : groupe {nl}, chapitre dans un cours {nc}.')
            pdf=safe_pdf(ROOT,row.get('CHEMIN_PDF',''))
            if pdf:
                with open(pdf,'rb') as f:
                    st.download_button('Consulter / télécharger le PDF du cours',data=f.read(),file_name=pdf.name,mime='application/pdf',key=f'pdf_{phase}_{gid}_{cid}')
            else:
                st.caption('PDF non résolu localement à partir du chemin exporté. Le chapitre reste consultable.')
            selected=recorded[(recorded['ETAPE']==phase)&(recorded['ID_GROUPE']==gid)&(recorded['ID_CHAPITRE']==cid)]
            if not selected.empty:
                prev=selected.iloc[-1]
                valeur = prev.get('NOTE_PERTINENCE','')
                note_txt = f' — pertinence {valeur}/5' if str(valeur) else ''
                st.info(f"Avis saisi dans l'application : {prev['DECISION_ENSEIGNANT']}{note_txt} — {prev['VALIDATEUR']} ({prev['DATE_VALIDATION']}). Distinct de l'export expérimental.")
            if not revised.empty:
                later=revised.loc[(revised['etape'].eq(phase)) & (revised['groupe_id'].eq(gid)) &
                                  (revised['chapitre_initial_id'].eq(cid))]
                if not later.empty:
                    last=later.iloc[-1]
                    st.info('Décision pédagogique enregistrée : '+last['decision']+' — '+last['enseignant_id']+
                            ' (recommandation automatique historique conservée).')



def dashboard_validation_stats(chapitres_t0: pd.DataFrame, chapitres_t1: pd.DataFrame,
                               history_v2: pd.DataFrame, reviews_h5: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Calcule les couvertures sans compter les révisions d'un même chapitre deux fois.

    Une proposition = (PARCOURS, ETAPE, ID_GROUPE, ID_CHAPITRE).
    H5 mesure les jugements de pertinence, V2 les décisions opérationnelles.
    AUCUNE_PROPOSITION est un avis sur un groupe sans candidat, pas un chapitre validé.
    """
    cols = ['PARCOURS', 'ETAPE', 'ID_GROUPE', 'ID_CHAPITRE']
    frames = []
    for df in (chapitres_t0, chapitres_t1):
        if not df.empty and set(cols).issubset(df.columns):
            frames.append(df[cols].astype(str))
    pool = (pd.concat(frames, ignore_index=True).drop_duplicates(cols)
            if frames else pd.DataFrame(columns=cols))

    v2 = history_v2.copy()
    v2_cols = ['parcours', 'etape', 'groupe_id', 'chapitre_initial_id']
    if v2.empty or not set(v2_cols + ['decision']).issubset(v2.columns):
        v2 = pd.DataFrame(columns=v2_cols + ['decision'])
    else:
        # read_decisions() fournit l'ordre chronologique (date_utc, rowid).
        # Conserver le dernier événement, sans effacer le journal historique.
        v2 = v2.drop_duplicates(v2_cols, keep='last').copy()
    no_candidate = v2[v2['decision'].eq('AUCUNE_PROPOSITION')].copy()
    active_v2 = v2[~v2['decision'].eq('AUCUNE_PROPOSITION')].copy()
    active_v2 = active_v2[active_v2['chapitre_initial_id'].astype(str).str.strip().ne('')]
    mapping = dict(zip(v2_cols, cols))
    active_v2 = active_v2.rename(columns=mapping)
    if not active_v2.empty:
        active_v2 = active_v2.assign(**{c: active_v2[c].astype(str) for c in cols})

    h5_cols = cols + ['NOTE_PERTINENCE_1_5']
    if reviews_h5.empty or not set(h5_cols).issubset(reviews_h5.columns):
        h5 = pd.DataFrame(columns=cols)
    else:
        h5 = reviews_h5[reviews_h5['NOTE_PERTINENCE_1_5'].astype(str).isin(['1', '2', '3', '4', '5'])]
        h5 = h5[cols].astype(str).drop_duplicates(cols)

    if not pool.empty:
        v2_for_pool = pool.merge(active_v2[cols + ['decision']], on=cols, how='inner', validate='one_to_one')
        h5_for_pool = pool.merge(h5, on=cols, how='inner', validate='one_to_one')
    else:
        v2_for_pool = pd.DataFrame(columns=cols + ['decision'])
        h5_for_pool = pd.DataFrame(columns=cols)

    table = []
    for parcours in ('DA', 'BI', 'DS', 'IA'):
        for cycle in ('T0', 'T1'):
            mask = pool['PARCOURS'].eq(parcours) & pool['ETAPE'].eq(cycle)
            m_v2 = v2_for_pool['PARCOURS'].eq(parcours) & v2_for_pool['ETAPE'].eq(cycle)
            m_h5 = h5_for_pool['PARCOURS'].eq(parcours) & h5_for_pool['ETAPE'].eq(cycle)
            items = v2_for_pool.loc[m_v2, 'decision']
            proposed = int(mask.sum())
            reviewed = int(m_v2.sum())
            table.append({
                'Parcours': parcours, 'Cycle': cycle, 'Propositions': proposed,
                'Évaluations': int(m_h5.sum()),
                'Décisions pédagogiques': reviewed,
                'Validés': int(items.eq('VALIDE').sum()),
                'Remplacés': int(items.eq('REMPLACE').sum()),
                'Rejetés': int(items.eq('REJETE').sum()),
                'Restants': proposed - reviewed,
            })
    stats = {
        'propositions': len(pool),
        'h5_couvertes': len(h5_for_pool),
        'h5_lignes': len(reviews_h5),
        'v2_couvertes': len(v2_for_pool),
        'v2_evenements': len(history_v2),
        'v2_restant': len(pool) - len(v2_for_pool),
        'sans_candidat_documentes': len(no_candidate),
        'v2_hors_pool': len(active_v2) - len(v2_for_pool),
    }
    return pd.DataFrame(table), stats

def apply_ui_theme() -> None:
    """Charge le thème moderne CoreUI sombre sans changer les données métiers."""
    css_file = Path(__file__).resolve().parent / 'coreui_dark.css'
    st.markdown('<style>\n' + css_file.read_text(encoding='utf-8') + '\n</style>', unsafe_allow_html=True)


def render_page_header(page: str) -> None:
    """En-tête CoreUI compact, sans modification des commandes Streamlit."""
    from html import escape
    descriptions = {
        'Tableau de bord': 'Suivi des diagnostics, recommandations et décisions pédagogiques.',
        'Diagnostic et scoring': 'Scores observés à T0 et niveaux initiaux des apprenants.',
        'Orientation des parcours': 'Proposition du modèle, avis du formateur et choix libre.',
        'Groupes et critères': 'Groupes pédagogiques, compétences et lacunes collectives.',
        'Performance et XAI': 'Résultats expérimentaux et explicabilité globale du modèle.',
        'Chapitres recommandés': 'Propositions du moteur hybride par groupe pédagogique.',
        'Propositions IA — chapitres et leçons': 'Brouillons IA soumis à une approbation humaine.',
        'Validation enseignante': 'Décisions sur les chapitres et ajouts complémentaires.',
        'Évaluation rapide': 'Appréciation de la pertinence des chapitres recommandés.',
        'Catalogue pédagogique': 'Référentiel des cours, chapitres, leçons et ressources.',
        'Contrôles et traçabilité': 'Contrôles des données, décisions et historiques.',
    }
    st.markdown(
        '<div class="core-header" role="banner">'
        '<div class="core-breadcrumb">Accueil &nbsp;/&nbsp; <strong>' + escape(page) + '</strong></div>'
        '<div class="core-heading">' + escape(page) + '</div>'
        '<div class="core-description">' + escape(descriptions.get(page, 'Espace enseignant.')) + '</div>'
        '</div>', unsafe_allow_html=True
    )


def render_featured_kpis(values: list[tuple[str, object, str]]) -> None:
    """Quatre KPI décorés par CSS ; valeurs tirées des exports réels."""
    from html import escape
    colors = ('purple', 'blue', 'yellow', 'red')
    cards = []
    for color, (label, value, subtitle) in zip(colors, values):
        cards.append(
            '<div class="core-kpi core-kpi--' + color + '">'
            '<div class="core-kpi-label">' + escape(label) + '</div>'
            '<div class="core-kpi-value">' + escape(str(value)) + '</div>'
            '<div class="core-kpi-sub">' + escape(subtitle) + '</div></div>'
        )
    st.markdown('<div class="core-kpi-grid">' + ''.join(cards) + '</div>', unsafe_allow_html=True)


apply_ui_theme()
st.sidebar.markdown("""
<div class="core-brand">
  <div class="core-logo">AE</div>
  <div><div class="core-brand-title">Adaptive e-Learning</div>
       <div class="core-brand-caption">Espace enseignants</div></div>
</div>
<div class="core-nav-title">NAVIGATION</div>
""", unsafe_allow_html=True)
VISIBLE_PAGES=PAGES if is_admin() else [x for x in PAGES if x not in ADMIN_ONLY_PAGES]
page = st.sidebar.radio('Navigation', VISIBLE_PAGES, label_visibility='collapsed')
logout_button()
render_page_header(page)
if my_parcours():
    st.info(f'Parcours **{my_parcours()} — {LABELS.get(my_parcours(),my_parcours())}** : vous ne voyez et ne décidez que pour ce parcours.')


if page=='Tableau de bord':
    st.markdown('<div class="core-section-title">Vue d’ensemble</div>', unsafe_allow_html=True)
    st.write('Chaîne scientifique : **diagnostic T0 → proposition de parcours → avis enseignant → choix libre → T1 → groupes → chapitres proposés**.')
    t0=data('diagnostic_t0');t1=data('t1');g0=data('groupes_t0');g1=data('groupes_t1');c0=data('chapitres_t0');c1=data('chapitres_t1');cat=data('catalogue_chapitres')
    render_featured_kpis([
        ('Diagnostics T0', len(t0), 'Apprenants diagnostiqués'),
        ('Évaluations T1', len(t1), 'Observations au cycle T1'),
        ('Groupes T0', len(g0), 'Groupes pédagogiques provisoires'),
        ('Groupes T1', len(g1), 'Groupes exploratoires'),
    ])
    a,b,c,d=st.columns(4)
    a.metric('Chapitres du catalogue initial',len(cat))
    b.metric('Propositions de chapitres T0',len(c0))
    c.metric('Propositions T1',len(c1))
    d.metric('Groupes T0 couverts',c0['ID_GROUPE'].nunique() if not c0.empty else 0)
    if is_admin():
        missing=diagnostics(ROOT)
        problems=[r for r in missing if r['Fichier'] in REQUIRED and r['Statut']!='OK']
        if problems:st.error(f'{len(problems)} fichier(s) critique(s) manquant(s) ou invalide(s). Voir « Contrôles et traçabilité ».')
        else:st.success('Exports essentiels repérés. Vérifier les propositions pédagogiques avant diffusion.')

    # Lire les trois stockages séparément. Les décisions V2 et les jugements H5
    # sont chargés à chaque affichage (pas de cache : visibles après redémarrage).
    st.subheader('Suivi des évaluations et des validations pédagogiques')
    try:
        history_v2=read_decisions(ROOT)
        reviews_h5=read_reviews(ROOT)
        archives=read_state(ROOT,'avis_chapitres')
        if my_parcours():
            history_v2=history_v2[history_v2['parcours'].eq(my_parcours())] if not history_v2.empty else history_v2
            reviews_h5=reviews_h5[reviews_h5['PARCOURS'].eq(my_parcours())] if not reviews_h5.empty else reviews_h5
            archives=scope_state(archives,'ID_GROUPE',my_groups(my_parcours()))
        by_course, totals=dashboard_validation_stats(c0,c1,history_v2,reviews_h5)
    except Exception as exc:
        st.error(f'Impossible de charger le suivi des validations : {exc}')
    else:
        a,b,c,d=st.columns(4)
        a.metric('Propositions évaluées',f"{totals['h5_couvertes']} / {totals['propositions']}")
        b.metric('Chapitres avec décision pédagogique',f"{totals['v2_couvertes']} / {totals['propositions']}")
        c.metric('Chapitres restant à décider',totals['v2_restant'])
        d.metric('Décisions enregistrées (historique)',totals['v2_evenements'])
        if totals['propositions']:
            st.progress(totals['v2_couvertes']/totals['propositions'])
        st.caption(
            'Évaluation : note de pertinence ; validation : choix pédagogique de l’enseignant. '
            'VALIDE, REMPLACE ou REJETE. Un même chapitre validé plusieurs fois compte pour une seule décision courante. '
            'Les révisions restent conservées dans l’historique.'
        )
        e,f,g=st.columns(3)
        e.metric('Notes d’évaluation enregistrées',totals['h5_lignes'])
        f.metric('Avis de l’ancien système (archive)',len(archives))
        g.metric('Groupes sans proposition documentés',totals['sans_candidat_documentes'])
        if totals['v2_hors_pool']:
            st.warning(f"{totals['v2_hors_pool']} décision(s) pédagogiques concernent des chapitres absents des exports actuels : non comptabilisées dans la progression.")

        st.subheader('Progression de validation par parcours et cycle')
        present(by_course, ['Parcours','Cycle','Propositions','Évaluations','Décisions pédagogiques',
                            'Validés','Remplacés','Rejetés','Restants'])

        with st.expander('Historique des décisions pédagogiques'):
            if history_v2.empty:
                st.info('Aucune décision pédagogique enregistrée pour le moment.')
            else:
                present(history_v2.iloc[::-1],
                        ['date_utc','parcours','etape','groupe_id','chapitre_initial_id',
                         'chapitre_initial_titre','enseignant_id','decision','justification'])
                st.download_button('Exporter l’historique des décisions (CSV)',
                                   history_v2.to_csv(index=False).encode('utf-8-sig'),
                                   file_name='decisions_chapitres_v2_historique.csv',mime='text/csv',
                                   key='dashboard_export_v2')

        with st.expander('Archives des anciens avis pédagogiques (lecture seule)'):
            st.caption('Les archives des décisions antérieures sont conservées séparément et ne sont pas comptées une seconde fois.')
            if archives.empty:
                st.info('Aucun ancien avis enregistré.')
            else:
                present(archives,['ETAPE','ID_GROUPE','ID_CHAPITRE','DECISION_ENSEIGNANT',
                                  'CHAPITRE_REMPLACEMENT','NOTE_PERTINENCE','VALIDATEUR','DATE_VALIDATION','COMMENTAIRE'])

    st.caption('Les évaluations de pertinence et les décisions pédagogiques ne démontrent pas à elles seules la qualité intégrale des contenus. Les analyses T1 sont rétrospectives et les prérequis documentaires demeurent partiellement renseignés.')
    st.subheader('Couverture des propositions par cycle')
    stat=[]
    for cycle,g,c in [('T0',g0,c0),('T1',g1,c1)]:
        stat.append({'Cycle':cycle,'Groupes':len(g),'Avec proposition':c['ID_GROUPE'].nunique() if not c.empty else 0,'Propositions':len(c)})
    present(pd.DataFrame(stat),['Cycle','Groupes','Avec proposition','Propositions'])

elif page=='Diagnostic et scoring':
    df=data('diagnostic_t0')
    if df.empty:st.error('Export T0 introuvable.')
    else:
        st.info('Scores observés au diagnostic initial. Les seuils de niveau T0 sont descriptifs et ne sont pas une prédiction T2.')
        ids=sorted(df['_ID_NORM'].tolist())
        target=st.selectbox('Apprenant (identifiant de la cohorte)',ids)
        line=df.loc[df['_ID_NORM']==target].iloc[0]
        cols=st.columns(4)
        for col,p in zip(cols,('DA','BI','DS','IA')):
            col.metric(p,str(line.get('S_'+p,'—')))
            col.caption('Niveau : '+LEVELS.get(line.get('NIVEAU_T0_'+p,''),line.get('NIVEAU_T0_'+p,'—')))
        with st.expander('Table diagnostique T0'):
            present(df,['_ID_NORM','S_DA','S_BI','S_DS','S_IA','NIVEAU_T0_DA','NIVEAU_T0_BI','NIVEAU_T0_DS','NIVEAU_T0_IA'])

elif page=='Orientation des parcours':
    auto=data('recommandation_auto');final=data('recommandation_finale_experimentale')
    if auto.empty:st.error('Résultats d’orientation T0 manquants.')
    else:
        univ=int(auto['PARCOURS_AUTO'].isin(LABELS).sum())
        a,b,c=st.columns(3)
        a.metric('Diagnostiqués',len(auto));b.metric('Propositions univoques',univ);c.metric('Cas à arbitrer',len(auto)-univ)
        st.warning('La proposition automatique n’est jamais une décision de l’enseignant, et le parcours suivi à T1 ne prouve pas le choix libre à T0.')
        if my_parcours():st.caption('Vous voyez les apprenants dont le système recommande votre parcours. Les cas ambigus sont arbitrés par l’administrateur.')
        ids=sorted(auto['_ID_NORM'].tolist())
        uid=st.selectbox('Identifiant de l’apprenant',ids)
        current=auto.loc[auto['_ID_NORM']==uid].iloc[0]
        proposed=current.get('PARCOURS_AUTO','') or 'A_VALIDER'
        st.write('**Proposition automatique (historique, immuable) :**',proposed)
        diagnostic=data('diagnostic_t0')
        score=diagnostic.loc[diagnostic['_ID_NORM']==uid] if not diagnostic.empty else pd.DataFrame()
        if not score.empty:
            v=score.iloc[0]
            cols=st.columns(4)
            for col, parcours in zip(cols, ('DA','BI','DS','IA')):
                col.metric(f'Score {parcours}',str(v.get('S_'+parcours,'—')))
            st.caption('Les quatre scores sont descriptifs et ne remplacent pas le choix final libre de l’apprenant.')
        if 'CLASSEMENT_PARCOURS' in current:st.caption('Classement : '+current['CLASSEMENT_PARCOURS'])
        prevexp=final[final['_ID_NORM']==uid] if not final.empty else pd.DataFrame()
        if not prevexp.empty:
            st.caption('Décision historique du notebook 05 : '+prevexp.iloc[0].get('STATUT_FINAL','NON_DOCUMENTEE'))
        st.divider()
        st.subheader('Avis enseignant sur l’orientation')
        with st.form('avis_parcours'):
            op=st.selectbox('Décision',['VALIDE','MODIFIE','REJETE','ARBITRE'])
            pr=st.selectbox('Parcours conseillé par le formateur',['']+list(LABELS))
            validator=st.text_input('Identité du formateur (compte connecté)' if validator_locked() else 'Identifiant de l’enseignant concerné',value=validator_default(),disabled=validator_locked())
            comment=st.text_area('Justification')
            go=st.form_submit_button('Enregistrer cet avis')
        if go:
            if op=='VALIDE' and proposed not in LABELS:st.error('Impossible de valider une proposition ambiguë : utiliser ARBITRE avec un parcours.')
            elif op=='VALIDE' and pr not in ('',proposed):st.error('Pour VALIDE, le parcours conseillé doit correspondre à la proposition automatique.')
            elif op=='MODIFIE' and pr==proposed:st.error('Pour MODIFIE, le parcours doit être différent de la proposition.')
            else:
                try:
                    save_record(ROOT,'avis_parcours',{'APPRENANT_ID':uid,'DECISION_ENSEIGNANT':op,
                     'PARCOURS_ENSEIGNANT':(proposed if op=='VALIDE' else pr),'VALIDATEUR':validator,'DATE_VALIDATION':utcnow(),'COMMENTAIRE':comment})
                    st.success('Avis enregistré séparément. Aucun choix apprenant n’a été déduit.')
                except Exception as e:st.error(str(e))
        st.subheader('Choix libre déclaré par l’apprenant')
        with st.form('choix_apprenant'):
            chosen=st.selectbox('Parcours choisi',list(LABELS),format_func=lambda x:f'{x} — {LABELS[x]}')
            source=st.text_input('Source de la déclaration explicite de l’apprenant',placeholder='Ex. formulaire signé, confirmation explicite')
            confirm=st.checkbox('Je confirme que ce choix a été explicitement communiqué par l’apprenant.')
            go_choice=st.form_submit_button('Enregistrer le choix explicite')
        if go_choice:
            if not confirm:st.error('Une confirmation explicite est nécessaire.')
            else:
                try:
                    save_record(ROOT,'choix_apprenants',{'APPRENANT_ID':uid,'PARCOURS_CHOISI':chosen,
                     'DATE_CHOIX':utcnow(),'SOURCE_CHOIX':source})
                    st.success('Choix apprenant enregistré indépendamment de la proposition et de l’avis enseignant.')
                except Exception as e:st.error(str(e))
        teacher=read_state(ROOT,'avis_parcours');choice=read_state(ROOT,'choix_apprenants')
        if not teacher.empty:
            tv=teacher[teacher['APPRENANT_ID']==uid]
            if not tv.empty:st.info('Avis enregistré dans Streamlit : '+tv.iloc[-1]['DECISION_ENSEIGNANT'])
        if not choice.empty:
            cv=choice[choice['APPRENANT_ID']==uid]
            if not cv.empty:st.success('Choix explicite enregistré dans Streamlit : '+cv.iloc[-1]['PARCOURS_CHOISI'])

elif page=='Performance et XAI':
    st.info('Consultation du modèle M_T1 entraîné dans le notebook 04. Cette page ne réentraîne pas le modèle et ne calcule pas de prédiction prospective pour de nouveaux apprenants.')
    meta=read_json(ROOT,'modele_metadata')
    if meta:
        perf=meta.get('performance_reference_nested_cv',{})
        a,b,c=st.columns(3)
        for col,key in zip((a,b,c),('MAE','RMSE','R2')):
            val=perf.get(key,None)
            col.metric(f'{key} — validation croisée',f'{val:.3f}' if isinstance(val,(float,int)) else '—')
        st.write('**Modèle :**',meta.get('algorithme','—'))
        st.write('**Formule :**',meta.get('formule','—'))
        st.caption(f"Échantillon modèle final : {meta.get('n_apprenants_final','—')} apprenants.")
    else:st.warning('Métadonnées du modèle 04 non trouvées.')
    st.subheader('Explicabilité globale (XAI)')
    xai_kind=st.selectbox('Méthode',['Permutation importance','Importance native RF','SHAP'])
    xai_source={'Permutation importance':'xai_permutation','Importance native RF':'xai_importance','SHAP':'xai_shap'}[xai_kind]
    xai=data(xai_source)
    if xai.empty:
        st.info('Table XAI absente : vérifier les exports du notebook 04.')
    else:
        st.caption('Table exportée du notebook 04. Les importances ne sont pas des explications causales individuelles.')
        present(xai,list(xai.columns)[:8],limit=25)
    base=data('base_groupes_t1')
    if not base.empty:
        st.subheader('Prédictions historiques hors pli (OOF)')
        st.warning('Les valeurs T2_PREDIT_OOF ont été calculées à des fins expérimentales rétrospectives ; ne pas les présenter comme des prédictions prospectives nouvelles.')
        selected=safe_col(base,['_ID_NORM','T1__PARCOURS','T1__SCORE','T2_PREDIT_OOF','NIVEAU_PARCOURS','ID_GROUPE'])
        if selected:present(base,selected)

elif page=='Groupes et critères':
    cycle=st.radio('Cycle',['T0','T1'],horizontal=True)
    groups,gid=filter_group(cycle)
    if gid:
        group_details(cycle,gid)
        st.subheader('Groupes du parcours et du niveau')
        present(groups,['ID_GROUPE','PARCOURS','NIVEAU','N_APPRENANTS','LACUNE_PRINCIPALE','SOURCE_LACUNES','STATUT_GROUPE'])
        if cycle=='T1':
            base=data('base_groupes_t1')
            if not base.empty:
                filtered=base[base['ID_GROUPE']==gid]
                st.caption(f'{len(filtered)} enregistrement(s) d’apprenants dans ce groupe (cohorte rétrospective).')
                present(filtered,['_ID_NORM','ID_GROUPE','T1__PARCOURS','NIVEAU_PARCOURS','T1__SCORE','NB_LACUNES'])

elif page=='Chapitres recommandés':
    st.info('Sorties du notebook 06 : chapitres uniquement. Les objectifs des leçons servent à l’indexation, pas à une recommandation séparée.')
    cycle=st.radio('Cycle',['T0','T1'],horizontal=True)
    _,gid=filter_group(cycle)
    if gid:
        group_details(cycle,gid)
        candidates=data('chapitres_'+cycle.lower())
        if not candidates.empty:
            selected=candidates[candidates['ID_GROUPE']==gid]
            st.subheader(f'{len(selected)} chapitre(s) candidat(s)')
            chapter_display(selected)
    st.caption('Aucun classement ne constitue à lui seul une preuve de pertinence pédagogique. Les prérequis sont à documenter. Le score RRF n’est pas une probabilité.')

elif page=='Propositions IA — chapitres et leçons':
    show_page(ROOT,data,filter_group,group_details)

elif page=='Validation enseignante':
    show_chapter_validation(ROOT,data)
    st.subheader('Archives des anciens avis pédagogiques (lecture seule)')
    st.caption('Ces décisions historiques sont archivées et conservées séparément des validations pédagogiques actuelles.')
    saved=read_state(ROOT,'avis_chapitres')
    if my_parcours():saved=scope_state(saved,'ID_GROUPE',my_groups(my_parcours()))
    if not saved.empty:present(saved,['ETAPE','ID_GROUPE','ID_CHAPITRE','DECISION_ENSEIGNANT','CHAPITRE_REMPLACEMENT','NOTE_PERTINENCE','VALIDATEUR','DATE_VALIDATION','COMMENTAIRE'])
    else:st.info('Aucun avis enseignant saisi dans cette application.')
    if not saved.empty:
        st.download_button('Exporter les avis de chapitres (CSV)',
                           saved.to_csv(index=False).encode('utf-8-sig'),
                           'avis_chapitres_enseignants.csv','text/csv')

elif page=='Évaluation rapide':
    show_h5_fast_review(ROOT,data)

elif page=='Catalogue pédagogique':
    st.write('Référentiel pédagogique extensible : **domaine → parcours → cours → chapitre → leçon**.')
    chapters=data('catalogue_chapitres');courses=data('cours');lessons=data('source_lecons')
    chapters,lessons=actual_catalogue(ROOT,chapters,lessons)
    if chapters.empty:st.error('Catalogue de chapitres manquant.')
    else:
        p=st.selectbox('Parcours',['Tous']+sorted(chapters['parcours_id'].unique().tolist()))
        view=chapters if p=='Tous' else chapters[chapters['parcours_id']==p]
        coursids=sorted(view['cours_id'].unique().tolist())
        c=st.selectbox('Cours',['Tous']+coursids)
        if c!='Tous':view=view[view['cours_id']==c]
        present(view,['domaine_id','parcours_id','cours_id','chapitre_id','chapitre_titre','chemin_pdf'])
        selected=st.selectbox('Détail d’un chapitre',view['chapitre_id'].tolist()) if not view.empty else None
        if selected:
            ch=view[view['chapitre_id']==selected].iloc[0]
            st.subheader(ch['chapitre_titre'])
            st.write('**Cours :**',ch['cours_id'])
            if 'texte_indexable' in ch:st.caption('Index sémantique : '+ch['texte_indexable'][:650])
            if not lessons.empty and 'chapter_id' in lessons:
                l=lessons[lessons['chapter_id']==selected]
                st.write('**Leçons et objectifs pédagogiques (non recommandées individuellement)**')
                present(l,['lesson_id','lesson_title','learning_objectives','keywords','assessment_type','minimum_score'])
            path=safe_pdf(ROOT,ch.get('chemin_pdf',''))
            if path:
                with open(path,'rb') as f:st.download_button('Télécharger le PDF du cours',f.read(),file_name=path.name,mime='application/pdf',key=f'catpdf_{selected}')
            else:st.caption('Aucun PDF accessible à cet emplacement à partir du projet local.')
        st.caption(f'{len(chapters)} chapitres du catalogue initial et du catalogue complémentaire approuvé ; aucun brouillon n’est publié.')

elif page=='Contrôles et traçabilité':
    st.write('Prévalidation basée sur la présence et les schémas des exports locaux. Cela ne remplace pas la validation scientifique ou humaine.')
    checks=pd.DataFrame(diagnostics(ROOT))
    st.dataframe(checks,use_container_width=True,hide_index=True)
    a=data('chapitres_t0');b=data('chapitres_t1')
    if not a.empty and not b.empty:
        issues=chapter_file_guard(a,b)
        if issues:
            for issue in issues:st.error(issue)
        else:st.success('Les exports de chapitres T0/T1 ont des identifiants distincts par groupe, des cycles cohérents et des statuts de candidats non validés.')
    rep=read_json(ROOT,'rapport_organisation')
    if rep:
        st.subheader('Arborescence des ressources')
        st.json({k:v for k,v in rep.items() if k!='avertissements'})
        if rep.get('avertissements'):
            with st.expander('Avertissements de migration'):
                st.write(rep.get('avertissements'))
    st.subheader('Traçabilité des décisions saisies')
    journal=ROOT/'outputs/streamlit_validation/journal_evenements.csv'
    if journal.exists():
        present(pd.read_csv(journal,dtype=str,keep_default_na=False),['HORODATAGE_UTC','TYPE','CLE','ACTION','VALIDATEUR_OU_SOURCE'])
    else:st.info('Aucune décision saisie dans Streamlit à ce stade.')
    st.caption('Limites : les prérequis ne sont pas entièrement documentés ; le RAG PDF reste à établir expérimentalement ; les jugements de pertinence portent sur les candidats hybrides et ne constituent pas une comparaison équitable TF-IDF/E5/RRF ; aucun nouveau modèle n’est entraîné ici.')

