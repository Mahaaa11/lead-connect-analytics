"""Daily recyclage campaign analysis: DC (status × color) × histo outcomes."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from engine.agent_day_performance import fold_agent
from engine.dashboard import SALE_STATUS_CODE
from engine.processor import (
    _clean_tel_db,
    _format_duration,
    last_onoff_call_durations,
)
from engine.status_labels import apply_resolved_status_labels, group_status_label

ERROR_STATUSES = ("Pas de collaboration", "Refus")
SHORT_SEC = 60

# Recommended daily mix (share of file) for vente maximization
RECOMMENDED_MIX = {
    "Répondeur|Red": 0.60,
    "Pas de collaboration|Orange": 0.22,
    "Rappel Personnel|Red": 0.05,
    "A Relancer|Red": 0.03,
    "A Relancer|Orange": 0.02,
    "Other": 0.08,
}


def _parse_day(day: date | datetime | str | int) -> date:
    if isinstance(day, datetime):
        return day.date()
    if isinstance(day, date):
        return day
    if isinstance(day, int):
        s = str(day)
        return datetime.strptime(s, "%Y%m%d").date()
    text = str(day).strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"Invalid day: {day}")
    return parsed.date()


def _day_code(d: date) -> int:
    return int(d.strftime("%Y%m%d"))


def load_dc_file(path: str | Path) -> pd.DataFrame:
    """Load a DC / Data Client export (flat sheet or status sheets with header row TEL)."""
    path = Path(path)
    xl = pd.ExcelFile(path)
    frames: list[pd.DataFrame] = []
    for sheet in xl.sheet_names:
        raw = pd.read_excel(path, sheet_name=sheet, header=None)
        hdr = None
        for i, row in raw.iterrows():
            vals = [str(v).strip() for v in row.tolist()[:12]]
            if vals and vals[0] == "TEL":
                hdr = int(i)
                break
        if hdr is None:
            # try normal header
            df = pd.read_excel(path, sheet_name=sheet)
            if "TEL" not in df.columns:
                continue
        else:
            df = pd.read_excel(path, sheet_name=sheet, header=hdr)
        if "TEL" not in df.columns:
            continue
        frames.append(df)
    if not frames:
        raise ValueError(f"No TEL sheet found in {path}")
    out = pd.concat(frames, ignore_index=True)
    out["TEL"] = _clean_tel_db(out["TEL"].astype(str))
    out = out[out["TEL"].ne("")].drop_duplicates("TEL", keep="first")
    if "Status_Category" not in out.columns and "LIB_STATUS" in out.columns:
        out["Status_Category"] = out["LIB_STATUS"].map(group_status_label)
    if "Status_Category" in out.columns:
        out["Status_Category"] = out["Status_Category"].map(group_status_label)
    if "Color" not in out.columns:
        out["Color"] = "Unknown"
    if "Days_Since_Last_Call" not in out.columns:
        out["Days_Since_Last_Call"] = pd.NA
    out["Bucket"] = (
        out["Status_Category"].astype(str).str.strip()
        + "|"
        + out["Color"].astype(str).str.strip()
    )
    return out.reset_index(drop=True)


def _prepare_hist(df_hist: pd.DataFrame) -> pd.DataFrame:
    df = df_hist.copy()
    if "TEL" not in df.columns:
        from engine.processor import _normalize_columns

        df = _normalize_columns(df)
    df["TEL"] = _clean_tel_db(df["TEL"].astype(str))
    df["DATE_N"] = pd.to_numeric(
        df["DATE"].astype(str).str.replace(r"\.0$", "", regex=True), errors="coerce"
    )
    df["STATUS_N"] = pd.to_numeric(df.get("STATUS"), errors="coerce")
    df["_h"] = pd.to_numeric(df.get("HEURE"), errors="coerce").fillna(0)
    df["Agent"] = df["TV"].map(fold_agent) if "TV" in df.columns else "Non renseigné"
    if "Status_Label" not in df.columns:
        df["Status_Label"] = apply_resolved_status_labels(df)
    df["Status_Group"] = df["Status_Label"].map(group_status_label)
    if "DUREE" in df.columns and "DUREE_SEC" not in df.columns:
        df["DUREE_SEC"] = pd.to_numeric(df["DUREE"], errors="coerce").fillna(0).astype(int)
    elif "DUREE_SEC" not in df.columns:
        df["DUREE_SEC"] = 0
    return df.sort_values(["TEL", "DATE_N", "_h"])


def _onoff_map(onoff: pd.DataFrame | None, day: date) -> dict[str, int]:
    if onoff is None or onoff.empty or "TEL" not in onoff.columns:
        return {}
    calls = onoff.copy()
    calls["TEL"] = _clean_tel_db(calls["TEL"].astype(str))
    if "CALL_DATE" in calls.columns:
        cd = pd.to_datetime(calls["CALL_DATE"], errors="coerce")
        filt = calls[cd.dt.date == day]
        if not filt.empty:
            calls = filt
    last = last_onoff_call_durations(calls)
    if last.empty:
        return {}
    return dict(
        zip(
            last["TEL"].astype(str),
            pd.to_numeric(last["Duree_Dernier_Appel_Sec"], errors="coerce")
            .fillna(0)
            .astype(int),
        )
    )


def compute_daily_campaign(
    dc: pd.DataFrame,
    df_hist: pd.DataFrame,
    *,
    day: date | datetime | str | int,
    onoff: pd.DataFrame | None = None,
    short_sec: int = SHORT_SEC,
    target_size: int | None = None,
) -> dict[str, Any]:
    """Analyze one campaign day: mix, clearance, conversions by status×color, agents."""
    day_d = _parse_day(day)
    day_n = _day_code(day_d)
    hist = _prepare_hist(df_hist)
    dc = dc.copy()
    dc["TEL"] = _clean_tel_db(dc["TEL"].astype(str))

    day_hist = hist[hist["DATE_N"] == day_n].copy()
    called = set(day_hist["TEL"].astype(str))
    vente_tels = set(
        day_hist.loc[day_hist["STATUS_N"] == int(SALE_STATUS_CODE), "TEL"].astype(str)
    )

    last_day = (
        day_hist.groupby("TEL", as_index=False)
        .tail(1)[["TEL", "Status_Group", "Agent", "_h"]]
        .rename(columns={"Status_Group": "Outcome", "Agent": "Agent_Outcome"})
    )
    last_day = last_day.copy()
    last_day.loc[last_day["TEL"].isin(vente_tels), "Outcome"] = "Vente"
    vente_agent = (
        day_hist[day_hist["STATUS_N"] == 1]
        .groupby("TEL", as_index=False)
        .tail(1)[["TEL", "Agent"]]
        .rename(columns={"Agent": "Agent_Vente"})
    )
    last_day = last_day.merge(vente_agent, on="TEL", how="left")
    last_day["Agent"] = last_day["Agent_Vente"].fillna(last_day["Agent_Outcome"])

    merged = dc.merge(last_day, on="TEL", how="left")
    merged["Called"] = merged["TEL"].isin(called)
    merged["Outcome"] = merged["Outcome"].fillna("Non rappelé")
    merged["Agent"] = merged["Agent"].fillna("")

    # Mix DC
    mix = (
        merged.groupby(["Status_Category", "Color"], dropna=False)
        .agg(TEL=("TEL", "count"), Appeles=("Called", "sum"), Ventes=("Outcome", lambda s: int((s == "Vente").sum())))
        .reset_index()
    )
    mix["Part_%"] = (100 * mix["TEL"] / max(len(merged), 1)).round(1)
    mix["Clearance_%"] = (100 * mix["Appeles"] / mix["TEL"].clip(lower=1)).round(1)
    mix["Taux_vente_%"] = (100 * mix["Ventes"] / mix["Appeles"].clip(lower=1)).round(2)
    mix["Bucket"] = mix["Status_Category"].astype(str) + "|" + mix["Color"].astype(str)
    mix = mix.sort_values(["Ventes", "TEL"], ascending=[False, False])

    # Conversion matrix prior bucket → outcome (called only)
    called_df = merged[merged["Called"]].copy()
    conv = (
        pd.crosstab(
            called_df["Bucket"],
            called_df["Outcome"],
            margins=True,
        )
        if not called_df.empty
        else pd.DataFrame()
    )

    # Bucket performance
    bucket_perf = mix.copy()
    bucket_perf = bucket_perf.sort_values("Taux_vente_%", ascending=False)

    # Clearance / KPIs
    n_dc = len(merged)
    n_called = int(merged["Called"].sum())
    n_ventes = int((merged["Outcome"] == "Vente").sum())
    clearance = round(100 * n_called / max(n_dc, 1), 1)
    taux = round(100 * n_ventes / max(n_called, 1), 2)

    # Errors <1min among day's last status (all called, not only DC)
    dur_map = _onoff_map(onoff, day_d)
    err_rows: list[dict[str, Any]] = []
    if not last_day.empty:
        for _, row in last_day[last_day["Outcome"].isin(ERROR_STATUSES)].iterrows():
            tel = str(row["TEL"])
            sec = dur_map.get(tel)
            if sec is None:
                continue
            if sec < int(short_sec):
                err_rows.append(
                    {
                        "TEL": tel,
                        "Agent": row["Agent"],
                        "Statut": row["Outcome"],
                        "Duree_sec": int(sec),
                        "Duree": _format_duration(int(sec)),
                    }
                )
    errors = pd.DataFrame(err_rows)
    err_by_agent = (
        errors.groupby("Agent").size().rename("Err_lt_1min").reset_index()
        if not errors.empty
        else pd.DataFrame(columns=["Agent", "Err_lt_1min"])
    )

    # Agents: from DC-called
    agent_rows = []
    for ag, g in called_df[called_df["Agent"] != ""].groupby("Agent"):
        if ag == "Non renseigné":
            continue
        agent_rows.append(
            {
                "Agent": ag,
                "TEL": len(g),
                "Ventes": int((g["Outcome"] == "Vente").sum()),
                "Taux_%": round(100 * (g["Outcome"] == "Vente").sum() / max(len(g), 1), 2),
                "Répondeur": int((g["Outcome"] == "Répondeur").sum()),
                "Pas_collab": int((g["Outcome"] == "Pas de collaboration").sum()),
                "Refus": int((g["Outcome"] == "Refus").sum()),
                "Raccroche": int((g["Outcome"] == "Raccroche au nez").sum()),
            }
        )
    agents = pd.DataFrame(agent_rows).sort_values(["Ventes", "TEL"], ascending=[False, False])
    if not agents.empty and not err_by_agent.empty:
        agents = agents.merge(err_by_agent, on="Agent", how="left")
        agents["Err_lt_1min"] = agents["Err_lt_1min"].fillna(0).astype(int)

    # Suggested mix vs actual (top buckets)
    target = int(target_size or n_dc or 1800)
    suggested = []
    for bucket, share in RECOMMENDED_MIX.items():
        suggested.append(
            {
                "Bucket": bucket,
                "Share_reco_%": round(100 * share, 1),
                "Volume_reco": int(round(target * share)),
                "Volume_actuel": int((merged["Bucket"] == bucket).sum())
                if bucket != "Other"
                else int(
                    (~merged["Bucket"].isin([b for b in RECOMMENDED_MIX if b != "Other"])).sum()
                ),
            }
        )
    suggested_df = pd.DataFrame(suggested)
    suggested_df["Ecart"] = suggested_df["Volume_actuel"] - suggested_df["Volume_reco"]

    # Ventes detail from DC
    ventes_detail = merged[merged["Outcome"] == "Vente"][
        [
            c
            for c in [
                "TEL",
                "Status_Category",
                "Color",
                "Days_Since_Last_Call",
                "Bucket",
                "Agent",
            ]
            if c in merged.columns
        ]
    ].copy()

    # Non rappelés by bucket (clearance leak)
    non_rappeles = (
        merged[~merged["Called"]]
        .groupby(["Status_Category", "Color"], dropna=False)
        .size()
        .rename("Non_rappeles")
        .reset_index()
        .sort_values("Non_rappeles", ascending=False)
    )

    kpis = {
        "day": day_d.isoformat(),
        "day_label": day_d.strftime("%d/%m/%Y"),
        "dc_tels": n_dc,
        "called": n_called,
        "clearance_pct": clearance,
        "ventes": n_ventes,
        "taux_pct": taux,
        "errors_lt_1min": int(len(errors)),
        "short_sec": short_sec,
        "target_size": target,
    }

    return {
        "kpis": kpis,
        "mix": mix,
        "bucket_perf": bucket_perf,
        "conversions": conv,
        "agents": agents,
        "errors": errors,
        "err_by_agent": err_by_agent,
        "suggested_mix": suggested_df,
        "ventes_detail": ventes_detail,
        "non_rappeles": non_rappeles,
        "merged": merged,
    }


def export_daily_campaign_excel(result: dict[str, Any], out_path: str | Path) -> Path:
    out_path = Path(out_path)
    k = result["kpis"]
    resume = pd.DataFrame(
        [
            {"Metrique": "Date", "Valeur": k["day_label"]},
            {"Metrique": "TEL_DC", "Valeur": k["dc_tels"]},
            {"Metrique": "Appeles", "Valeur": k["called"]},
            {"Metrique": "Clearance_%", "Valeur": k["clearance_pct"]},
            {"Metrique": "Ventes", "Valeur": k["ventes"]},
            {"Metrique": "Taux_vente_%", "Valeur": k["taux_pct"]},
            {"Metrique": "Erreurs_lt_1min_Onoff", "Valeur": k["errors_lt_1min"]},
            {
                "Metrique": "Lecture",
                "Valeur": "Clearance=écoulement DC; buckets=Status×Color; reco mix vente",
            },
        ]
    )
    with pd.ExcelWriter(out_path, engine="openpyxl") as w:
        resume.to_excel(w, sheet_name="Resume", index=False)
        result["mix"].to_excel(w, sheet_name="Mix_DC", index=False)
        result["bucket_perf"].to_excel(w, sheet_name="Perf_buckets", index=False)
        if isinstance(result["conversions"], pd.DataFrame) and not result["conversions"].empty:
            result["conversions"].to_excel(w, sheet_name="Conversions")
        result["agents"].to_excel(w, sheet_name="Agents", index=False)
        result["suggested_mix"].to_excel(w, sheet_name="Mix_recommande", index=False)
        result["ventes_detail"].to_excel(w, sheet_name="Ventes_detail", index=False)
        result["non_rappeles"].to_excel(w, sheet_name="Non_rappeles", index=False)
        if not result["errors"].empty:
            result["errors"].to_excel(w, sheet_name="Erreurs_lt_1min", index=False)
    return out_path


def export_daily_campaign_charts(result: dict[str, Any], out_path: str | Path) -> Path | None:
    """Optional 1-page PDF charts. Returns None if matplotlib missing."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages
    except ImportError:
        return None

    out_path = Path(out_path)
    k = result["kpis"]
    mix = result["mix"].head(12).copy()
    agents = result["agents"].head(12).copy() if not result["agents"].empty else pd.DataFrame()

    with PdfPages(out_path) as pdf:
        fig, axes = plt.subplots(2, 2, figsize=(11.69, 8.27))
        fig.suptitle(
            f"Campagne recyclage — {k['day_label']}",
            fontsize=14,
            fontweight="bold",
        )
        fig.text(
            0.5,
            0.93,
            f"DC {k['dc_tels']} · Appelés {k['called']} ({k['clearance_pct']}%) · "
            f"Ventes {k['ventes']} ({k['taux_pct']}%) · Erreurs <1min {k['errors_lt_1min']}",
            ha="center",
            fontsize=9,
            color="#475569",
        )

        ax = axes[0, 0]
        if not mix.empty:
            labels = (mix["Status_Category"].astype(str) + " / " + mix["Color"].astype(str)).tolist()
            ax.barh(labels[::-1], mix["TEL"].tolist()[::-1], color="#2563eb")
            ax.set_title("Mix DC (top buckets)", fontweight="bold")
            ax.set_xlabel("TEL")
        else:
            ax.set_visible(False)

        ax = axes[0, 1]
        if not mix.empty and mix["Appeles"].sum() > 0:
            m2 = mix[mix["Appeles"] > 0].head(10)
            labels = (m2["Status_Category"].astype(str) + " / " + m2["Color"].astype(str)).tolist()
            ax.barh(labels[::-1], m2["Taux_vente_%"].tolist()[::-1], color="#16a34a")
            ax.set_title("Taux vente / appelés (%)", fontweight="bold")
        else:
            ax.text(0.5, 0.5, "Pas d'appels matchés", ha="center", va="center")
            ax.set_axis_off()

        ax = axes[1, 0]
        nr = result["non_rappeles"].head(10)
        if not nr.empty:
            labels = (nr["Status_Category"].astype(str) + " / " + nr["Color"].astype(str)).tolist()
            ax.barh(labels[::-1], nr["Non_rappeles"].tolist()[::-1], color="#f59e0b")
            ax.set_title("Non rappelés (fuite clearance)", fontweight="bold")
        else:
            ax.text(0.5, 0.5, "Clearance 100%", ha="center", va="center")
            ax.set_axis_off()

        ax = axes[1, 1]
        if not agents.empty:
            a = agents.head(10).sort_values("Ventes")
            ax.barh(a["Agent"], a["Ventes"], color="#8b5cf6")
            ax.set_title("Ventes par agent (DC matché)", fontweight="bold")
        else:
            ax.set_visible(False)

        fig.tight_layout(rect=[0, 0.02, 1, 0.91])
        pdf.savefig(fig, dpi=150)
        plt.close(fig)

    return out_path
