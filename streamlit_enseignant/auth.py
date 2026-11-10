"""Connexion simple des enseignants (prototype local).

- Comptes dans outputs/streamlit_validation/enseignants.json (mots de passe hachés PBKDF2).
- Créer un compte : python creer_enseignant.py --email ... --nom ... --parcours DA
- L'identifiant de l'enseignant connecté (ex. ENS-DA-01) pré-remplit les avis,
  ce qui rend la traçabilité des validateurs fiable.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
import streamlit as st

ACCOUNTS = Path('outputs/streamlit_validation/enseignants.json')
ITERATIONS = 200_000
MAX_FAILS, LOCK_SECONDS = 5, 30
PARCOURS = {'DA', 'BI', 'DS', 'IA'}


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ITERATIONS)
    return f'pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}'


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split('$')
        check = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(check.hex(), digest)
    except (ValueError, TypeError):
        return False


def load_accounts(root: Path) -> list[dict]:
    path = Path(root) / ACCOUNTS
    if not path.is_file():
        return []
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save_accounts(root: Path, accounts: list[dict]) -> None:
    path = Path(root) / ACCOUNTS
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(accounts, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(tmp, path)


def add_account(root: Path, email: str, nom: str, parcours: str, password: str, role: str = 'enseignant') -> dict:
    email = email.strip().lower()
    if '@' not in email or len(password) < 8:
        raise ValueError('E-mail invalide ou mot de passe de moins de 8 caractères.')
    if role not in ('admin', 'enseignant'):
        raise ValueError("Rôle : 'admin' ou 'enseignant'.")
    if role == 'admin':
        parcours = 'TOUS'
    elif parcours not in PARCOURS:
        raise ValueError('Parcours : DA, BI, DS ou IA.')
    accounts = load_accounts(root)
    if any(a['email'] == email for a in accounts):
        raise ValueError('Cet e-mail existe déjà.')
    n = sum(1 for a in accounts if a.get('role', 'enseignant') == role and a['parcours'] == parcours) + 1
    prefix = 'ADMIN' if role == 'admin' else f'ENS-{parcours}'
    account = {'email': email, 'nom': nom.strip(), 'parcours': parcours, 'role': role,
               'identifiant': f'{prefix}-{n:02d}', 'hash': hash_password(password)}
    save_accounts(root, accounts + [account])
    return account


def authenticate(root: Path, email: str, password: str) -> dict | None:
    email = email.strip().lower()
    account = next((a for a in load_accounts(root) if a['email'] == email), None)
    # Même coût de calcul si l'e-mail est inconnu (évite de révéler quels comptes existent).
    stored = account['hash'] if account else hash_password('x')
    ok = verify_password(password, stored)
    return account if (account and ok) else None


def current_user() -> dict:
    return st.session_state.get('user', {})


def is_admin() -> bool:
    return current_user().get('role') == 'admin'


def my_parcours() -> str | None:
    """Parcours imposé à l'enseignant connecté ; None pour l'admin (accès à tous)."""
    u = current_user()
    return None if u.get('role') == 'admin' else (u.get('parcours') or '__AUCUN__')


def validator_default() -> str:
    """Identifiant pré-rempli : celui de l'enseignant connecté. Vide pour l'admin,
    afin de ne jamais enregistrer un avis pédagogique au nom de l'administrateur."""
    return '' if is_admin() else current_user().get('identifiant', '')


def validator_locked() -> bool:
    return not is_admin()


def _css() -> None:
    st.markdown("""
<style>
[data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="stToolbar"] {display:none !important}
[data-testid="stApp"], [data-testid="stAppViewContainer"], [data-testid="stMain"] {background:#020617 !important}
.block-container {max-width:420px !important; padding-top:11vh !important}
[data-testid="stForm"] {background:#fff !important; border:0 !important; border-radius:22px !important;
  padding:30px 30px 22px !important; box-shadow:0 20px 60px rgba(0,0,0,.45)}
.lg-logo {width:36px; height:36px; border-radius:10px; background:#fbbf24; display:flex;
  align-items:center; justify-content:center; font-size:19px; margin-bottom:14px}
.lg-brand {color:#d97706; font-size:11px; font-weight:700; letter-spacing:.14em; margin:0}
.lg-title {color:#0f172a; font-size:26px; font-weight:700; margin:2px 0 6px}
.lg-sub {color:#64748b; font-size:13px; line-height:1.45; margin:0 0 14px}
[data-testid="stForm"] label p {color:#0f172a !important; font-size:13px !important; font-weight:500}
[data-testid="stForm"] [data-baseweb="input"], [data-testid="stForm"] [data-baseweb="base-input"] {
  background:#e8effc !important; border:0 !important; border-radius:10px !important}
[data-testid="stForm"] input {color:#0f172a !important; -webkit-text-fill-color:#0f172a !important}
[data-testid="stForm"] [data-baseweb="input"] button svg {fill:#475569 !important}
[data-testid="stFormSubmitButton"] button {width:100%; background:#0f172a !important; color:#fff !important;
  border:0 !important; border-radius:10px !important; padding:.55rem 0; font-weight:600}
[data-testid="stFormSubmitButton"] button:hover {background:#1e293b !important}
[data-testid="stFormSubmitButton"] button:focus-visible, [data-testid="stForm"] input:focus {
  outline:2px solid #fbbf24 !important; outline-offset:1px}
.lg-err {background:#fef2f2; color:#b91c1c; border-radius:8px; padding:10px 12px; font-size:13px; margin:4px 0 10px}
.lg-foot {color:#94a3b8; font-size:11px; text-align:center; margin:12px 0 0}
</style>""", unsafe_allow_html=True)


def require_login(root: Path) -> dict:
    """À appeler juste après st.set_page_config. Arrête la page tant que l'utilisateur n'est pas connecté."""
    if st.session_state.get('user'):
        return st.session_state['user']
    _css()
    locked_until = st.session_state.get('_lock_until', 0)
    with st.form('login', clear_on_submit=False):
        st.markdown('<div class="lg-logo">🎓</div><p class="lg-brand">ADAPTIVE E-LEARNING</p>'
                    '<div class="lg-title">Bienvenue</div>'
                    '<p class="lg-sub">Connectez-vous pour accéder à l’espace enseignants.</p>',
                    unsafe_allow_html=True)
        email = st.text_input('Adresse e-mail', placeholder='prenom.nom@exemple.com')
        password = st.text_input('Mot de passe', type='password')
        error = st.session_state.pop('_login_error', '')
        if error:
            st.markdown(f'<div class="lg-err">{error}</div>', unsafe_allow_html=True)
        submit = st.form_submit_button('Se connecter')
        st.markdown('<p class="lg-foot">L’accès nécessite un compte enseignant.</p>', unsafe_allow_html=True)
    if submit:
        if time.time() < locked_until:
            st.session_state['_login_error'] = f'Trop de tentatives. Réessayez dans {int(locked_until - time.time()) + 1} s.'
            st.rerun()
        if not load_accounts(root):
            st.session_state['_login_error'] = 'Aucun compte créé. Lancez : python creer_enseignant.py'
            st.rerun()
        account = authenticate(root, email, password)
        if account:
            st.session_state['user'] = {k: account[k] for k in ('email', 'nom', 'parcours', 'identifiant')}
            st.session_state['user']['role'] = account.get('role', 'enseignant')
            st.session_state['_teacher_access'] = True   # déverrouille aussi la revue pédagogique
            st.session_state['_fails'] = 0
            st.rerun()
        fails = st.session_state.get('_fails', 0) + 1
        st.session_state['_fails'] = fails
        if fails >= MAX_FAILS:
            st.session_state['_lock_until'] = time.time() + LOCK_SECONDS
            st.session_state['_fails'] = 0
        st.session_state['_login_error'] = 'Adresse e-mail ou mot de passe incorrect.'
        st.rerun()
    st.stop()


def logout_button() -> None:
    user = current_user()
    scope = 'administrateur · tous les parcours' if is_admin() else f"parcours {user.get('parcours', '')}"
    st.sidebar.markdown(f"**{user.get('nom') or user.get('email', '')}**  \n"
                        f"{user.get('identifiant', '')} · {scope}")
    if st.sidebar.button('Se déconnecter', use_container_width=True):
        for k in ('user', '_teacher_access'):
            st.session_state.pop(k, None)
        st.rerun()
