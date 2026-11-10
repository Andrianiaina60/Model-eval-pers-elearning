"""Décisions manuelles distinctes des CSV expérimentaux. Traçabilité locale."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import csv
import json
import os
import tempfile
import pandas as pd

BASE='outputs/streamlit_validation'
FIELDS={
 'avis_parcours':['APPRENANT_ID','DECISION_ENSEIGNANT','PARCOURS_ENSEIGNANT','VALIDATEUR','DATE_VALIDATION','COMMENTAIRE'],
 'choix_apprenants':['APPRENANT_ID','PARCOURS_CHOISI','DATE_CHOIX','SOURCE_CHOIX'],
 'avis_chapitres':['ETAPE','ID_GROUPE','ID_CHAPITRE','DECISION_ENSEIGNANT','CHAPITRE_REMPLACEMENT','NOTE_PERTINENCE','VALIDATEUR','DATE_VALIDATION','COMMENTAIRE'],
}
CHOIX_PARCOURS={'DA','BI','DS','IA'}
CHOIX_AVIS_P={'VALIDE','MODIFIE','REJETE','ARBITRE'}
CHOIX_AVIS_C={'VALIDE','MODIFIE','REJETE'}

def state_path(root:Path,name:str)->Path:
 if name not in FIELDS: raise KeyError(name)
 return Path(root)/BASE/f'{name}.csv'

def read_state(root:Path,name:str)->pd.DataFrame:
 path=state_path(root,name)
 if not path.exists():return pd.DataFrame(columns=FIELDS[name])
 df=pd.read_csv(path,dtype=str,encoding='utf-8-sig',keep_default_na=False)
 # Tolère les avis des versions antérieures (sans note de pertinence).
 if name=='avis_chapitres' and 'NOTE_PERTINENCE' not in df.columns:
  df['NOTE_PERTINENCE']=''
 if not set(FIELDS[name]).issubset(df.columns):
  raise ValueError(f'{path.name} : schema incomplet')
 return df

def validate(name:str,row:dict):
 missing=[f for f in FIELDS[name] if f not in row and not (name=='avis_chapitres' and f=='NOTE_PERTINENCE')]
 if missing: raise ValueError(f'Champs manquants: {missing}')
 if name=='avis_parcours':
  if row['DECISION_ENSEIGNANT'] not in CHOIX_AVIS_P:raise ValueError('Avis invalide')
  if row['DECISION_ENSEIGNANT'] in {'MODIFIE','ARBITRE'} and row['PARCOURS_ENSEIGNANT'] not in CHOIX_PARCOURS:
   raise ValueError('Modification/arbitrage : parcours obligatoire')
  if not row['APPRENANT_ID'].strip() or not row['VALIDATEUR'].strip():raise ValueError('Identifiant et validateur obligatoires')
 if name=='choix_apprenants':
  if row['PARCOURS_CHOISI'] not in CHOIX_PARCOURS:raise ValueError('Parcours choisi invalide')
  if not row['APPRENANT_ID'].strip() or not row['SOURCE_CHOIX'].strip():raise ValueError('Identifiant et source du choix obligatoires')
 if name=='avis_chapitres':
  if row['DECISION_ENSEIGNANT'] in {'MODIFIE','REJETE'} and not str(row.get('COMMENTAIRE','')).strip():
   raise ValueError('Justification obligatoire pour modification/refus')
  if row['ETAPE'] not in {'T0','T1'} or row['DECISION_ENSEIGNANT'] not in CHOIX_AVIS_C:
   raise ValueError('Cycle/avis invalide')
  if row['DECISION_ENSEIGNANT']=='MODIFIE' and not row['CHAPITRE_REMPLACEMENT'].strip():
   raise ValueError('Remplacement obligatoire')
  if row['DECISION_ENSEIGNANT']=='MODIFIE' and row['CHAPITRE_REMPLACEMENT']==row['ID_CHAPITRE']:
   raise ValueError('Le chapitre de remplacement doit differer du candidat')
  if str(row.get('NOTE_PERTINENCE','')) not in {'','1','2','3','4','5'}:
   raise ValueError('La note de pertinence doit être comprise entre 1 et 5')
  if not row['ID_GROUPE'].strip() or not row['ID_CHAPITRE'].strip() or not row['VALIDATEUR'].strip():
   raise ValueError('Groupe, chapitre et validateur obligatoires')

def _atomic_csv(path:Path,rows:list[dict],columns:list[str]):
 path.parent.mkdir(parents=True,exist_ok=True)
 fd,temp=tempfile.mkstemp(prefix=path.stem+'_',suffix='.tmp',dir=path.parent)
 try:
  with os.fdopen(fd,'w',newline='',encoding='utf-8-sig') as f:
   w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore')
   w.writeheader();w.writerows(rows);f.flush();os.fsync(f.fileno())
  os.replace(temp,path)
 finally:
  if os.path.exists(temp):os.remove(temp)

def save_record(root:Path,name:str,row:dict)->None:
 validate(name,row)
 source=read_state(root,name)
 keys={'avis_parcours':['APPRENANT_ID'],'choix_apprenants':['APPRENANT_ID'],
       'avis_chapitres':['ETAPE','ID_GROUPE','ID_CHAPITRE']}[name]
 previous=source
 for k in keys:
  previous=previous[previous[k].astype(str)==str(row[k])]
 # Une clé composite doit être testée conjointement : tous ses champs doivent coïncider.
 same_key=pd.Series(True,index=source.index,dtype=bool)
 for k in keys:
  same_key &= source[k].astype(str).eq(str(row[k]))
 existing=source.loc[~same_key].to_dict('records')
 existing.append({key:str(row.get(key,'')) for key in FIELDS[name]})
 _atomic_csv(state_path(root,name),existing,FIELDS[name])
 journal=Path(root)/BASE/'journal_evenements.csv'
 jcols=['HORODATAGE_UTC','TYPE','CLE','ACTION','VALIDATEUR_OU_SOURCE','AVANT_JSON','APRES_JSON']
 events=[]
 if journal.exists():
  events=pd.read_csv(journal,dtype=str,keep_default_na=False,encoding='utf-8-sig').to_dict('records')
 events.append({'HORODATAGE_UTC':datetime.now(timezone.utc).isoformat(),
                'TYPE':name,'CLE':'/'.join(str(row[k]) for k in keys),
                'ACTION':str(row.get('DECISION_ENSEIGNANT',row.get('PARCOURS_CHOISI',''))),
                'VALIDATEUR_OU_SOURCE':str(row.get('VALIDATEUR',row.get('SOURCE_CHOIX',''))),
                'AVANT_JSON':json.dumps(previous.iloc[-1].to_dict(),ensure_ascii=False) if not previous.empty else '',
                'APRES_JSON':json.dumps({key:str(row.get(key,'')) for key in FIELDS[name]},ensure_ascii=False)})
 _atomic_csv(journal,events,jcols)

def utcnow()->str:
 return datetime.now(timezone.utc).isoformat(timespec='seconds')
