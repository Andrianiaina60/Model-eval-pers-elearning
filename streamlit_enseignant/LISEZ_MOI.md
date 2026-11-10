# Correction des deux erreurs de tests Streamlit

Depuis la racine du projet Ubuntu, sauvegarder puis remplacer `test_import_csv_h5.py` par celui fourni. Exécuter ensuite `fix_preflight_import.py` depuis la racine du projet ; il ne modifie que les imports de `test_preflight.py`, avec sauvegarde automatique.

```bash
cd ~/projet/Model-eval-pers-elearning
source .venv/bin/activate
cp streamlit_enseignant/tests/test_import_csv_h5.py streamlit_enseignant/tests/test_import_csv_h5.py.bak
# Décompresser le pack à la racine du projet
unzip -o FIX_TESTS_STREAMLIT_H5_20261102.zip
python fix_preflight_import.py
python -m unittest discover -s streamlit_enseignant/tests -p 'test_*.py' -v
```

Aucun fichier de données ou export H5 n'est modifié.
