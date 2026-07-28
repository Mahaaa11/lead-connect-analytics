"""Login gate and account settings for the analytics app."""

from __future__ import annotations

import importlib

import streamlit as st


def _database_module():
    """Reload database module so Streamlit hot-reload picks up new functions."""
    from engine import database

    importlib.reload(database)
    return database


def _brand_logo_module():
    from ui import brand_logo

    importlib.reload(brand_logo)
    return brand_logo


def init_auth_session() -> None:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "auth_username" not in st.session_state:
        st.session_state.auth_username = ""
    if "auth_db_error" not in st.session_state:
        st.session_state.auth_db_error = ""
    db = _database_module()
    if not hasattr(db, "ensure_app_user"):
        raise RuntimeError(
            "Module database obsolète. Arrêtez Streamlit (Ctrl+C) puis relancez : "
            "streamlit run ui/streamlit_app.py"
        )
    try:
        db.ensure_app_user()
        st.session_state.auth_db_error = ""
    except Exception as exc:
        st.session_state.auth_db_error = str(exc)


def render_login_page() -> None:
    import importlib
    from ui import brand_theme

    importlib.reload(brand_theme)
    brand_logo = _brand_logo_module()

    st.markdown(brand_theme.LOGIN_PAGE_CSS, unsafe_allow_html=True)
    st.markdown('<div class="lc-login-root-marker"></div>', unsafe_allow_html=True)

    col_brand, col_form = st.columns([1.05, 0.95], gap="small")

    with col_brand:
        st.markdown(
            f"""
            <div class="lc-col-brand-marker"></div>
            <div class="lc-brand-panel">
              <div class="lc-logo-card">
                {brand_logo.logo_img_html(max_width="260px")}
              </div>
              <p class="lc-brand-eyebrow">Plateforme Analytics · FÈS</p>
              <h1 class="lc-brand-title">Vos données.<br/>Votre performance.</h1>
              <p class="lc-brand-desc">
                Analyse, ventes, recyclage et suivi quotidien — en un seul espace.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_form:
        db_error = st.session_state.get("auth_db_error") or ""
        if db_error:
            st.error(
                f"Impossible de joindre la base de données : {db_error}\n\n"
                "Vérifiez **DATABASE_URL** dans les secrets Streamlit "
                "(format `postgresql://...?sslmode=require`)."
            )

        st.markdown(
            """
            <div class="lc-col-form-marker"></div>
            <div class="lc-form-panel">
              <div class="lc-form-header">
                <span class="lc-form-badge">Espace sécurisé</span>
                <h2 class="lc-form-title">Connexion</h2>
                <p class="lc-form-sub">Bienvenue — connectez-vous pour continuer</p>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Identifiant", placeholder="Votre identifiant")
            password = st.text_input("Mot de passe", type="password", placeholder="••••••••")
            submitted = st.form_submit_button(
                "Se connecter →", type="primary", use_container_width=True
            )

        if submitted:
            user = username.strip()
            if st.session_state.get("auth_db_error"):
                st.error("Connexion base indisponible — corrigez DATABASE_URL avant de vous connecter.")
                return
            db = _database_module()
            if not user or not password:
                st.error("Identifiant et mot de passe sont obligatoires.")
            else:
                try:
                    ok = db.authenticate(user, password)
                except Exception as exc:
                    st.error(f"Erreur base de données : {exc}")
                    return
                if ok:
                    st.session_state.authenticated = True
                    st.session_state.auth_username = user
                    st.rerun()
                else:
                    st.error(
                        "Identifiant ou mot de passe incorrect. "
                        "Sur PostgreSQL, le mot de passe migré peut différer de `leadconnect` — "
                        "ajoutez `APP_RESET_PASSWORD_ON_START = \"true\"` dans les secrets Streamlit "
                        "puis redémarrez l'app."
                    )


def render_logout_button() -> None:
    user = st.session_state.get("auth_username") or "—"
    st.caption(f"Connecté : **{user}**")
    if st.button("Déconnexion", use_container_width=True, key="logout_btn"):
        st.session_state.authenticated = False
        st.session_state.auth_username = ""
        st.rerun()
    st.divider()


def render_account_settings() -> None:
    username = st.session_state.get("auth_username") or ""
    if not username:
        return

    st.markdown(
        """
        <div class="lc-page-hero" style="padding:12px 0 16px 0;margin-bottom:12px;">
            <div class="lc-eyebrow">Paramètres</div>
            <h2 class="lc-title" style="font-size:1.5rem;">Compte applicatif</h2>
            <p class="lc-subtitle">Modifiez votre mot de passe ici.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("change_password_form"):
        current_password = st.text_input("Mot de passe actuel", type="password")
        new_password = st.text_input("Nouveau mot de passe", type="password")
        confirm_password = st.text_input("Confirmer le nouveau mot de passe", type="password")
        submit = st.form_submit_button("Mettre à jour le mot de passe", type="primary")

    if submit:
        db = _database_module()
        if len(new_password) < 6:
            st.error("Le nouveau mot de passe doit contenir au moins 6 caractères.")
        elif new_password != confirm_password:
            st.error("Les deux mots de passe ne correspondent pas.")
        else:
            ok, message = db.change_app_password(username, current_password, new_password)
            if ok:
                st.success(message)
            else:
                st.error(message)
