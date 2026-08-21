"""Per-agent / per-day performance: status mix, conversions, short-call errors."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd

from engine.agent_analytics import _normalize_agent_label
from engine.dashboard import SALE_STATUS_CODE
from engine.processor import (
    _clean_tel_db,
    _format_duration,
    _normalize_columns,
    last_onoff_call_durations,
)
from engine.status_labels import apply_resolved_status_labels, group_status_label

ERROR_STATUSES = ("Pas de collaboration", "Refus")
DEFAULT_SHORT_SEC = 60


def fold_agent(label: object) -> str:
    text = _normalize_agent_label(label)
    if text == "Non renseigné":
        return text
    parts = text.split()
    if len(parts) >= 2 and parts[0].casefold() == parts[1].casefold():
        return parts[0]
    return text


def _prepare_history(df_hist: pd.DataFrame) -> pd.DataFrame:
    if df_hist is None or df_hist.empty:
        return pd.DataFrame()
    df = df_hist.copy()
    # Already normalized daily_tracking frames may have TEL_DB / Status_Label / DATETIME
    if "TEL" not in df.columns and "TEL_DB" in df.columns:
        df["TEL"] = df["TEL_DB"]
    if "TEL" not in df.columns:
        df = _normalize_columns(df)
    if "TEL" not in df.columns:
        return pd.DataFrame()

    df["TEL"] = _clean_tel_db(df["TEL"].astype(str))
    agent_col = "TV" if "TV" in df.columns else None
    if agent_col is None:
        for cand in ("STATUS_USER", "AGENT"):
            if cand in df.columns:
                agent_col = cand
                break
    df["Agent"] = df[agent_col].map(fold_agent) if agent_col else "Non renseigné"

    if "Status_Label" not in df.columns:
        df["Status_Label"] = apply_resolved_status_labels(df)
    df["Status_Group"] = df["Status_Label"].map(group_status_label)

    if "DATETIME" not in df.columns:
        if "DATE" in df.columns:
            dates = pd.to_datetime(df["DATE"].astype(str), format="%Y%m%d", errors="coerce")
            if dates.isna().all():
                dates = pd.to_datetime(df["DATE"], errors="coerce")
            hours = (
                df["HEURE"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(4)
                if "HEURE" in df.columns
                else "0000"
            )
            df["DATETIME"] = pd.to_datetime(
                dates.dt.strftime("%Y-%m-%d") + " " + hours.str[:2] + ":" + hours.str[2:4],
                errors="coerce",
            )
        else:
            df["DATETIME"] = pd.NaT

    if "DATE_ONLY" not in df.columns:
        df["DATE_ONLY"] = pd.to_datetime(df["DATETIME"], errors="coerce").dt.date

    if "DUREE" in df.columns and "DUREE_SEC" not in df.columns:
        df["DUREE_SEC"] = pd.to_numeric(df["DUREE"], errors="coerce").fillna(0).astype(int)
    elif "DUREE_SEC" not in df.columns:
        df["DUREE_SEC"] = 0

    if "HEURE" in df.columns:
        df["_h"] = pd.to_numeric(df["HEURE"], errors="coerce").fillna(0)
    else:
        df["_h"] = 0
    return df


def list_agent_day_options(df_hist: pd.DataFrame) -> dict[str, Any]:
    """Agents and available dates from history."""
    work = _prepare_history(df_hist)
    if work.empty:
        return {"agents": [], "dates": [], "dates_by_agent": {}}
    work = work[work["Agent"] != "Non renseigné"]
    agents = sorted(work["Agent"].dropna().unique().tolist())
    dates = sorted(
        {d for d in work["DATE_ONLY"].dropna().tolist() if isinstance(d, date)},
        reverse=True,
    )
    dates_by_agent: dict[str, list[date]] = {}
    for ag, g in work.groupby("Agent"):
        dates_by_agent[str(ag)] = sorted(
            {d for d in g["DATE_ONLY"].dropna().tolist() if isinstance(d, date)},
            reverse=True,
        )
    return {
        "agents": agents,
        "dates": dates,
        "dates_by_agent": dates_by_agent,
        "prepared": work,
    }


def _onoff_duration_map(onoff: pd.DataFrame | None, day: date | None = None) -> dict[str, int]:
    if onoff is None or onoff.empty or "TEL" not in onoff.columns:
        return {}
    calls = onoff.copy()
    calls["TEL"] = _clean_tel_db(calls["TEL"].astype(str))
    if day is not None and "CALL_DATE" in calls.columns:
        d = pd.to_datetime(calls["CALL_DATE"], errors="coerce")
        filtered = calls[d.dt.date == day]
        if not filtered.empty:
            calls = filtered
    last = last_onoff_call_durations(calls)
    if last.empty:
        return {}
    return dict(
        zip(
            last["TEL"].astype(str),
            pd.to_numeric(last["Duree_Dernier_Appel_Sec"], errors="coerce").fillna(0).astype(int),
        )
    )


def _prior_for_ventes(
    ventes: pd.DataFrame,
    day_hist: pd.DataFrame,
    store_history: pd.DataFrame | None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    hist = pd.DataFrame()
    if store_history is not None and not store_history.empty:
        hist = store_history.copy()
        if "TEL" not in hist.columns:
            hist = _normalize_columns(hist)
        if "TEL" in hist.columns:
            hist["TEL"] = _clean_tel_db(hist["TEL"].astype(str))
            if "Status_Label" not in hist.columns:
                hist["Status_Label"] = apply_resolved_status_labels(hist)
            hist["Status_Group"] = hist["Status_Label"].map(group_status_label)
            if "DATETIME" not in hist.columns and "DATE" in hist.columns:
                dcol = hist["DATE"].astype(str).str.replace(r"\.0$", "", regex=True)
                hcol = (
                    hist["HEURE"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(4)
                    if "HEURE" in hist.columns
                    else "0000"
                )
                hist["DATETIME"] = pd.to_datetime(
                    dcol + hcol + "00", format="%Y%m%d%H%M%S", errors="coerce"
                )

    for _, row in ventes.iterrows():
        tel = str(row["TEL"])
        prior = "Sans contact précédent"
        if not hist.empty:
            g = hist[hist["TEL"] == tel].sort_values("DATETIME")
            is_v = pd.to_numeric(g.get("STATUS", pd.Series(dtype=float)), errors="coerce") == int(
                SALE_STATUS_CODE
            )
            vg = g[is_v]
            if not vg.empty:
                t0 = vg.iloc[-1]["DATETIME"]
                before = g[
                    (g["DATETIME"] < t0)
                    & (pd.to_numeric(g["STATUS"], errors="coerce") != int(SALE_STATUS_CODE))
                ]
                if not before.empty:
                    prior = str(before.iloc[-1]["Status_Group"])
        if prior == "Sans contact précédent" and not day_hist.empty:
            gh = day_hist[day_hist["TEL"] == tel].sort_values(["DATETIME", "_h"])
            is_v = pd.to_numeric(gh.get("STATUS", pd.Series(dtype=float)), errors="coerce") == int(
                SALE_STATUS_CODE
            )
            if is_v.any():
                idx = is_v[is_v].index[0]
                before = gh.loc[:idx].iloc[:-1]
                before = before[
                    pd.to_numeric(before.get("STATUS", pd.Series(dtype=float)), errors="coerce")
                    != int(SALE_STATUS_CODE)
                ]
                if not before.empty:
                    prior = str(before.iloc[-1]["Status_Group"])
        rows.append({"TEL": tel, "Prior": prior})
    return pd.DataFrame(rows)


def compute_agent_day_performance(
    df_hist: pd.DataFrame,
    *,
    agent: str,
    day: date | datetime | str,
    onoff: pd.DataFrame | None = None,
    store_history: pd.DataFrame | None = None,
    short_sec: int = DEFAULT_SHORT_SEC,
    prepared: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Performance snapshot for one agent on one calendar day."""
    work = prepared if prepared is not None else _prepare_history(df_hist)
    if isinstance(day, datetime):
        day_d = day.date()
    elif isinstance(day, date):
        day_d = day
    else:
        day_d = pd.to_datetime(day, errors="coerce")
        day_d = day_d.date() if pd.notna(day_d) else None

    empty = {
        "agent": agent,
        "day": day_d.isoformat() if day_d else str(day),
        "tel_uniques": 0,
        "appels": 0,
        "ventes": 0,
        "taux": 0.0,
        "status_mix": pd.DataFrame(columns=["Statut", "TEL", "Part_%"]),
        "conversions": pd.DataFrame(columns=["TEL", "Prior"]),
        "conversion_summary": pd.DataFrame(columns=["Depuis", "Ventes"]),
        "errors": pd.DataFrame(),
        "errors_summary": {"Pas_de_collab_lt_1min": 0, "Refus_lt_1min": 0, "Total": 0},
        "short_sec": short_sec,
    }
    if work.empty or day_d is None:
        return empty

    day_all = work[work["DATE_ONLY"] == day_d].copy()
    day_ag = day_all[day_all["Agent"] == agent].copy()
    if day_ag.empty:
        return empty

    # Last status per TEL for this agent that day
    last = day_ag.sort_values(["DATETIME", "_h"]).groupby("TEL", as_index=False).tail(1).copy()

    # Ventes: STATUS=1 on agent's TELs that day (any row), attribute to agent of last call or vente row
    vente_mask = pd.to_numeric(day_ag.get("STATUS", pd.Series(dtype=float)), errors="coerce") == int(
        SALE_STATUS_CODE
    )
    vente_tels = set(day_ag.loc[vente_mask, "TEL"].astype(str))
    # Also mark last status as Vente when TEL sold
    last = last.copy()
    last.loc[last["TEL"].isin(vente_tels), "Status_Group"] = "Vente"

    mix = (
        last["Status_Group"]
        .value_counts()
        .rename_axis("Statut")
        .reset_index(name="TEL")
    )
    total_tel = int(len(last))
    mix["Part_%"] = (100 * mix["TEL"] / max(total_tel, 1)).round(1)

    ventes_df = last[last["Status_Group"] == "Vente"][["TEL"]].drop_duplicates()
    priors = (
        _prior_for_ventes(ventes_df, day_ag, store_history)
        if not ventes_df.empty
        else pd.DataFrame(columns=["TEL", "Prior"])
    )
    if not priors.empty:
        conv_sum = (
            priors["Prior"]
            .value_counts()
            .rename_axis("Depuis")
            .reset_index(name="Ventes")
        )
    else:
        conv_sum = pd.DataFrame(columns=["Depuis", "Ventes"])

    dur_map = _onoff_duration_map(onoff, day_d)
    error_rows: list[dict[str, Any]] = []
    for _, row in last[last["Status_Group"].isin(ERROR_STATUSES)].iterrows():
        tel = str(row["TEL"])
        sec = dur_map.get(tel)
        if sec is None:
            continue  # durée uniquement depuis Onoff
        if sec < int(short_sec):
            error_rows.append(
                {
                    "TEL": tel,
                    "Statut": row["Status_Group"],
                    "Duree_sec": int(sec),
                    "Duree": _format_duration(int(sec)),
                }
            )
    errors = pd.DataFrame(error_rows)
    if not errors.empty:
        errors = errors.sort_values(["Statut", "Duree_sec", "TEL"])

    pc_err = int((errors["Statut"] == "Pas de collaboration").sum()) if not errors.empty else 0
    rf_err = int((errors["Statut"] == "Refus").sum()) if not errors.empty else 0

    return {
        "agent": agent,
        "day": day_d.isoformat(),
        "day_label": day_d.strftime("%d/%m/%Y"),
        "tel_uniques": total_tel,
        "appels": int(len(day_ag)),
        "ventes": int(len(vente_tels)),
        "taux": round(100 * len(vente_tels) / max(total_tel, 1), 2),
        "status_mix": mix,
        "conversions": priors,
        "conversion_summary": conv_sum,
        "errors": errors,
        "errors_summary": {
            "Pas_de_collab_lt_1min": pc_err,
            "Refus_lt_1min": rf_err,
            "Total": pc_err + rf_err,
        },
        "short_sec": short_sec,
        "pas_de_collab": int((last["Status_Group"] == "Pas de collaboration").sum()),
        "refus": int((last["Status_Group"] == "Refus").sum()),
        "raccroche": int((last["Status_Group"] == "Raccroche au nez").sum()),
        "repondeur": int((last["Status_Group"] == "Répondeur").sum()),
    }
