"""Agent-level statistics from call history (TV + DUREE + STATUS)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from engine.processor import (
    DEFAULT_STATUS_MAPPING,
    _find_column,
    _map_status,
    _parse_date_column,
)

AGENT_ALIASES = (
    "TV",
    "STATUS_USER",
    "AGENT",
    "USER",
    "OPERATEUR",
    "CONSEILLER",
    "LOGIN",
    "NOM_AGENT",
)
QUALITY_STATUS_LABELS = ("Refus", "Pas de collaboration")
DEFAULT_SHORT_CALL_SEC = 4


def _normalize_agent_label(value: object) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "nat", "0", "0.0"}:
        return "Non renseigné"
    return text


def prepare_agent_history_frame(df_hist: pd.DataFrame) -> pd.DataFrame:
    """Normalize history for per-agent analytics."""
    if df_hist.empty:
        return pd.DataFrame()

    out = df_hist.copy()
    agent_col = _find_column(out, AGENT_ALIASES)
    if not agent_col:
        raise ValueError(
            "Colonne agent introuvable dans l'historique (attendu : TV)."
        )

    out = out.rename(columns={agent_col: "Agent"})
    out["Agent"] = out["Agent"].map(_normalize_agent_label)

    if "STATUS" not in out.columns:
        status_col = _find_column(out, ("STATUS", "STATUT", "CODE_STATUS"))
        if not status_col:
            raise ValueError("Colonne STATUS introuvable dans l'historique.")
        out = out.rename(columns={status_col: "STATUS"})

    if "DATE" in out.columns:
        out["DATE"] = _parse_date_column(out["DATE"])
        out = out[out["DATE"].notna()].copy()

    if "DUREE" in out.columns:
        out["DUREE_SEC"] = pd.to_numeric(out["DUREE"], errors="coerce").fillna(0).astype(int)
    else:
        out["DUREE_SEC"] = 0

    out["Status_Category"] = _map_status(out["STATUS"], DEFAULT_STATUS_MAPPING)
    out = out[out["Status_Category"].notna()].copy()
    return out.reset_index(drop=True)


def compute_agent_statistics(
    df_hist: pd.DataFrame,
    *,
    short_call_threshold_sec: int = DEFAULT_SHORT_CALL_SEC,
    days_back: int | None = None,
) -> dict[str, Any]:
    """Build agent summary, status mix, and quality alerts for Refus / Pas de collab."""
    work = prepare_agent_history_frame(df_hist)
    if work.empty:
        return {
            "agents_summary": pd.DataFrame(),
            "status_by_agent": pd.DataFrame(),
            "quality_detail": pd.DataFrame(),
            "top_status_by_agent": pd.DataFrame(),
            "period_label": "Aucune donnée",
            "short_call_threshold_sec": short_call_threshold_sec,
            "agent_count": 0,
            "total_calls": 0,
            "agents_with_alerts": 0,
        }

    if days_back and days_back > 0 and "DATE" in work.columns:
        cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=int(days_back))
        work = work[work["DATE"] >= cutoff].copy()
        period_label = f"{days_back} derniers jours"
    else:
        period_label = "Historique complet"

    if work.empty:
        return {
            "agents_summary": pd.DataFrame(),
            "status_by_agent": pd.DataFrame(),
            "quality_detail": pd.DataFrame(),
            "top_status_by_agent": pd.DataFrame(),
            "period_label": period_label,
            "short_call_threshold_sec": short_call_threshold_sec,
            "agent_count": 0,
            "total_calls": 0,
            "agents_with_alerts": 0,
        }

    quality_mask = work["Status_Category"].isin(QUALITY_STATUS_LABELS)
    short_quality = quality_mask & (work["DUREE_SEC"] < int(short_call_threshold_sec))

    status_counts = (
        work.groupby(["Agent", "Status_Category"])
        .size()
        .reset_index(name="Appels")
    )
    status_pivot = (
        status_counts.pivot(index="Agent", columns="Status_Category", values="Appels")
        .fillna(0)
        .astype(int)
        .reset_index()
    )

    agent_totals = work.groupby("Agent").size().reset_index(name="Total_Appels")
    top_status = (
        status_counts.sort_values("Appels", ascending=False)
        .groupby("Agent", as_index=False)
        .first()
        .rename(columns={"Status_Category": "Statut_Principal", "Appels": "Appels_Statut_Principal"})
    )

    refus_counts = (
        work[work["Status_Category"] == "Refus"]
        .groupby("Agent")
        .size()
        .reset_index(name="Refus")
    )
    collab_counts = (
        work[work["Status_Category"] == "Pas de collaboration"]
        .groupby("Agent")
        .size()
        .reset_index(name="Pas_Collaboration")
    )
    short_counts = (
        work[short_quality]
        .groupby("Agent")
        .size()
        .reset_index(name="Appels_Courts_Qualite")
    )

    summary = agent_totals.merge(top_status, on="Agent", how="left")
    summary = summary.merge(refus_counts, on="Agent", how="left")
    summary = summary.merge(collab_counts, on="Agent", how="left")
    summary = summary.merge(short_counts, on="Agent", how="left")
    for col in ("Refus", "Pas_Collaboration", "Appels_Courts_Qualite"):
        summary[col] = summary[col].fillna(0).astype(int)

    summary["Part_Statut_Principal_%"] = (
        summary["Appels_Statut_Principal"] / summary["Total_Appels"] * 100
    ).round(1)
    summary["Taux_Appels_Courts_Qualite_%"] = (
        summary["Appels_Courts_Qualite"]
        / summary[["Refus", "Pas_Collaboration"]].sum(axis=1).replace(0, pd.NA)
        * 100
    ).round(1)
    summary["Taux_Appels_Courts_Qualite_%"] = summary["Taux_Appels_Courts_Qualite_%"].fillna(0)

    summary["Alerte"] = summary["Appels_Courts_Qualite"].apply(
        lambda n: "⚠️" if int(n) > 0 else ""
    )
    summary["Agent_Affichage"] = summary.apply(
        lambda row: f"{row['Alerte']} {row['Agent']}".strip(),
        axis=1,
    )
    summary = summary.sort_values(
        ["Appels_Courts_Qualite", "Total_Appels"],
        ascending=[False, False],
    ).reset_index(drop=True)

    quality_detail = work[short_quality].copy()
    if not quality_detail.empty:
        quality_detail["Alerte"] = "⚠️ < 4s"
        keep = [
            c
            for c in (
                "Agent",
                "Alerte",
                "TEL",
                "DATE",
                "HEURE",
                "Status_Category",
                "DUREE_SEC",
                "DUREE",
                "LIB_STATUS",
                "LIB_DETAIL",
            )
            if c in quality_detail.columns
        ]
        quality_detail = quality_detail[keep].sort_values(
            ["Agent", "DUREE_SEC", "DATE"],
            ascending=[True, True, False],
        )
        if "DATE" in quality_detail.columns:
            quality_detail["DATE"] = quality_detail["DATE"].dt.strftime("%Y-%m-%d")

    top_mix = (
        status_counts.sort_values(["Agent", "Appels"], ascending=[True, False])
        .groupby("Agent", group_keys=False)
        .head(5)
        .reset_index(drop=True)
    )

    return {
        "agents_summary": summary,
        "status_by_agent": status_pivot,
        "quality_detail": quality_detail.reset_index(drop=True),
        "top_status_by_agent": top_mix,
        "period_label": period_label,
        "short_call_threshold_sec": short_call_threshold_sec,
        "agent_count": int(summary["Agent"].nunique()),
        "total_calls": int(len(work)),
        "agents_with_alerts": int((summary["Appels_Courts_Qualite"] > 0).sum()),
    }
