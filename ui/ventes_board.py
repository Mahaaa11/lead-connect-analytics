"""Dedicated Ventes analytics page UI."""

from __future__ import annotations

import io
from typing import Any

import pandas as pd
import streamlit as st

from engine import data_client_dashboard as _dc
from engine.status_labels import collapse_status_table
from ui.brand_theme import NAVY, STATUS_CHART_COLORS

PRIOR_COLOR_DISPLAY_ORDER = getattr(
    _dc,
    "PRIOR_COLOR_DISPLAY_ORDER",
    ["Vert", "Bleu", "Orange", "Rouge", "Sans contact précédent"],
)
STATUS_DISPLAY_ORDER = _dc.STATUS_DISPLAY_ORDER
color_hex_for_label = _dc.color_hex_for_label


def _prepare_chart_df(
    df: pd.DataFrame,
    *,
    label_col: str,
    value_col: str,
    top_n: int | None = None,
    min_share: float | None = None,
    other_label: str = "Autres (reste)",
) -> pd.DataFrame:
    """Keep top categories for charts; roll the long tail into one bar."""
    plot_df = df[[label_col, value_col]].copy()
    plot_df[value_col] = pd.to_numeric(plot_df[value_col], errors="coerce").fillna(0)
    plot_df = plot_df.sort_values(value_col, ascending=False).reset_index(drop=True)
    if plot_df.empty:
        return plot_df

    keep_mask = pd.Series(True, index=plot_df.index)
    if min_share is not None and str(value_col).endswith("%"):
        keep_mask &= plot_df[value_col] >= float(min_share)
    if top_n is not None and top_n > 0:
        keep_mask &= plot_df.index < int(top_n)
    if not keep_mask.any():
        keep_mask.iloc[0] = True

    head = plot_df.loc[keep_mask].copy()
    tail = plot_df.loc[~keep_mask]
    if not tail.empty:
        other_val = float(tail[value_col].sum())
        if other_val > 0:
            head = pd.concat(
                [
                    head,
                    pd.DataFrame([{label_col: other_label, value_col: round(other_val, 2)}]),
                ],
                ignore_index=True,
            )
    return head.reset_index(drop=True)


def _render_colored_bar_chart(
    df: pd.DataFrame,
    *,
    label_col: str,
    value_col: str,
    color_from_label: bool = False,
    y_title: str = "",
    height: int | None = None,
    horizontal: bool = True,
    top_n: int | None = 12,
    min_share: float | None = 1.0,
) -> None:
    """Readable bar chart: horizontal by default, collapsed long tail."""
    import plotly.graph_objects as go

    if df.empty or label_col not in df.columns or value_col not in df.columns:
        return

    plot_df = _prepare_chart_df(
        df,
        label_col=label_col,
        value_col=value_col,
        top_n=top_n,
        min_share=min_share if str(value_col).endswith("%") else None,
    )
    if plot_df.empty:
        return

    if horizontal:
        plot_df = plot_df.sort_values(value_col, ascending=True).reset_index(drop=True)

    n = len(plot_df)
    if color_from_label:
        bar_colors = [color_hex_for_label(str(label)) for label in plot_df[label_col]]
    else:
        bar_colors = [STATUS_CHART_COLORS[i % len(STATUS_CHART_COLORS)] for i in range(n)]
        if horizontal:
            bar_colors = list(reversed(bar_colors))

    labels = plot_df[label_col].astype(str)
    values = plot_df[value_col]
    is_pct = str(value_col).endswith("%")
    text = values.map(lambda v: f"{float(v):.1f}%" if is_pct else f"{int(v):,}")

    if horizontal:
        fig = go.Figure(
            data=[
                go.Bar(
                    y=labels,
                    x=values,
                    orientation="h",
                    marker={"color": bar_colors},
                    text=text,
                    textposition="outside",
                    cliponaxis=False,
                )
            ]
        )
        fig.update_layout(
            height=height or max(320, 36 * n + 80),
            margin={"l": 16, "r": 72, "t": 16, "b": 40},
            xaxis_title=y_title,
            yaxis_title="",
            showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font={"family": "Segoe UI, system-ui, sans-serif", "color": NAVY, "size": 12},
            yaxis={"automargin": True, "tickfont": {"size": 12}},
            xaxis={"gridcolor": "rgba(0,35,78,0.08)", "zeroline": False},
        )
    else:
        fig = go.Figure(
            data=[
                go.Bar(
                    x=labels,
                    y=values,
                    marker={"color": bar_colors},
                    text=text,
                    textposition="outside",
                    cliponaxis=False,
                )
            ]
        )
        fig.update_layout(
            height=height or 380,
            margin={"l": 24, "r": 16, "t": 24, "b": 100},
            xaxis_title="",
            yaxis_title=y_title,
            showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font={"family": "Segoe UI, system-ui, sans-serif", "color": NAVY},
            xaxis={"tickangle": -30, "automargin": True},
        )

    st.plotly_chart(fig, use_container_width=True)
    if top_n is not None or (min_share is not None and is_pct):
        bits = ["Graphique : top catégories"]
        if min_share is not None and is_pct:
            bits.append(f"≥ {min_share:g} %")
        if top_n is not None:
            bits.append(f"max {top_n}")
        st.caption(" · ".join(bits) + " — détail complet dans le tableau.")


def _export_ventes_excel(metrics: dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame(
            {
                "Indicateur": [
                    "Ventes (événements)",
                    "TEL uniques vendus",
                    "Taux vente / base TEL",
                    "Sans statut précédent",
                ],
                "Valeur": [
                    metrics["total_ventes"],
                    metrics["ventes_unique_tels"],
                    f"{metrics['overall_vente_rate_pct']}%",
                    metrics["ventes_sans_statut_precedent"],
                ],
            }
        ).to_excel(writer, sheet_name="KPIs", index=False)
        metrics["conversion_by_prior_status"].to_excel(writer, sheet_name="Par_statut", index=False)
        metrics["conversion_by_prior_color"].to_excel(writer, sheet_name="Par_couleur", index=False)
        metrics.get("autre_breakdown", pd.DataFrame()).to_excel(writer, sheet_name="Detail_Autre", index=False)
        metrics.get("unmapped_status_catalog", pd.DataFrame()).to_excel(
            writer, sheet_name="Codes_hors_mapping", index=False
        )
        metrics.get("status_code_catalog", pd.DataFrame()).to_excel(
            writer, sheet_name="Catalogue_statuts", index=False
        )
        metrics["status_color_matrix"].to_excel(writer, sheet_name="Statut_x_Couleur", index=False)
        detail = metrics.get("vente_detail", pd.DataFrame())
        if not detail.empty:
            detail.to_excel(writer, sheet_name="Detail", index=False)
    buffer.seek(0)
    return buffer.getvalue()


def render_ventes_page(metrics: dict[str, Any]) -> bytes | None:
    """Render the dedicated ventes analytics page."""
    if metrics["total_ventes"] == 0:
        st.warning("Aucune vente trouvée pour la période et les filtres sélectionnés.")
        return None

    period = f"{metrics['year']}"
    if metrics.get("month"):
        period += f" · mois {metrics['month']}"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ventes", f"{metrics['total_ventes']:,}")
    c2.metric("TEL uniques", f"{metrics['ventes_unique_tels']:,}")
    c3.metric("Taux / base TEL", f"{metrics['overall_vente_rate_pct']}%")
    c4.metric("Sans statut précédent", f"{metrics['ventes_sans_statut_precedent']:,}")
    st.caption(f"Période : **{period}** · MAJ {metrics['generated_at']}")

    tab_origine, tab_codes, tab_matrix, tab_jour, tab_detail = st.tabs(
        [
            "Origine (statut & couleur)",
            "Codes hors mapping",
            "Matrice statut × couleur",
            "Ventes par jour",
            "Détail des ventes",
        ]
    )

    with tab_origine:
        by_status = metrics.get("conversion_by_prior_status", pd.DataFrame())
        by_color = metrics.get("conversion_by_prior_color", pd.DataFrame())

        st.markdown("**Quel statut mène à la vente ?**")
        st.caption(
            "Statuts regroupés par nom (ex. tous les « Répondeur », avec ou sans sous-code). "
            f"Encore « Autre » : **{metrics.get('ventes_autre_categorie', 0):,}**."
        )
        if not by_status.empty:
            by_status = collapse_status_table(by_status, "Statut_précédent")
            value_col = "Part_des_ventes_%" if "Part_des_ventes_%" in by_status.columns else "Ventes"
            _render_colored_bar_chart(
                by_status,
                label_col="Statut_précédent",
                value_col=value_col,
                color_from_label=False,
                y_title="% des ventes" if value_col == "Part_des_ventes_%" else "Ventes",
                horizontal=True,
                top_n=10,
                min_share=1.0,
            )
            with st.expander("Tableau complet des statuts", expanded=False):
                st.dataframe(by_status, hide_index=True, use_container_width=True)
        else:
            st.info("Pas de données statut précédent.")

        st.markdown("**Quelle couleur mène à la vente ?**")
        st.caption(
            "Couleur du contact avant la vente (ancienneté du dernier contact). "
            "« Sans contact précédent » = aucun appel antérieur dans l'historique."
        )
        if not by_color.empty:
            value_col = "Part_des_ventes_%" if "Part_des_ventes_%" in by_color.columns else "Ventes"
            _render_colored_bar_chart(
                by_color,
                label_col="Couleur_précédente",
                value_col=value_col,
                color_from_label=True,
                y_title="% des ventes" if value_col == "Part_des_ventes_%" else "Ventes",
                horizontal=True,
                top_n=None,
                min_share=None,
            )
            with st.expander("Tableau des couleurs", expanded=False):
                st.dataframe(by_color, hide_index=True, use_container_width=True)
        else:
            st.info("Pas de données couleur précédente.")

    with tab_codes:
        st.markdown("**Codes STATUS hors mapping — vrais noms**")
        st.caption(
            "Codes absents du mapping standard (ex. **193**, **103**, **102**…) "
            "avec leur libellé **LIB_DETAIL** et sous-statut **STATUS_STATUS**."
        )
        autre = metrics.get("autre_breakdown", pd.DataFrame())
        catalog = metrics.get("unmapped_status_catalog", pd.DataFrame())

        if not catalog.empty:
            st.dataframe(catalog, hide_index=True, use_container_width=True)
            st.markdown("**Principaux libellés LIB_DETAIL observés**")
            details = catalog[catalog["LIB_DETAIL_principal"].astype(str).str.len() > 0]
            if not details.empty:
                st.dataframe(
                    details[["Code_STATUS", "LIB_DETAIL_principal", "Occurrences"]],
                    hide_index=True,
                    use_container_width=True,
                )
        else:
            st.info("Tous les codes sont couverts par le mapping.")

        if not autre.empty:
            st.markdown("**Ventes encore classées « Autre » (détail)**")
            st.dataframe(autre, hide_index=True, use_container_width=True)

    with tab_matrix:
        st.markdown("**Matrice : statut précédent × couleur précédente**")
        st.caption("Montre quels couples statut/couleur produisent le plus de ventes.")
        matrix = metrics.get("status_color_matrix", pd.DataFrame())
        if not matrix.empty:
            pivot = matrix.pivot_table(
                index="Statut_précédent",
                columns="Couleur_précédente",
                values="Ventes",
                fill_value=0,
                aggfunc="sum",
            )
            for col in PRIOR_COLOR_DISPLAY_ORDER:
                if col not in pivot.columns:
                    pivot[col] = 0
            ordered_cols = [c for c in PRIOR_COLOR_DISPLAY_ORDER if c in pivot.columns]
            extra_cols = [c for c in pivot.columns if c not in ordered_cols]
            pivot = pivot[ordered_cols + extra_cols]
            st.dataframe(pivot.astype(int), use_container_width=True)
            top_pairs = matrix.nlargest(15, "Ventes")
            st.bar_chart(top_pairs.set_index("Statut_précédent")["Ventes"])
        else:
            st.info("Matrice vide pour ces filtres.")

    with tab_jour:
        by_day = metrics.get("ventes_by_day", pd.DataFrame())
        if not by_day.empty:
            st.line_chart(by_day.set_index("Date")["Ventes"])
            st.dataframe(by_day, hide_index=True, use_container_width=True)
        else:
            st.info("Pas de ventes par jour.")

    with tab_detail:
        detail = metrics.get("vente_detail", pd.DataFrame())
        if not detail.empty:
            show = [
                c
                for c in [
                    "Date_vente",
                    "TEL",
                    "Code_avant_vente",
                    "Libellé_avant_vente",
                    "LIB_DETAIL_avant",
                    "Sous_statut_avant",
                    "Catégorie_avant_vente",
                    "Couleur_avant_vente",
                ]
                if c in detail.columns
            ]
            st.dataframe(detail[show].head(1000), hide_index=True, use_container_width=True)
            st.caption(f"{len(detail):,} vente(s) au total — affichage limité à 1 000 lignes.")
        else:
            st.info("Pas de détail disponible.")

    return _export_ventes_excel(metrics)
