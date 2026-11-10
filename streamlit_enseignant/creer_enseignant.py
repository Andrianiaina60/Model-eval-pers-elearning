"""Crée un compte.  Exemples :
python creer_enseignant.py --role admin --email admin@gmail.com --nom "Chercheur"
python creer_enseignant.py --email prof.da@exemple.com --nom "Nom Prénom" --parcours DA
Le mot de passe est demandé à la saisie (jamais écrit en clair)."""
import argparse
import getpass
from pathlib import Path
from auth import add_account
from data_access import project_root

p = argparse.ArgumentParser()
p.add_argument('--role', choices=['enseignant', 'admin'], default='enseignant')
p.add_argument('--email', required=True)
p.add_argument('--nom', required=True)
p.add_argument('--parcours', choices=['DA', 'BI', 'DS', 'IA'], help='obligatoire pour un enseignant')
a = p.parse_args()
if a.role == 'enseignant' and not a.parcours:
    raise SystemExit('--parcours est obligatoire pour un enseignant.')
pwd = getpass.getpass('Mot de passe (8 caractères min.) : ')
if pwd != getpass.getpass('Confirmer : '):
    raise SystemExit('Les mots de passe diffèrent.')
acc = add_account(project_root(Path(__file__).resolve().parent), a.email, a.nom, a.parcours or 'TOUS', pwd, a.role)
print('Compte créé :', acc['email'], '→', acc['role'], acc['identifiant'])
