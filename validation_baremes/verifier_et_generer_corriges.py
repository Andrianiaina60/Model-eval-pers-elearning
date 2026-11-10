#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Édition contrôlée de barèmes approuvés ; ne touche pas aux dossiers outputs/.

IMPORTANT : seule une approbation humaine réelle documentée peut remplir les champs
VALIDATEUR, DATE_DECISION et SOURCE_PREUVE. Ce script vérifie les traces, il ne
certifie pas l'authenticité des signatures ou des documents de référence.
"""
from pathlib import Path
import csv, re, sys, hashlib, datetime
ROOT = Path(__file__).resolve().parent
REGISTER = ROOT / 'registre_baremes_140_questions.csv'
MANIFEST = ROOT / 'manifest_sources_sha256.csv'
OUTPUT = ROOT / 'baremes_approuves_a_installer'
EXPECTED = {'T0': 20, 'T1': 60, 'T2': 60}
REQUIRED = ['STATUT_VALIDATION', 'DECISION_BAREME', 'REPONSE_DECIDEE',
            'COMPETENCE_DECIDEE', 'JUSTIFICATION_DECIDEE', 'VALIDATEUR',
            'QUALIFICATION_VALID', 'DATE_DECISION', 'SOURCE_PREUVE']


def read_csv(path):
    with path.open('r', encoding='utf-8-sig', newline='') as fh:
        return list(csv.DictReader(fh))


def k_from_source(stage, row):
    if stage == 'T0':
        return (stage, row['DOMAINE'], str(int(row['Q_NUM'])))
    return (stage, row['PARCOURS'], str(int(row['QUESTION_INDEX'])))


rows = read_csv(REGISTER)
issues = []
if len(rows) != 140:
    issues.append(f'140 items attendus, reçus {len(rows)}')

# Vérifier les copies sources figées à partir des empreintes cryptographiques.
for m in read_csv(MANIFEST):
    target = ROOT / m['CHEMIN_COPIE']
    if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != m['SHA256']:
        issues.append('Fichier source manquant ou modifié : ' + str(target))

keys = set()
indexed = {}
for row in rows:
    uid = row.get('ID_ITEM', '')
    k = (row.get('ETAPE', ''), row.get('PARCOURS', ''),
         str(row.get('QUESTION_INDEX', '')).strip())
    if uid in keys or k in indexed:
        issues.append(f'Doublon de question : {uid}')
    keys.add(uid)
    indexed[k] = row
    if row.get('STATUT_VALIDATION') != 'APPROUVE':
        issues.append(f'{uid} : validation humaine non obtenue')
    decision = row.get('DECISION_BAREME', '')
    if decision not in {'VALIDER_PROPOSITION', 'CONSERVER_ORIGINAL', 'MODIFIER'}:
        issues.append(f'{uid} : décision absente ou incompatible avec notation mono-réponse ({decision})')
    if decision == 'VALIDER_PROPOSITION' and not row.get('REPONSE_PROPOSEE', '').strip():
        issues.append(f'{uid} : réponse proposée vide ; arbitrage indispensable')
    if decision == 'VALIDER_PROPOSITION' and row.get('REPONSE_DECIDEE', '').strip() != row.get('REPONSE_PROPOSEE', '').strip():
        issues.append(f'{uid} : réponse décidée différente de la proposition approuvée')
    if decision == 'CONSERVER_ORIGINAL' and row.get('REPONSE_DECIDEE', '').strip() != row.get('REPONSE_INITIALE', '').strip():
        issues.append(f'{uid} : réponse décidée différente de la clé originale conservée')
    for required in REQUIRED:
        if not row.get(required, '').strip():
            issues.append(f'{uid} : {required} non renseigné')
    if not re.fullmatch(r'[A-E]', row.get('REPONSE_DECIDEE', '').strip()):
        issues.append(f'{uid} : réponse unique A–E attendue ; plusieurs réponses ou exclusion exigent une adaptation du notebook')
    d = row.get('DATE_DECISION', '').strip()
    try:
        datetime.date.fromisoformat(d)
    except ValueError:
        issues.append(f'{uid} : DATE_DECISION invalide (attendu AAAA-MM-JJ)')

for stage, count in EXPECTED.items():
    source = read_csv(ROOT / 'sources_originales' / f'corrige_{stage}_initial.csv')
    if len(source) != count:
        issues.append(f'{stage} : effectif initial incorrect, {len(source)} au lieu de {count}')
    if sum(r['ETAPE'] == stage for r in rows) != count:
        issues.append(f'{stage} : nombre incorrect dans le registre')
    for srow in source:
        lookup = k_from_source(stage, srow)
        recorded = indexed.get(lookup)
        if recorded is None:
            issues.append(f'{stage} : question absente {lookup}')
            continue
        if srow['QUESTION'] != recorded['QUESTION'] or srow['MODALITES_OBSERVEES'] != recorded['OPTIONS_ORIGINALES_OBSERVEES']:
            issues.append(f'{recorded["ID_ITEM"]} : texte de question ou modalités de réponse modifiées')
        if srow['REPONSE_CORRECTE'] != recorded['REPONSE_INITIALE']:
            issues.append(f'{recorded["ID_ITEM"]} : réponse initiale altérée')

all_paths = {stage: OUTPUT / f'corrige_{stage}_valide.csv' for stage in EXPECTED}
for path in all_paths.values():
    if path.exists():
        issues.append(f'Fichier final déjà existant — écrasement interdit : {path}')

if issues:
    print('BLOCAGE : aucun corrigé final généré. Corrections nécessaires :')
    for issue in issues[:30]:
        print(' -', issue)
    if len(issues) > 30:
        print(f' ... et {len(issues)-30} autres points')
    sys.exit(1)

# On reprend le CSV initial exactement, sans reconstruire ses modalités observées.
OUTPUT.mkdir(exist_ok=True)
for stage, path in all_paths.items():
    with (ROOT / 'sources_originales' / f'corrige_{stage}_initial.csv').open(
            encoding='utf-8-sig', newline='') as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames
        source_rows = list(reader)
    for srow in source_rows:
        r = indexed[k_from_source(stage, srow)]
        srow['REPONSE_CORRECTE'] = r['REPONSE_DECIDEE'].strip()
        srow['COMPETENCE'] = r['COMPETENCE_DECIDEE'].strip()
        srow['JUSTIFICATION_COURTE'] = r['JUSTIFICATION_DECIDEE'].strip()
    with path.open('w', encoding='utf-8-sig', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(source_rows)
    print('Fichier produit après contrôles :', path)
print('Les décisions restent à vérifier avec les pièces de référence ; aucune signature ne peut être certifiée automatiquement.')
