"""Unified shell for the Lead & Connect analytics application."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from engine.data_client_dashboard import color_hex_for_label
from ui.brand_theme import GLOBAL_CSS, NAVY, ORANGE, OVERVIEW_CSS, TEXT_SECONDARY

NAV_ANALYTICS = [
    ("overview", "Vue d'ensemble"),
    ("data_client", "Data Client"),
    ("ventes", "Ventes"),
    ("dashboard", "Performance"),
    ("forecast", "Prévisionnel"),
]

NAV_OPERATIONS = [
    ("export", "Export recyclage"),
    ("database", "Base de données"),
]

NAV_LABELS = {key: label for key, label in NAV_ANALYTICS + NAV_OPERATIONS}


def inject_global_theme() -> None:
    import importlib
    from ui import brand_theme

    importlib.reload(brand_theme)
    st.markdown(brand_theme.GLOBAL_CSS, unsafe_allow_html=True)


def render_sidebar_brand() -> None:
    import importlib
    from ui import brand_logo

    importlib.reload(brand_logo)
    st.markdown(
        f"""
        <div class="lc-sidebar-logo">
            <div class="lc-logo-sidebar-wrap">
                {brand_logo.logo_img_html(css_class="lc-logo-sidebar", max_width="176px")}
            </div>
            <div class="brand-sub">Plateforme Analytics · FÈS</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_navigation(*, default: str = "overview") -> str:
    options = [key for key, _ in NAV_ANALYTICS + NAV_OPERATIONS]
    index = options.index(default) if default in options else 0
    st.markdown('<div class="nav-section">Navigation</div>', unsafe_allow_html=True)
    return st.radio(
        "Navigation",
        options=options,
        index=index,
        format_func=lambda x: NAV_LABELS[x],
        key="app_mode_nav",
        label_visibility="collapsed",
    )


def render_global_data_source(
    *,
    store_exists: bool,
    store_stats: dict[str, Any] | None = None,
    key_prefix: str = "global",
) -> dict[str, Any]:
    """Shared data source selector for analytics modules."""
    st.markdown("**Source de données**")
    use_store = st.checkbox(
        "Utiliser la base persistante",
        value=store_exists,
        disabled=not store_exists,
        key=f"{key_prefix}_use_store",
    )
    db_file = hist_file = None
    if use_store and store_exists and store_stats:
        st.caption(
            f"{store_stats.get('db_tels', 0):,} TEL · "
            f"{store_stats.get('hist_rows', 0):,} lignes histo · "
            f"MAJ {str(store_stats.get('last_update', '—'))[:10]}"
        )
    elif not use_store:
        db_file = st.file_uploader(
            "Base client (DB)",
            type=["xls", "xlsx", "xlsm"],
            key=f"{key_prefix}_db",
        )
        hist_file = st.file_uploader(
            "Historique",
            type=["xls", "xlsx", "xlsm", "csv"],
            key=f"{key_prefix}_hist",
        )
    return {"use_store": use_store and store_exists, "db_file": db_file, "hist_file": hist_file}


def render_section_header(title: str, subtitle: str, *, badge: str | None = None) -> None:
    badge_html = f'<span class="lc-badge">{badge}</span>' if badge else ""
    st.markdown(
        f"""
        <div class="lc-page-hero" style="display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:12px;">
            <div>
                <div class="lc-eyebrow">Lead &amp; Connect Analytics</div>
                <h2 class="lc-title">{title}</h2>
                <p class="lc-subtitle">{subtitle}</p>
            </div>
            {badge_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _fmt(n: int | float) -> str:
    return f"{int(n):,}".replace(",", "\u202f")


def _color_bars_html(top_colors: list[dict[str, Any]]) -> str:
    if not top_colors:
        return f"<p style='color:{TEXT_SECONDARY};font-size:0.8rem'>Aucune donnée couleur</p>"
    max_count = max(c["count"] for c in top_colors) or 1
    rows = []
    for item in top_colors:
        color = color_hex_for_label(item["label"])
        width = min(100, 100 * item["count"] / max_count)
        rows.append(
            f"<div class='color-row'>"
            f"<span class='dot' style='background:{color}'></span>"
            f"<span style='min-width:52px'>{item['label']}</span>"
            f"<div class='bar'><div class='fill' style='width:{width}%;background:{color}'></div></div>"
            f"<span style='min-width:48px;text-align:right;font-weight:600'>{_fmt(item['count'])}</span>"
            f"</div>"
        )
    return f"<div class='color-bars'>{''.join(rows)}</div>"


def _overview_html(metrics: dict[str, Any], *, overview_css: str | None = None) -> str:
    css = overview_css or OVERVIEW_CSS
    store = metrics.get("store", {})
    last_update = str(store.get("last_update", "—"))[:16].replace("T", " ")
    positive = metrics.get("positive_rate_pct")
    positive_txt = f"{positive}%" if positive is not None else "—"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><style>{css}</style></head>
<body><div class="wrap">
<div class="hero">
  <div>
    <div class="eyebrow">Analytics Platform · FÈS</div>
    <h1>Vue d'ensemble<br/><em>Data · Performance · Ventes</em></h1>
    <p>Plateforme tout-en-un — transformez vos exports en insights actionnables pour le recyclage et la conversion.</p>
  </div>
  <div class="badge">MAJ {metrics['generated_at']}</div>
</div>

<div class="quote-strip">
  Great analytics is not just numbers — it's intentional decisions behind every call.
</div>

<div class="kpi-grid">
  <div class="kpi b">
    <div class="num">01</div>
    <div class="kpi-label">Total fiches</div>
    <div class="kpi-val">{_fmt(metrics['total_fiches'])}</div>
    <div class="kpi-sub">Data Client</div>
  </div>
  <div class="kpi g">
    <div class="num">02</div>
    <div class="kpi-label">Exploitables</div>
    <div class="kpi-val">{_fmt(metrics['exploitable_count'])}</div>
    <div class="kpi-sub">{metrics['exploitable_pct']}% du total</div>
  </div>
  <div class="kpi p">
    <div class="num">03</div>
    <div class="kpi-label">Ventes {metrics['year']}</div>
    <div class="kpi-val">{_fmt(metrics['ventes_year_count'])}</div>
    <div class="kpi-sub">{metrics['ventes_year_pct']}% vendus cette année</div>
  </div>
  <div class="kpi o">
    <div class="num">04</div>
    <div class="kpi-label">Contacts actifs</div>
    <div class="kpi-val">{_fmt(metrics['active_contacts'])}</div>
    <div class="kpi-sub">Taux vente {metrics['vente_rate_pct']}%</div>
  </div>
  <div class="kpi r">
    <div class="num">05</div>
    <div class="kpi-label">Obsolètes</div>
    <div class="kpi-val">{_fmt(metrics['stale_count'])}</div>
    <div class="kpi-sub">{metrics['stale_pct']}% · { _fmt(metrics['recyclable_count']) } recyclables</div>
  </div>
  <div class="kpi s">
    <div class="num">06</div>
    <div class="kpi-label">Ventes 7j</div>
    <div class="kpi-val">{_fmt(metrics['recent_ventes_7d'])}</div>
    <div class="kpi-sub">Taux positif {positive_txt}</div>
  </div>
</div>

<div class="panels">
  <div class="panel">
    <div class="panel-title">Base persistante</div>
    <div class="store-grid">
      <div class="store-item"><div class="v">{_fmt(store.get('db_tels', 0))}</div><div class="l">TEL clients</div></div>
      <div class="store-item"><div class="v">{_fmt(store.get('hist_rows', 0))}</div><div class="l">Lignes historique</div></div>
      <div class="store-item"><div class="v">{_fmt(store.get('onoff_rows', 0))}</div><div class="l">Appels Onoff</div></div>
      <div class="store-item"><div class="v" style="font-size:0.85rem">{last_update}</div><div class="l">Dernière fusion</div></div>
    </div>
    <div style="margin-top:16px;font-size:0.78rem;color:{TEXT_SECONDARY}">
      Ventes totales historique : <b>{_fmt(metrics['total_ventes'])}</b> événements ·
      <b>{_fmt(metrics['vente_unique_tels'])}</b> TEL uniques ·
      Inactifs : <b>{_fmt(metrics['inactive_count'])}</b> ({metrics['inactive_pct']}%)
    </div>
  </div>
  <div class="panel">
    <div class="panel-title">Répartition couleurs (top)</div>
    {_color_bars_html(metrics.get('top_colors', []))}
  </div>
</div>

<div class="panel">
  <div class="panel-title">Modules analytics</div>
  <div class="modules">
    <div class="mod"><div class="mod-num">01</div><h3>Data Client</h3><p>KPIs, donuts couleur/statut, chaîne exploitables, filtres année/mois.</p></div>
    <div class="mod"><div class="mod-num">02</div><h3>Performance</h3><p>Conversion vente, parcours statuts, obsolètes, doublons, relances, suivi ventes.</p></div>
    <div class="mod"><div class="mod-num">03</div><h3>Prévisionnel</h3><p>Projection J+1 à J+7, quotas, exclusion Book1, export coloré.</p></div>
    <div class="mod"><div class="mod-num">04</div><h3>Export recyclage</h3><p>Sélection par statut/couleur, quotas, durées Onoff, masque Excel.</p></div>
    <div class="mod"><div class="mod-num">05</div><h3>Base de données</h3><p>Fusion quotidienne, persistance SQLite, filtres FICHIER, export complet.</p></div>
    <div class="mod"><div class="mod-num">06</div><h3>Ventes</h3><p>Suivi quotidien statut d'origine, baseline snapshot, analyse export_data_client.</p></div>
  </div>
</div>
</div></body></html>"""


def render_overview_board(metrics: dict[str, Any], *, height: int = 1380) -> None:
    import importlib
    from ui import brand_theme

    importlib.reload(brand_theme)
    html = _overview_html(metrics, overview_css=brand_theme.OVERVIEW_CSS)
    components.html(html, height=height, scrolling=True)
