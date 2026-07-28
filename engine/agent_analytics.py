"""Agent-level statistics from call history (TV + DUREE + STATUS)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from engine.processor import (
    DEFAULT_STATUS_MAPPING,
    TEL_ALIASES,
    _find_column,
    _map_status,
    _normalize_columns,
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
_EMPTY_AGENT_VALUES = {"", "nan", "none", "nat", "0", "0.0", "manual"}


def _find_column_ci(df: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    upper_map = {str(col).strip().upper(): col for col in df.columns}
    for alias in aliases:
        key = alias.upper()
        if key in upper_map:
            return upper_map[key]
    return None


def _normalize_agent_label(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "Non renseigné"
    text = str(value).strip()
    if not text or text.lower() in _EMPTY_AGENT_VALUES:
        return "Non renseigné"
    if text.replace(".", "", 1).isdigit():
        return "Non renseigné"
    return text


def _build_id_tv_agent_map(df: pd.DataFrame) -> dict[int, str]:
    if "ID_TV" not in df.columns:
        return {}
    tv_col = _find_column_ci(df, ("TV",))
    if not tv_col:
        return {}
    mapping: dict[int, str] = {}
    for _, row in df[[tv_col, "ID_TV"]].dropna(subset=["ID_TV"]).iterrows():
        label = _normalize_agent_label(row[tv_col])
        if label == "Non renseigné":
            continue
        try:
            mapping[int(float(row["ID_TV"]))] = label
        except (TypeError, ValueError):
            continue
    return mapping


def _build_tel_agent_map(df_db: pd.DataFrame | None) -> dict[str, str]:
    if df_db is None or df_db.empty:
        return {}
    db = _normalize_columns(df_db.copy())
    tel_col = _find_column_ci(db, TEL_ALIASES)
    agent_col = _find_column_ci(db, AGENT_ALIASES)
    if not tel_col or not agent_col:
        return {}
    out: dict[str, str] = {}
    for _, row in db[[tel_col, agent_col]].iterrows():
        tel = str(row[tel_col]).strip()
        label = _normalize_agent_label(row[agent_col])
        if tel and label != "Non renseigné":
            out[tel] = label
    return out


def _resolve_agent_labels(
    df: pd.DataFrame,
    *,
    id_tv_map: dict[int, str],
    tel_agent_map: dict[str, str],
) -> pd.Series:
    agents = pd.Series("Non renseigné", index=df.index, dtype=object)

    tv_col = _find_column_ci(df, ("TV",))
    if tv_col:
        agents = df[tv_col].map(_normalize_agent_label)

    missing = agents == "Non renseigné"
    if missing.any() and "ID_TV" in df.columns and id_tv_map:
        ids = pd.to_numeric(df.loc[missing, "ID_TV"], errors="coerce")

        def _from_id(value: object) -> str:
            if pd.isna(value):
                return "Non renseigné"
            try:
                return id_tv_map.get(int(float(value)), "Non renseigné")
            except (TypeError, ValueError):
                return "Non renseigné"

        agents.loc[missing] = ids.map(_from_id)
        missing = agents == "Non renseigné"

    if missing.any() and tel_agent_map and "TEL" in df.columns:
        agents.loc[missing] = (
            df.loc[missing, "TEL"]
            .astype(str)
            .str.strip()
            .map(tel_agent_map)
            .fillna("Non renseigné")
        )
        missing = agents == "Non renseigné"

    status_user_col = _find_column_ci(df, ("STATUS_USER",))
    if missing.any() and status_user_col:
        agents.loc[missing] = df.loc[missing, status_user_col].map(_normalize_agent_label)
        agents.loc[missing & (agents == "Non renseigné")] = "Non renseigné"

    return agents


def prepare_agent_history_frame(
    df_hist: pd.DataFrame,
    *,
    df_db: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Normalize history for per-agent analytics."""
    if df_hist.empty:
        return pd.DataFrame()

    out = _normalize_columns(df_hist.copy())
    if "TEL" not in out.columns:
        tel_col = _find_column_ci(out, TEL_ALIASES)
        if tel_col:
            out = out.rename(columns={tel_col: "TEL"})

    if not _find_column_ci(out, AGENT_ALIASES) and not _find_column_ci(
        _normalize_columns(df_db.copy()) if df_db is not None and not df_db.empty else pd.DataFrame(),
        AGENT_ALIASES,
    ):
        raise ValueError(
            "Colonne agent introuvable (attendu : TV dans l'historique ou la base client)."
        )

    id_tv_map = _build_id_tv_agent_map(out)
    tel_agent_map = _build_tel_agent_map(df_db)
    out["Agent"] = _resolve_agent_labels(out, id_tv_map=id_tv_map, tel_agent_map=tel_agent_map)

    if "STATUS" not in out.columns:
        status_col = _find_column_ci(out, ("STATUS", "STATUT", "CODE_STATUS"))
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
    df_db: pd.DataFrame | None = None,
    short_call_threshold_sec: int = DEFAULT_SHORT_CALL_SEC,
    days_back: int | None = None,
) -> dict[str, Any]:
    """Build agent summary, status mix, and quality alerts for Refus / Pas de collab."""
    work = prepare_agent_history_frame(df_hist, df_db=df_db)
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

    threshold = int(short_call_threshold_sec)
    quality_mask = work["Status_Category"].isin(QUALITY_STATUS_LABELS)
    short_quality = quality_mask & (work["DUREE_SEC"] < threshold)

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
        quality_detail["Alerte"] = f"⚠️ < {threshold}s"
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
                "TV",
                "ID_TV",
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
        "short_call_threshold_sec": threshold,
        "agent_count": int(summary["Agent"].nunique()),
        "total_calls": int(len(work)),
        "agents_with_alerts": int((summary["Appels_Courts_Qualite"] > 0).sum()),
    }
