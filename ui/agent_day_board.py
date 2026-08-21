"""UI for per-agent / per-day performance inside Performance dashboard."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from engine import agent_day_performance as adp


def render_agent_day_performance_panel(
    *,
    df_hist: pd.DataFrame,
    onoff: pd.DataFrame | None = None,
    store_history: pd.DataFrame | None = None,
) -> None:
    """Selectors + KPIs / charts for one agent on one day."""
    st.markdown("**Performance par agent & date**")
    st.caption(
        "Mix des statuts posés (dernier statut du TEL), origines des ventes "
        "(converti depuis…), et erreurs = Pas de collab / Refus avec durée Onoff < 1 min "
        "(durée uniquement Onoff, pas d'historique)."
    )

    options = adp.list_agent_day_options(df_hist)
    agents: list[str] = options.get("agents") or []
    if not agents:
        st.info("Aucun agent trouvé dans l'historique chargé.")
        return

    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        agent = st.selectbox("Agent", options=agents, key="perf_agent_day_agent")
    dates_for_agent: list[date] = options.get("dates_by_agent", {}).get(agent) or options.get("dates") or []
    if not dates_for_agent:
        st.warning(f"Aucune date disponible pour {agent}.")
        return
    with c2:
        day = st.selectbox(
            "Date",
            options=dates_for_agent,
            format_func=lambda d: d.strftime("%d/%m/%Y") if isinstance(d, date) else str(d),
            key="perf_agent_day_date",
        )
    with c3:
        short_sec = st.number_input(
            "Seuil erreur (s)",
            min_value=10,
            max_value=120,
            value=60,
            step=5,
            key="perf_agent_day_short",
        )

    with st.spinner(f"Analyse {agent} · {day}…"):
        result = adp.compute_agent_day_performance(
            df_hist,
            agent=agent,
            day=day,
            onoff=onoff,
            store_history=store_history,
            short_sec=int(short_sec),
            prepared=options.get("prepared"),
        )

    _render_result(result)


def _render_result(result: dict[str, Any]) -> None:
    day_label = result.get("day_label") or result.get("day")
    agent = result.get("agent")
    st.subheader(f"{agent} — {day_label}")

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("TEL uniques", f"{result['tel_uniques']:,}")
    m2.metric("Appels", f"{result['appels']:,}")
    m3.metric("Ventes", f"{result['ventes']:,}")
    m4.metric("Taux", f"{result['taux']}%")
    m5.metric("Pas de collab", f"{result.get('pas_de_collab', 0):,}")
    m6.metric("Refus", f"{result.get('refus', 0):,}")

    err = result.get("errors_summary") or {}
    e1, e2, e3 = st.columns(3)
    e1.metric(
        f"Erreurs Pas collab (<{result.get('short_sec', 60)}s)",
        f"{err.get('Pas_de_collab_lt_1min', 0):,}",
    )
    e2.metric(
        f"Erreurs Refus (<{result.get('short_sec', 60)}s)",
        f"{err.get('Refus_lt_1min', 0):,}",
    )
    e3.metric("Total erreurs", f"{err.get('Total', 0):,}")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Statuts posés (dernier statut / TEL)**")
        mix = result.get("status_mix", pd.DataFrame())
        if mix.empty:
            st.info("Aucun statut.")
        else:
            chart = mix.set_index("Statut")["TEL"]
            st.bar_chart(chart)
            st.dataframe(mix, hide_index=True, use_container_width=True)

    with col_b:
        st.markdown("**Ventes — converti depuis**")
        conv = result.get("conversion_summary", pd.DataFrame())
        detail = result.get("conversions", pd.DataFrame())
        if conv.empty:
            st.info("Aucune vente ce jour pour cet agent.")
        else:
            st.bar_chart(conv.set_index("Depuis")["Ventes"])
            st.dataframe(conv, hide_index=True, use_container_width=True)
            with st.expander("Détail TEL → statut précédent"):
                st.dataframe(detail, hide_index=True, use_container_width=True)

    st.markdown(
        f"**Erreurs** — Pas de collab / Refus avec durée Onoff **< {result.get('short_sec', 60)} s** "
        "(uniquement durée Onoff ; TEL sans match Onoff exclus)"
    )
    errors = result.get("errors", pd.DataFrame())
    if errors is None or errors.empty:
        st.success("Aucune erreur sous le seuil pour ce jour.")
    else:
        st.warning(f"{len(errors):,} TEL en erreur.")
        st.dataframe(errors, hide_index=True, use_container_width=True)
