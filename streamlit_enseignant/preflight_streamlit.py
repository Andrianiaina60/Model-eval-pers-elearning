"""Contrôle des fichiers essentiels, sans lire les identifiants d'apprenants ni recalculer les résultats."""
from pathlib import Path
import argparse
from data_access import PATHS,REQUIRED,diagnostics,chapter_file_guard,read_csv


def check(root:Path)->tuple[bool,list[dict]]:
    errors=[]
    reports=diagnostics(root)
    for item in reports:
        if item['Fichier'] in REQUIRED and item['Statut']!='OK':errors.append(f"{item['Fichier']}: {item['Statut']} {item['Détail']}")
    if not errors:
        c0=read_csv(root,'chapitres_t0');c1=read_csv(root,'chapitres_t1')
        errors.extend(chapter_file_guard(c0,c1))
    return not errors,reports+([{'ERREURS':errors}] if errors else [])

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path.cwd())
    args=parser.parse_args()
    ok,report=check(args.root.resolve())
    for r in report:
        if 'Fichier' in r:
            print(f"{r['Statut']:<21} {r['Fichier']:<35} {r.get('Détail','')}")
        else:
            for e in r['ERREURS']:print('ERREUR :',e)
    print('\nBILAN:', 'OK — Streamlit peut lire les exports.' if ok else 'À CORRIGER — fichiers essentiels manquants/incohérents.')
    raise SystemExit(0 if ok else 2)
