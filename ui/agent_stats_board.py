"""Agent statistics panel for Export recyclage."""

from __future__ import annotations

import io
from typing import Any

import pandas as pd
import streamlit as st


def render_agent_statistics(metrics: dict[str, Any]) -> None:
    """Render agent performance tables and quality alerts."""
    st.markdown("### Statistiques agents")
    st.caption(
        f"Période : **{metrics.get('period_label', '—')}** · "
        f"Seuil alerte Refus / Pas de collab : **<{metrics.get('short_call_threshold_sec', 4)} s** · "
        f"Agent = colonne **TV** de l'historique."
    )

    if metrics.get("agent_count", 0) == 0:
        st.info("Aucun appel agent exploitable sur la période sélectionnée.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Agents actifs", f"{metrics['agent_count']:,}")
    c2.metric("Appels analysés", f"{metrics['total_calls']:,}")
    c3.metric("Agents avec alerte", f"{metrics['agents_with_alerts']:,}")
    c4.metric(
        "Appels courts (Refus/Collab)",
        f"{int(metrics['agents_summary']['Appels_Courts_Qualite'].sum()):,}",
    )

    summary = metrics["agents_summary"].copy()
    display = summary[
        [
            "Agent_Affichage",
            "Total_Appels",
            "Statut_Principal",
            "Part_Statut_Principal_%",
            "Refus",
            "Pas_Collaboration",
            "Appels_Courts_Qualite",
            "Taux_Appels_Courts_Qualite_%",
        ]
    ].rename(
        columns={
            "Agent_Affichage": "Agent",
            "Part_Statut_Principal_%": "% statut principal",
            "Appels_Courts_Qualite": "Appels < seuil (Refus/Collab)",
            "Taux_Appels_Courts_Qualite_%": "% courts / (Refus+Collab)",
        }
    )

    st.markdown("**Classement agents — statuts les plus posés**")
    st.dataframe(display, hide_index=True, use_container_width=True)

    with st.expander("Répartition statut × agent (top volumes)", expanded=False):
        mix = metrics.get("top_status_by_agent", pd.DataFrame())
        if mix.empty:
            st.info("Aucune répartition disponible.")
        else:
            st.dataframe(mix, hide_index=True, use_container_width=True)

    with st.expander("Matrice complète statut × agent", expanded=False):
        pivot = metrics.get("status_by_agent", pd.DataFrame())
        if pivot.empty:
            st.info("Aucune matrice disponible.")
        else:
            st.dataframe(pivot, hide_index=True, use_container_width=True)

    detail = metrics.get("quality_detail", pd.DataFrame())
    st.markdown("**Appels Refus / Pas de collaboration avec durée suspecte**")
    if detail.empty:
        st.success("Aucun appel Refus ou Pas de collaboration sous le seuil de durée.")
    else:
        st.warning(
            f"{len(detail):,} appel(s) statué(s) Refus ou Pas de collaboration "
            f"avec une durée inférieure à {metrics.get('short_call_threshold_sec', 4)} secondes."
        )
        show = detail.rename(
            columns={
                "Status_Category": "Statut",
                "DUREE_SEC": "Durée (s)",
            }
        )
        st.dataframe(show, hide_index=True, use_container_width=True)

    with st.expander("Pistes d'évaluation complémentaires", expanded=False):
        st.markdown(
            """
            - **Taux Répondeur** : part des Répondeur vs contacts réels par agent.
            - **Stabilité des statuts** : agents qui changent souvent de statut sur le même TEL.
            - **Durée moyenne par statut** : repérer les Refus/Collab systématiquement très courts.
            - **Évolution hebdo** : comparer les alertes avant/après coaching.
            - **Volume vs qualité** : un agent très productif avec beaucoup d'alertes mérite un focus QA.
            """
        )

    excel_bytes = _agent_stats_workbook(metrics)
    if excel_bytes:
        st.download_button(
            "Télécharger rapport agents (.xlsx)",
            data=excel_bytes,
            file_name="Rapport_Statistiques_Agents.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


def _agent_stats_workbook(metrics: dict[str, Any]) -> bytes | None:
    summary = metrics.get("agents_summary")
    if summary is None or summary.empty:
        return None
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Agents", index=False)
        mix = metrics.get("top_status_by_agent", pd.DataFrame())
        if not mix.empty:
            mix.to_excel(writer, sheet_name="Top statuts", index=False)
        pivot = metrics.get("status_by_agent", pd.DataFrame())
        if not pivot.empty:
            pivot.to_excel(writer, sheet_name="Matrice", index=False)
        detail = metrics.get("quality_detail", pd.DataFrame())
        if not detail.empty:
            detail.to_excel(writer, sheet_name="Alertes duree", index=False)
    buffer.seek(0)
    return buffer.getvalue()
