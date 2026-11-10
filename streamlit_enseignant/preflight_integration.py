"""Vérification non destructive des fichiers nécessaires à l'interface Streamlit.
Lancer depuis la racine : python streamlit_enseignant/preflight_integration.py
"""
from __future__ import annotations
import sys
from pathlib import Path
from data_access import project_root, diagnostics


def main() -> int:
    root=project_root(Path(__file__).resolve().parent)
    print('RACINE PROJET :',root)
    results=diagnostics(root)
    problems=[]
    for result in results:
        state=result['Statut']; detail=result['Détail']
        print(f"{state:<23} {result['Fichier']:<32} {detail}")
        if state not in {'OK','OPTIONNEL_ABSENT'}:
            problems.append(result)
    if problems:
        print(f'\n{len(problems)} élément(s) bloquant(s). Vérifier les exports avant de lancer Streamlit.')
        return 2
    print('\nOK — toutes les dépendances requises et leurs schémas sont disponibles.')
    print('Ce contrôle ne valide ni les enseignants, ni H4/H5, ni le serveur Ollama.')
    return 0


if __name__=='__main__':
    sys.exit(main())
